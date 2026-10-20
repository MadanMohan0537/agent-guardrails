from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


class AuditLog:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS audit (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, event TEXT NOT NULL,
            payload TEXT NOT NULL, previous_hash TEXT NOT NULL, entry_hash TEXT NOT NULL UNIQUE
        )""")

    @staticmethod
    def _hash(at: str, event: str, payload: str, previous_hash: str) -> str:
        raw = json.dumps([at, event, payload, previous_hash], separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()

    def append(self, at: str, event: str, payload: dict[str, Any]) -> str:
        row = self.db.execute("SELECT entry_hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        previous = row[0] if row else "GENESIS"
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = self._hash(at, event, body, previous)
        self.db.execute(
            "INSERT INTO audit(at,event,payload,previous_hash,entry_hash) VALUES(?,?,?,?,?)",
            (at, event, body, previous, digest),
        )
        self.db.commit()
        return digest

    def entries(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.db.execute("SELECT * FROM audit ORDER BY seq")]

    def verify(self) -> bool:
        previous = "GENESIS"
        for row in self.db.execute("SELECT * FROM audit ORDER BY seq"):
            if row["previous_hash"] != previous:
                return False
            if row["entry_hash"] != self._hash(row["at"], row["event"], row["payload"], previous):
                return False
            previous = row["entry_hash"]
        return True
