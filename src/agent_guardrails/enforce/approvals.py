from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any


def canonical_payload(tool: str, tool_version: str, arguments: dict[str, Any]) -> str:
    payload = {"arguments": arguments, "tool": tool, "tool_version": tool_version}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_hash(tool: str, tool_version: str, arguments: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_payload(tool, tool_version, arguments).encode()).hexdigest()


@dataclass(frozen=True)
class Approval:
    approval_id: str
    payload_hash: str
    approver: str
    expires_at: str

    def valid_for(self, *, tool: str, tool_version: str, arguments: dict[str, Any], now: str) -> bool:
        expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        current = datetime.fromisoformat(now.replace("Z", "+00:00"))
        return current <= expiry and self.payload_hash == payload_hash(tool, tool_version, arguments)


class ApprovalStore:
    def __init__(self) -> None:
        self._items: dict[str, Approval] = {}

    def add(self, approval: Approval) -> None:
        self._items[approval.approval_id] = approval

    def valid_approvers(self, approval_ids: list[str], **payload: Any) -> set[str]:
        return {
            item.approver
            for approval_id in approval_ids
            if (item := self._items.get(approval_id)) and item.valid_for(**payload)
        }
