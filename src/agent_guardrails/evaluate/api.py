from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from .storage import RunStore

app = FastAPI(title="Agent Guardrails", version="0.1.0")
store = RunStore()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/runs")
def runs(limit: int = 20) -> list[dict]:
    return store.latest(min(max(limit, 1), 100))


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")

