from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import EvalCase


def load_jsonl(path: str | Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            try:
                data = json.loads(raw)
                cases.append(EvalCase(**data))
            except (json.JSONDecodeError, TypeError) as exc:
                raise ValueError(f"Invalid dataset row {line_number}: {exc}") from exc
    if not cases:
        raise ValueError("Dataset is empty")
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Dataset case IDs must be unique")
    return cases


def dataset_fingerprint(cases: list[EvalCase]) -> str:
    canonical = [case.__dict__ for case in sorted(cases, key=lambda item: item.id)]
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]

