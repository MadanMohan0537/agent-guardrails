from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from statistics import mean
from uuid import uuid4

from .dataset import dataset_fingerprint
from .models import CaseResult, EvalCase
from .statistics import bootstrap_interval


class EvalRunner:
    def __init__(self, adapter, scorers: list, concurrency: int = 5) -> None:
        self.adapter = adapter
        self.scorers = scorers
        self.semaphore = asyncio.Semaphore(concurrency)

    async def _run_case(self, case: EvalCase) -> CaseResult:
        async with self.semaphore:
            try:
                response = await self.adapter.generate(case)
                return CaseResult(case, response, [scorer.score(case, response) for scorer in self.scorers])
            except Exception as exc:  # noqa: BLE001 - isolate one failed case from the experiment
                from .models import ModelResponse

                return CaseResult(case, ModelResponse("", 0), [], [f"{type(exc).__name__}: {exc}"])

    async def run(self, cases: list[EvalCase]) -> dict:
        results = await asyncio.gather(*(self._run_case(case) for case in cases))
        pass_values = [float(item.passed) for item in results]
        low, high = bootstrap_interval(pass_values)
        latencies = [item.response.latency_ms for item in results]
        summary = {
            "cases": len(results),
            "passed": sum(item.passed for item in results),
            "pass_rate": mean(pass_values),
            "pass_rate_ci95": [low, high],
            "mean_latency_ms": mean(latencies),
            "total_cost_usd": sum(item.response.cost_usd for item in results),
        }
        return {
            "id": str(uuid4()),
            "created_at": datetime.now(UTC).isoformat(),
            "model": self.adapter.name,
            "dataset_hash": dataset_fingerprint(cases),
            "summary": summary,
            "results": [
                {
                    "case_id": item.case.id,
                    "passed": item.passed,
                    "response": item.response.text,
                    "latency_ms": item.response.latency_ms,
                    "scores": [score.__dict__ for score in item.scores],
                    "errors": item.errors,
                    "tags": item.case.tags,
                }
                for item in results
            ],
        }


def release_gate(current: dict, baseline: dict | None, min_pass_rate: float, max_regression: float) -> tuple[bool, list[str]]:
    reasons = []
    rate = current["summary"]["pass_rate"]
    if rate < min_pass_rate:
        reasons.append(f"pass rate {rate:.1%} is below {min_pass_rate:.1%}")
    if baseline:
        delta = baseline["summary"]["pass_rate"] - rate
        if delta > max_regression:
            reasons.append(f"regression {delta:.1%} exceeds {max_regression:.1%}")
    return (not reasons, reasons)
