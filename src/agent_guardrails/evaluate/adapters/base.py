from __future__ import annotations

from typing import Protocol

from ..models import EvalCase, ModelResponse


class ModelAdapter(Protocol):
    name: str

    async def generate(self, case: EvalCase) -> ModelResponse: ...

