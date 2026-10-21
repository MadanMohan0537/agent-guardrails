from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  model TEXT NOT NULL,
  dataset_hash TEXT NOT NULL,
  summary_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS case_results (
  run_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  passed INTEGER NOT NULL,
  latency_ms REAL NOT NULL,
  response_text TEXT NOT NULL,
  scores_json TEXT NOT NULL,
  PRIMARY KEY (run_id, case_id)
);
"""


class RunStore:
    def __init__(self, path: str | Path = ".agent-guardrails/runs.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def save(self, run: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?)",
                (run["id"], run["created_at"], run["model"], run["dataset_hash"], json.dumps(run["summary"])),
            )
            for result in run["results"]:
                connection.execute(
                    "INSERT OR REPLACE INTO case_results VALUES (?, ?, ?, ?, ?, ?)",
                    (run["id"], result["case_id"], result["passed"], result["latency_ms"], result["response"], json.dumps(result["scores"])),
                )

    def latest(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, created_at, model, dataset_hash, summary_json FROM runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"id": row[0], "created_at": row[1], "model": row[2], "dataset_hash": row[3], "summary": json.loads(row[4])}
            for row in rows
        ]

