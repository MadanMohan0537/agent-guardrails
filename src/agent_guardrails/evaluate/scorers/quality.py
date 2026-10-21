from __future__ import annotations

import re

from ..models import EvalCase, ModelResponse, Score


class Groundedness:
    """Token-overlap proxy that runs offline; replace or complement with a judge."""

    name = "groundedness"

    def __init__(self, threshold: float = 0.45) -> None:
        self.threshold = threshold

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {token.casefold() for token in re.findall(r"[a-zA-Z0-9]+", text) if len(token) > 2}

    def score(self, case: EvalCase, response: ModelResponse) -> Score:
        if not case.context:
            return Score(self.name, 1.0, True, "No grounding context")
        output_tokens = self._tokens(response.text)
        context_tokens = self._tokens(" ".join(case.context))
        value = len(output_tokens & context_tokens) / max(1, len(output_tokens))
        return Score(self.name, value, value >= self.threshold, f"Context overlap {value:.2%}")


class SemanticReference:
    """Lightweight token F1 reference metric with no external model dependency."""

    name = "reference_f1"

    def __init__(self, threshold: float = 0.65) -> None:
        self.threshold = threshold

    def score(self, case: EvalCase, response: ModelResponse) -> Score:
        if not case.expected:
            return Score(self.name, 1.0, True, "No reference answer")
        expected = Groundedness._tokens(case.expected)
        actual = Groundedness._tokens(response.text)
        overlap = len(expected & actual)
        precision = overlap / max(1, len(actual))
        recall = overlap / max(1, len(expected))
        value = 2 * precision * recall / max(precision + recall, 1e-9)
        return Score(self.name, value, value >= self.threshold, f"Token F1 {value:.3f}")

