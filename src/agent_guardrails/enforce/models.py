from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Decision = Literal["allow", "deny", "approval_required"]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    version: str
    scope: str
    risk: Literal["read", "write", "high"]


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    agent_id: str
    tool: str
    arguments: dict[str, Any]
    requested_at: str
    dry_run: bool = False


@dataclass(frozen=True)
class PolicyDecision:
    outcome: Decision
    reasons: tuple[str, ...]
    approvals_required: int = 0


@dataclass
class ExecutionResult:
    call_id: str
    outcome: str
    detail: dict[str, Any] = field(default_factory=dict)
