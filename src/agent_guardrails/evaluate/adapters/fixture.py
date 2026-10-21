from __future__ import annotations

import asyncio
import time

from ..models import EvalCase, ModelResponse


class FixtureAdapter:
    """Deterministic adapter for demos, tests, and CI without model spend."""

    name = "fixture-v1"

    async def generate(self, case: EvalCase) -> ModelResponse:
        started = time.perf_counter()
        await asyncio.sleep(0)
        if case.metadata.get("fixture_output"):
            text = str(case.metadata["fixture_output"])
        elif case.expected:
            text = case.expected
        else:
            text = f"I can help with: {case.input}"
        return ModelResponse(
            text=text,
            latency_ms=(time.perf_counter() - started) * 1000,
            input_tokens=max(1, len(case.input.split())),
            output_tokens=max(1, len(text.split())),
            trace=[{"type": "model", "name": self.name, "status": "ok"}],
        )

