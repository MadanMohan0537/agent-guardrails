from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvalCase:
    id: str
    input: str
    expected: str | None = None
    context: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelResponse:
    text: str
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    trace: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class Score:
    name: str
    value: float
    passed: bool
    reason: str = ""


@dataclass
class CaseResult:
    case: EvalCase
    response: ModelResponse
    scores: list[Score]
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors and all(score.passed for score in self.scores)

