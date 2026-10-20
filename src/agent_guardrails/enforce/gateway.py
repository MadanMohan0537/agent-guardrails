from __future__ import annotations

from typing import Any

from .approvals import ApprovalStore
from .audit import AuditLog
from .models import ExecutionResult, ToolCall, ToolSpec
from .policy import PolicyEngine
from .tools import ToyEnvironment


class Gateway:
    def __init__(self, policy: PolicyEngine, approvals: ApprovalStore, audit: AuditLog, env: ToyEnvironment):
        self.policy, self.approvals, self.audit, self.env = policy, approvals, audit, env
        self.tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self.tools[spec.name] = spec

    def handle(self, call: ToolCall, approval_ids: list[str] | None = None) -> ExecutionResult:
        spec = self.tools.get(call.tool)
        if not spec:
            self.audit.append(call.requested_at, "denied", {"call_id": call.call_id, "reason": "unknown_tool"})
            return ExecutionResult(call.call_id, "denied", {"reasons": ["unknown_tool"]})
        decision = self.policy.evaluate(call, spec)
        detail = {"reasons": list(decision.reasons), "approvals_required": decision.approvals_required}
        if decision.outcome == "deny":
            self.audit.append(call.requested_at, "denied", {"call": call.__dict__, **detail})
            return ExecutionResult(call.call_id, "denied", detail)
        if decision.outcome == "approval_required":
            approvers = self.approvals.valid_approvers(
                approval_ids or [], tool=call.tool, tool_version=spec.version,
                arguments=call.arguments, now=call.requested_at,
            )
            detail["valid_approvers"] = sorted(approvers)
            if len(approvers) < decision.approvals_required:
                self.audit.append(call.requested_at, "approval_required", {"call": call.__dict__, **detail})
                return ExecutionResult(call.call_id, "approval_required", detail)
        if call.dry_run:
            self.audit.append(call.requested_at, "dry_run", {"call": call.__dict__, **detail})
            return ExecutionResult(call.call_id, "dry_run", {**detail, "would_execute": call.tool})
        result = self.env.execute(call.tool, call.arguments)
        self.audit.append(call.requested_at, "executed", {"call": call.__dict__, "result": result, **detail})
        return ExecutionResult(call.call_id, "executed", result)


def build_gateway(audit_path: str = ":memory:", policy: dict[str, Any] | None = None) -> Gateway:
    gateway = Gateway(PolicyEngine(policy), ApprovalStore(), AuditLog(audit_path), ToyEnvironment())
    for spec in (
        ToolSpec("ledger.read", "1.0", "ledger.read", "read"),
        ToolSpec("crm.read", "1.0", "crm.read", "read"),
        ToolSpec("email.send", "1.0", "email.send", "write"),
        ToolSpec("ledger.transfer", "2.1", "ledger.transfer", "write"),
    ):
        gateway.register(spec)
    return gateway
