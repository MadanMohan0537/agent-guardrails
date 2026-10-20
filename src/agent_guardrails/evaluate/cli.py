from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from .adapters.fixture import FixtureAdapter
from .adapters.http import HTTPAdapter
from .dataset import load_jsonl
from .mutations import adversarial_variants
from .runner import EvalRunner, release_gate
from .scorers.deterministic import ExactMatch, LatencyBudget, RefusalSafety, RequiredTerms
from .scorers.quality import Groundedness, SemanticReference
from .storage import RunStore


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="sentinel-eval")
    sub = root.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Run an evaluation suite")
    run.add_argument("dataset")
    run.add_argument("--adapter", choices=["fixture", "http"], default="fixture")
    run.add_argument("--endpoint", default=os.getenv("MODEL_ENDPOINT", "http://localhost:8001/v1/chat/completions"))
    run.add_argument("--model", default=os.getenv("MODEL_NAME", "local-model"))
    run.add_argument("--mutations", action="store_true")
    run.add_argument("--min-pass-rate", type=float, default=0.8)
    run.add_argument("--output", default="artifacts/latest-run.json")
    sub.add_parser("history", help="Show recent experiment summaries")
    return root


async def execute(args: argparse.Namespace) -> int:
    store = RunStore()
    if args.command == "history":
        print(json.dumps(store.latest(), indent=2))
        return 0
    cases = load_jsonl(args.dataset)
    if args.mutations:
        cases = [variant for case in cases for variant in [case, *adversarial_variants(case)]]
    adapter = FixtureAdapter() if args.adapter == "fixture" else HTTPAdapter(args.endpoint, args.model, os.getenv("MODEL_API_KEY"))
    scorers = [ExactMatch(), RequiredTerms(), RefusalSafety(), LatencyBudget(), Groundedness(), SemanticReference()]
    run = await EvalRunner(adapter, scorers).run(cases)
    baseline = store.latest(1)
    passed, reasons = release_gate(run, baseline[0] if baseline else None, args.min_pass_rate, 0.02)
    run["gate"] = {"passed": passed, "reasons": reasons}
    store.save(run)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(run, indent=2), encoding="utf-8")
    print(json.dumps({"run_id": run["id"], **run["summary"], "gate": run["gate"]}, indent=2))
    return 0 if passed else 2


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(asyncio.run(execute(parser().parse_args(argv))))


if __name__ == "__main__":
    main()

