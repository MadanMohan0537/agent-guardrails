"""HTTP API over the tool gateway and the release gate.

The evaluation harness is not served here. It keeps a local SQLite experiment
store, a FastAPI dashboard, and an optional outbound model call. Those do not
run in this Worker. Each /enforce request builds a new in-memory gateway, so
the audit chain covers that request only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse


def _add_toolkit_path() -> None:
    """Make `agent_guardrails` importable locally and inside the Worker bundle.

    Locally the package lives at `<repo>/src`. Wrangler copies the entry file to
    `/session/metadata/entry.py` and mounts the other modules beside it, so the
    `src` directory may be next to this file rather than one level up.
    """
    here = Path(__file__).resolve()
    bases = [here.parent, *list(here.parents)[:4]]
    for base in bases:
        src = base / "src"
        if (src / "agent_guardrails").is_dir() and str(src) not in sys.path:
            sys.path.insert(0, str(src))
            return
        if (base / "agent_guardrails").is_dir() and str(base) not in sys.path:
            sys.path.insert(0, str(base))
            return


_add_toolkit_path()

from agent_guardrails.enforce.approvals import Approval, payload_hash  # noqa: E402
from agent_guardrails.enforce.gateway import build_gateway  # noqa: E402
from agent_guardrails.enforce.models import ToolCall  # noqa: E402
from agent_guardrails.release.gate import compare  # noqa: E402

_NOT_ON_WORKER = [
    "evaluate: suite runner, robustness mutations, experiment history, and the dashboard stay on a local Python process",
    "durable audit history across requests: /enforce uses a new in-memory SQLite log each time",
    "HTML release reports: the Worker returns the JSON decision from the same compare function the CLI uses",
]


def service_info() -> dict:
    return {
        "name": "agent-guardrails",
        "runtime": "cloudflare-python-worker",
        "endpoints": [
            {"method": "GET", "path": "/", "purpose": "Service info"},
            {"method": "GET", "path": "/health", "purpose": "Process check"},
            {"method": "POST", "path": "/enforce", "purpose": "Tool-call gateway"},
            {"method": "POST", "path": "/release", "purpose": "Baseline versus candidate gate"},
        ],
        "not_available_on_worker": list(_NOT_ON_WORKER),
    }


def dispatch(method: str, url: str, body: str | None = None) -> tuple[int, dict]:
    path = urlparse(url).path.rstrip("/") or "/"
    if method == "GET" and path == "/":
        return 200, service_info()
    if method == "GET" and path == "/health":
        return 200, {"status": "ok"}
    if method == "POST" and path == "/enforce":
        return enforce(body)
    if method == "POST" and path == "/release":
        return release(body)
    return 404, {"error": "not_found", "path": path}


def enforce(body: str | None) -> tuple[int, dict]:
    payload, error = _object(body)
    if error:
        return 400, error
    missing = [key for key in ("agent_id", "tool", "requested_at") if key not in payload]
    if missing:
        return 400, {"error": "invalid_call", "missing": missing}
    arguments = payload.get("arguments", {})
    if not isinstance(arguments, dict):
        return 400, {"error": "arguments_must_be_object"}
    dry_run = payload.get("dry_run", False)
    if not isinstance(dry_run, bool):
        return 400, {"error": "dry_run_must_be_boolean"}
    approvals = payload.get("approvals", [])
    if not isinstance(approvals, list):
        return 400, {"error": "approvals_must_be_a_list"}
    try:
        gateway = build_gateway(":memory:")
    except Exception as exc:  # noqa: BLE001 - surface a runtime the Worker cannot load
        return 501, {"error": "enforce_unavailable", "reason": f"{type(exc).__name__}: {exc}"}
    call = ToolCall(
        call_id=str(payload.get("call_id") or "call"),
        agent_id=str(payload["agent_id"]),
        tool=str(payload["tool"]),
        arguments=arguments,
        requested_at=str(payload["requested_at"]),
        dry_run=dry_run,
    )
    approval_ids: list[str] = []
    for item in approvals:
        built, failure = _approval(item)
        if failure:
            return 400, failure
        gateway.approvals.add(built)
        approval_ids.append(built.approval_id)
    result = gateway.handle(call, approval_ids or None)
    return 200, {
        "call_id": result.call_id,
        "outcome": result.outcome,
        "detail": result.detail,
        "audit_entries": len(gateway.audit.entries()),
        "audit_chain_valid": gateway.audit.verify(),
        "audit_scope": "this request only",
    }


def _approval(item: object) -> tuple[Approval | None, dict | None]:
    if not isinstance(item, dict):
        return None, {"error": "approval_must_be_object"}
    missing = [key for key in ("approval_id", "approver", "expires_at", "payload_hash") if key not in item]
    if missing:
        return None, {"error": "invalid_approval", "missing": missing}
    # The hash is the one issued for a specific payload. It is not recomputed
    # from the arguments on this request, or a changed call would approve itself.
    return Approval(
        str(item["approval_id"]),
        str(item["payload_hash"]),
        str(item["approver"]),
        str(item["expires_at"]),
    ), None


def release(body: str | None) -> tuple[int, dict]:
    payload, error = _object(body)
    if error:
        return 400, error
    missing = [key for key in ("baseline", "candidate", "policy") if key not in payload]
    if missing:
        return 400, {"error": "invalid_release", "missing": missing}
    try:
        report = compare(payload["baseline"], payload["candidate"], payload["policy"])
    except (ValueError, TypeError) as exc:
        return 422, {"error": "invalid_evaluation", "message": str(exc)}
    return 200, report


def _object(body: str | None) -> tuple[dict | None, dict | None]:
    if body is None or not str(body).strip():
        return None, {"error": "body_required"}
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        return None, {"error": "invalid_json", "message": str(exc)}
    if not isinstance(payload, dict):
        return None, {"error": "body_must_be_object"}
    return payload, None


def issued_payload_hash(tool: str, tool_version: str, arguments: dict) -> str:
    """Hash helper for clients that bind an approval before execution."""
    return payload_hash(tool, tool_version, arguments)
