from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .approvals import Approval, payload_hash
from .gateway import build_gateway
from .models import ToolCall


def run_demo(audit_path: str = "scopelock.db") -> dict:
    gateway = build_gateway(audit_path)
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    timestamp = now.isoformat()
    cases = [
        ToolCall("read-1", "researcher", "ledger.read", {"account": "operating"}, timestamp),
        ToolCall("blocked-1", "researcher", "ledger.transfer", {"amount": 20, "recipient": "vendor-42"}, timestamp),
        ToolCall("dry-1", "operator", "email.send", {"to": "ops@example.test", "subject": "Status"}, timestamp, True),
        ToolCall("auto-1", "operator", "ledger.transfer", {"amount": 75, "recipient": "vendor-42"}, timestamp),
        ToolCall("approve-1", "operator", "ledger.transfer", {"amount": 250, "recipient": "vendor-42"}, timestamp),
    ]
    results = [gateway.handle(call) for call in cases]
    requested = cases[-1]
    approval = Approval(
        "approval-1", payload_hash(requested.tool, "2.1", requested.arguments), "finance-lead",
        (now + timedelta(minutes=15)).isoformat(),
    )
    gateway.approvals.add(approval)
    results.append(gateway.handle(requested, [approval.approval_id]))
    tampered = ToolCall("tamper-1", "operator", "ledger.transfer", {"amount": 251, "recipient": "vendor-42"}, timestamp)
    results.append(gateway.handle(tampered, [approval.approval_id]))
    return {
        "results": [result.__dict__ for result in results],
        "environment": gateway.env.snapshot(),
        "audit_entries": len(gateway.audit.entries()),
        "audit_chain_valid": gateway.audit.verify(),
        "binding_experiment": {"original_executed": results[-2].outcome == "executed", "mutated_rejected": results[-1].outcome == "approval_required"},
    }
