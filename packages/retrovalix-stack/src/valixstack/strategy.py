from __future__ import annotations

import math

from .core import Side, Signal, Tick


class ProbabilityEdgeStrategy:
    """Transparent baseline model, not a profitability claim."""

    def __init__(self, min_edge: float = 0.03) -> None:
        self.min_edge = min_edge

    def probability_up(self, tick: Tick) -> float:
        distance = (tick.spot - tick.reference) / max(tick.reference, 1e-9)
        score = 140.0 * distance + 8.0 * tick.momentum
        dampener = 1.0 + 10.0 * max(tick.volatility, 0.0)
        return min(0.995, max(0.005, 1.0 / (1.0 + math.exp(-score / dampener))))

    def signal(self, tick: Tick) -> Signal | None:
        p_up = self.probability_up(tick)
        candidates = [
            Signal(Side.UP, p_up, tick.up_ask, p_up - tick.up_ask),
            Signal(Side.DOWN, 1.0 - p_up, tick.down_ask, (1.0 - p_up) - tick.down_ask),
        ]
        best = max(candidates, key=lambda item: item.edge)
        return best if best.edge >= self.min_edge else None

