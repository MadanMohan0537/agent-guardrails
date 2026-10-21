import json
from pathlib import Path

from worker.logic import dispatch, issued_payload_hash

from agent_guardrails.enforce.approvals import payload_hash

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
STAMP = "2026-10-09T12:00:00+00:00"


def post(path: str, payload: dict) -> tuple[int, dict]:
    return dispatch("POST", f"https://agent-guardrails.example.workers.dev{path}", json.dumps(payload))


def test_service_info_lists_real_routes_and_limits():
    status, body = dispatch("GET", "https://agent-guardrails.example.workers.dev/")
    assert status == 200
    assert body["name"] == "agent-guardrails"
    paths = [item["path"] for item in body["endpoints"]]
    assert paths == ["/", "/health", "/enforce", "/release"]
    assert any(item.startswith("evaluate:") for item in body["not_available_on_worker"])
    assert "workers.dev" not in json.dumps(body["endpoints"])


def test_health():
    status, body = dispatch("GET", "https://agent-guardrails.example.workers.dev/health")
    assert status == 200
    assert body == {"status": "ok"}


def test_unknown_route():
    status, body = dispatch("POST", "https://agent-guardrails.example.workers.dev/evaluate", "{}")
    assert status == 404
    assert body["error"] == "not_found"


def test_small_transfer_executes_and_audits_one_request():
    status, body = post(
        "/enforce",
        {
            "call_id": "call-001",
            "agent_id": "operator",
            "tool": "ledger.transfer",
            "arguments": {"amount": 75, "recipient": "vendor-42"},
            "requested_at": STAMP,
        },
    )
    assert status == 200
    assert body["outcome"] == "executed"
    assert body["audit_chain_valid"] is True
    assert body["audit_entries"] == 1
    assert body["audit_scope"] == "this request only"
    json.dumps(body, allow_nan=False)


def test_missing_scope_and_unknown_tool_are_denied():
    status, body = post(
        "/enforce",
        {
            "agent_id": "researcher",
            "tool": "ledger.transfer",
            "arguments": {"amount": 20, "recipient": "vendor-42"},
            "requested_at": STAMP,
        },
    )
    assert status == 200
    assert body["outcome"] == "denied"
    status, body = post(
        "/enforce",
        {"agent_id": "operator", "tool": "shell.root", "arguments": {}, "requested_at": STAMP},
    )
    assert body["outcome"] == "denied"
    assert body["detail"]["reasons"] == ["unknown_tool"]


def test_approval_hash_rejects_a_changed_amount():
    arguments = {"amount": 250, "recipient": "vendor-42"}
    digest = issued_payload_hash("ledger.transfer", "2.1", arguments)
    assert digest == payload_hash("ledger.transfer", "2.1", arguments)
    approval = {
        "approval_id": "a1",
        "approver": "finance-lead",
        "expires_at": "2026-10-09T12:30:00+00:00",
        "payload_hash": digest,
    }
    status, body = post(
        "/enforce",
        {
            "agent_id": "operator",
            "tool": "ledger.transfer",
            "arguments": arguments,
            "requested_at": STAMP,
            "approvals": [approval],
        },
    )
    assert status == 200
    assert body["outcome"] == "executed"
    changed = dict(arguments)
    changed["amount"] = 251
    status, body = post(
        "/enforce",
        {
            "agent_id": "operator",
            "tool": "ledger.transfer",
            "arguments": changed,
            "requested_at": STAMP,
            "approvals": [approval],
        },
    )
    assert body["outcome"] == "approval_required"


def test_enforce_rejects_bad_input():
    status, body = dispatch("POST", "https://agent-guardrails.example.workers.dev/enforce", "")
    assert status == 400
    assert body["error"] == "body_required"
    status, body = post("/enforce", {"tool": "ledger.read"})
    assert status == 400
    assert "agent_id" in body["missing"]


def test_release_good_passes_and_bad_blocks():
    policy = json.loads((EXAMPLES / "policy.json").read_text())
    baseline = json.loads((EXAMPLES / "baseline.json").read_text())
    good = json.loads((EXAMPLES / "candidate-good.json").read_text())
    bad = json.loads((EXAMPLES / "candidate-bad.json").read_text())
    status, passed = post("/release", {"baseline": baseline, "candidate": good, "policy": policy})
    assert status == 200
    assert passed["decision"] == "PASS"
    assert passed["candidate"]["quality"] == 1
    status, blocked = post("/release", {"baseline": baseline, "candidate": bad, "policy": policy})
    assert status == 200
    assert blocked["decision"] == "BLOCK"
    assert blocked["candidate"]["quality"] == 0.875
    rules = {item["rule"] for item in blocked["failures"]}
    assert "critical_cohort_quality" in rules
    assert "critical_cohort_regression" in rules
    json.dumps(blocked, allow_nan=False)


def test_release_rejects_a_policy_typo():
    policy = json.loads((EXAMPLES / "policy.json").read_text())
    baseline = json.loads((EXAMPLES / "baseline.json").read_text())
    policy["minimun_quality"] = 1
    status, body = post("/release", {"baseline": baseline, "candidate": baseline, "policy": policy})
    assert status == 422
    assert "unknown policy" in body["message"]
