from __future__ import annotations

import time

import httpx

from ..models import EvalCase, ModelResponse


class HTTPAdapter:
    """Calls an OpenAI-compatible chat-completions endpoint."""

    def __init__(self, endpoint: str, model: str, api_key: str | None = None) -> None:
        self.endpoint = endpoint
        self.name = model
        self.api_key = api_key

    async def generate(self, case: EvalCase) -> ModelResponse:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        messages = []
        if case.context:
            messages.append({"role": "system", "content": "\n\n".join(case.context)})
        messages.append({"role": "user", "content": case.input})
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self.endpoint,
                headers=headers,
                json={"model": self.name, "messages": messages, "temperature": 0},
            )
            response.raise_for_status()
            data = response.json()
        usage = data.get("usage", {})
        return ModelResponse(
            text=data["choices"][0]["message"]["content"],
            latency_ms=(time.perf_counter() - started) * 1000,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            trace=[{"type": "http", "endpoint": self.endpoint, "status": response.status_code}],
        )

