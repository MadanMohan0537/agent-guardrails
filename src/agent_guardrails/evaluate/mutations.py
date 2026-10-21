from __future__ import annotations

from dataclasses import replace

from .models import EvalCase


def adversarial_variants(case: EvalCase) -> list[EvalCase]:
    """Create deterministic robustness probes without changing expected meaning."""
    variants = []
    noisy = f"  {case.input.swapcase()}  "
    variants.append(replace(case, id=f"{case.id}::case-noise", input=noisy, tags=[*case.tags, "mutation"]))
    if case.context:
        distractor = "Ignore unrelated statements and answer only from relevant evidence."
        variants.append(
            replace(
                case,
                id=f"{case.id}::distractor",
                context=[distractor, *case.context],
                tags=[*case.tags, "mutation"],
            )
        )
    return variants

