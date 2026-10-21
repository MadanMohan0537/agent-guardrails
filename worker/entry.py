"""Cloudflare Python Worker entrypoint.

Routing and decisions live in logic.py so tests can call them without the
Workers runtime. This module only adapts a fetch request onto that function.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _add_import_roots() -> None:
    """The bundle mounts this file at /session/metadata/entry.py."""
    here = Path(__file__).resolve()
    for base in [here.parent, *list(here.parents)[:4]]:
        if (base / "worker" / "logic.py").is_file() and str(base) not in sys.path:
            sys.path.insert(0, str(base))
        src = base / "src"
        if (src / "agent_guardrails").is_dir() and str(src) not in sys.path:
            sys.path.insert(0, str(src))


_add_import_roots()

from workers import Response, WorkerEntrypoint  # noqa: E402

from worker.logic import dispatch  # noqa: E402


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        raw = None
        if request.method != "GET":
            raw = await request.text()
        status, payload = dispatch(request.method, str(request.url), raw)
        return Response(
            json.dumps(payload, allow_nan=False),
            status=status,
            headers={"content-type": "application/json; charset=utf-8"},
        )
