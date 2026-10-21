import unittest
from datetime import datetime, timedelta, timezone

from agent_guardrails.enforce.approvals import Approval, canonical_payload, payload_hash
from agent_guardrails.enforce.audit import AuditLog
from agent_guardrails.enforce.gateway import build_gateway
from agent_guardrails.enforce.models import ToolCall

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
STAMP = NOW.isoformat()


class ScopeLockTests(unittest.TestCase):
    def setUp(self):
        self.gateway = build_gateway()

    def call(self, cid, agent, tool, args, dry=False):
        return ToolCall(cid, agent, tool, args, STAMP, dry)

    def approve(self, call, approver="lead", version="2.1", expires=None):
        approval = Approval(
            f"a-{approver}", payload_hash(call.tool, version, call.arguments), approver,
            (expires or NOW + timedelta(minutes=5)).isoformat(),
        )
        self.gateway.approvals.add(approval)
        return approval.approval_id

    def test_unknown_tool_denied_by_default(self):
        result = self.gateway.handle(self.call("1", "operator", "shell.root", {}))
        self.assertEqual("denied", result.outcome)

    def test_missing_scope_denied(self):
        result = self.gateway.handle(self.call("2", "researcher", "email.send", {"to": "x", "subject": "y"}))
        self.assertEqual("denied", result.outcome)

    def test_read_allowed(self):
        result = self.gateway.handle(self.call("3", "researcher", "ledger.read", {"account": "operating"}))
        self.assertEqual(5000.0, result.detail["balance"])

    def test_small_transfer_auto_executes(self):
        result = self.gateway.handle(self.call("4", "operator", "ledger.transfer", {"amount": 75, "recipient": "vendor-42"}))
        self.assertEqual("executed", result.outcome)

    def test_medium_transfer_requires_approval(self):
        call = self.call("5", "operator", "ledger.transfer", {"amount": 250, "recipient": "vendor-42"})
        self.assertEqual("approval_required", self.gateway.handle(call).outcome)
        self.assertEqual("executed", self.gateway.handle(call, [self.approve(call)]).outcome)

    def test_high_value_requires_distinct_dual_approval(self):
        call = self.call("6", "operator", "ledger.transfer", {"amount": 1200, "recipient": "vendor-42"})
        first = self.approve(call, "finance")
        self.assertEqual("approval_required", self.gateway.handle(call, [first]).outcome)
        second = self.approve(call, "risk")
        self.assertEqual("executed", self.gateway.handle(call, [first, second]).outcome)

    def test_duplicate_approver_does_not_satisfy_dual_control(self):
        call = self.call("7", "operator", "ledger.transfer", {"amount": 1200, "recipient": "vendor-42"})
        approval = self.approve(call, "same-person")
        self.assertEqual("approval_required", self.gateway.handle(call, [approval, approval]).outcome)

    def test_binding_rejects_changed_amount(self):
        original = self.call("8", "operator", "ledger.transfer", {"amount": 250, "recipient": "vendor-42"})
        approval = self.approve(original)
        changed = self.call("9", "operator", "ledger.transfer", {"amount": 251, "recipient": "vendor-42"})
        self.assertEqual("approval_required", self.gateway.handle(changed, [approval]).outcome)

    def test_binding_rejects_changed_recipient(self):
        original = self.call("10", "operator", "ledger.transfer", {"amount": 250, "recipient": "vendor-42"})
        approval = self.approve(original)
        changed = self.call("11", "operator", "ledger.transfer", {"amount": 250, "recipient": "customer-7"})
        self.assertEqual("approval_required", self.gateway.handle(changed, [approval]).outcome)

    def test_binding_rejects_tool_version_change(self):
        call = self.call("12", "operator", "ledger.transfer", {"amount": 250, "recipient": "vendor-42"})
        approval = self.approve(call, version="2.0")
        self.assertEqual("approval_required", self.gateway.handle(call, [approval]).outcome)

    def test_expired_approval_rejected(self):
        call = self.call("13", "operator", "ledger.transfer", {"amount": 250, "recipient": "vendor-42"})
        approval = self.approve(call, expires=NOW - timedelta(seconds=1))
        self.assertEqual("approval_required", self.gateway.handle(call, [approval]).outcome)

    def test_canonicalization_ignores_key_order(self):
        a = canonical_payload("t", "1", {"b": 2, "a": 1})
        b = canonical_payload("t", "1", {"a": 1, "b": 2})
        self.assertEqual(a, b)

    def test_dry_run_does_not_mutate(self):
        call = self.call("14", "operator", "ledger.transfer", {"amount": 75, "recipient": "vendor-42"}, True)
        before = self.gateway.env.snapshot()
        self.assertEqual("dry_run", self.gateway.handle(call).outcome)
        self.assertEqual(before, self.gateway.env.snapshot())

    def test_outside_hours_denied(self):
        call = ToolCall("15", "operator", "ledger.transfer", {"amount": 10, "recipient": "vendor-42"}, "2026-10-09T02:00:00+00:00")
        self.assertEqual("denied", self.gateway.handle(call).outcome)

    def test_unapproved_recipient_denied(self):
        call = self.call("16", "operator", "ledger.transfer", {"amount": 10, "recipient": "attacker"})
        self.assertEqual("denied", self.gateway.handle(call).outcome)

    def test_audit_chain_detects_tampering(self):
        log = AuditLog()
        log.append(STAMP, "one", {"x": 1})
        log.append(STAMP, "two", {"x": 2})
        self.assertTrue(log.verify())
        log.db.execute("UPDATE audit SET payload='{}' WHERE seq=1")
        log.db.commit()
        self.assertFalse(log.verify())


if __name__ == "__main__":
    unittest.main()
