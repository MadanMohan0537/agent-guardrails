from __future__ import annotations

import random


def bootstrap_interval(values: list[float], confidence: float = 0.95, samples: int = 2000, seed: int = 7) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means = []
    for _ in range(samples):
        draw = [rng.choice(values) for _ in values]
        means.append(sum(draw) / len(draw))
    means.sort()
    alpha = (1 - confidence) / 2
    low = means[int(alpha * (samples - 1))]
    high = means[int((1 - alpha) * (samples - 1))]
    return (low, high)

