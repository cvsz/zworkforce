from __future__ import annotations

from ztrader.abt.binance_perp_bot.models import StrategyKind
from ztrader.abt.binance_perp_bot.strategies.base import BaseStrategy
from ztrader.abt.binance_perp_bot.strategies.concrete import (
    PositionStrategy,
    ScalpStrategy,
    SwingStrategy,
)


class StrategyFactory:
    def __init__(self, strategies: list[BaseStrategy] | None = None) -> None:
        self._strategies = strategies or [
            ScalpStrategy(),
            SwingStrategy(),
            PositionStrategy(),
        ]

    def all(self) -> list[BaseStrategy]:
        return list(self._strategies)

    def get(self, kind: StrategyKind) -> BaseStrategy:
        for strategy in self._strategies:
            if strategy.kind == kind:
                return strategy
        raise KeyError(f"Unknown strategy kind: {kind}")
