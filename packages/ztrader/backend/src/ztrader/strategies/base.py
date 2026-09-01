from __future__ import annotations

from abc import ABC, abstractmethod

from ztrader.binance_perp_bot.models import (
    MarketSnapshot,
    RegimeMode,
    StrategyKind,
    TradeSignal,
)


class BaseStrategy(ABC):
    kind: StrategyKind
    timeframes: tuple[str, ...]

    @abstractmethod
    def check_signal(
        self, snapshot: MarketSnapshot, regime: RegimeMode
    ) -> TradeSignal | None:
        """Return a trade signal only when technical confluence is present."""

    @abstractmethod
    def calculate_size(
        self, snapshot: MarketSnapshot, equity_usdt: float, base_notional_usdt: float
    ) -> float:
        """Return ATR-adjusted notional size in USDT."""

    @abstractmethod
    def get_regime_suitability(self, regime: RegimeMode) -> float:
        """Return suitability score from 0.0 to 1.0 for the detected market regime."""
