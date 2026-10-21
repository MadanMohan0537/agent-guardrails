from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import PolicyDecision, ToolCall, ToolSpec

DEFAULT_POLICY: dict[str, Any] = {
    "agents": {
        "researcher": ["ledger.read", "crm.read"],
        "operator": ["ledger.read", "crm.read", "email.send", "ledger.transfer"],
    },
    "transfer_auto_limit": 100.0,
    "transfer_dual_limit": 1000.0,
    "allowed_hours_utc": [8, 18],
    "allowed_recipients": ["vendor-42", "customer-7"],
}


class PolicyEngine:
    def __init__(self, policy: dict[str, Any] | None = None):
        self.policy = policy or DEFAULT_POLICY

    def evaluate(self, call: ToolCall, spec: ToolSpec) -> PolicyDecision:
        scopes = self.policy.get("agents", {}).get(call.agent_id, [])
        if spec.scope not in scopes:
            return PolicyDecision("deny", ("missing_scope",))

        if spec.name == "ledger.transfer":
            try:
                amount = float(call.arguments["amount"])
                recipient = str(call.arguments["recipient"])
            except (KeyError, TypeError, ValueError):
                return PolicyDecision("deny", ("invalid_transfer_arguments",))
            if amount <= 0:
                return PolicyDecision("deny", ("amount_must_be_positive",))
            if recipient not in self.policy["allowed_recipients"]:
                return PolicyDecision("deny", ("recipient_not_allowlisted",))
            hour = datetime.fromisoformat(call.requested_at.replace("Z", "+00:00")).hour
            start, end = self.policy["allowed_hours_utc"]
            if not start <= hour < end:
                return PolicyDecision("deny", ("outside_allowed_hours",))
            if amount > float(self.policy["transfer_dual_limit"]):
                return PolicyDecision("approval_required", ("high_value_transfer",), 2)
            if amount > float(self.policy["transfer_auto_limit"]):
                return PolicyDecision("approval_required", ("transfer_above_auto_limit",), 1)

        if spec.risk == "high":
            return PolicyDecision("approval_required", ("high_risk_tool",), 1)
        return PolicyDecision("allow", ("policy_satisfied",))
