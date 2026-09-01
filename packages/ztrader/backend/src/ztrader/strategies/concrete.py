from __future__ import annotations

from ztrader.binance_perp_bot.indicators import atr, closes, ema, rsi
from ztrader.binance_perp_bot.models import (
    MarketSnapshot,
    RegimeMode,
    SignalAction,
    StrategyKind,
    TradeSignal,
)
from ztrader.binance_perp_bot.strategies.base import BaseStrategy


def atr_scaled_notional(
    snapshot: MarketSnapshot, equity_usdt: float, base_notional_usdt: float
) -> float:
    close = closes(snapshot.ohlcv)[-1]
    volatility = atr(snapshot.ohlcv) / max(close, 1e-9)
    multiplier = max(0.35, min(1.50, 0.01 / max(volatility, 0.001)))
    return min(equity_usdt, base_notional_usdt * multiplier)


class ScalpStrategy(BaseStrategy):
    kind = StrategyKind.SCALP
    timeframes = ("1m", "5m")

    def check_signal(
        self, snapshot: MarketSnapshot, regime: RegimeMode
    ) -> TradeSignal | None:
        price = closes(snapshot.ohlcv)
        fast = ema(price, 8)
        slow = ema(price, 21)
        momentum = rsi(price, 7)
        if fast > slow and 52 <= momentum <= 72:
            return TradeSignal(
                snapshot.symbol, self.kind, SignalAction.ENTER_LONG, 0.68, 0.0, regime
            )
        if fast < slow and 28 <= momentum <= 48:
            return TradeSignal(
                snapshot.symbol, self.kind, SignalAction.ENTER_SHORT, 0.68, 0.0, regime
            )
        return None

    def calculate_size(
        self, snapshot: MarketSnapshot, equity_usdt: float, base_notional_usdt: float
    ) -> float:
        return atr_scaled_notional(snapshot, equity_usdt, base_notional_usdt)

    def get_regime_suitability(self, regime: RegimeMode) -> float:
        return {
            RegimeMode.MEAN_REVERSION: 0.80,
            RegimeMode.TREND: 0.55,
            RegimeMode.HIGH_VOLATILITY: 0.25,
        }[regime]


class SwingStrategy(BaseStrategy):
    kind = StrategyKind.SWING
    timeframes = ("4h", "1d")

    def check_signal(
        self, snapshot: MarketSnapshot, regime: RegimeMode
    ) -> TradeSignal | None:
        price = closes(snapshot.ohlcv)
        fast = ema(price, 20)
        slow = ema(price, 50)
        momentum = rsi(price, 14)
        if fast > slow and momentum > 55:
            return TradeSignal(
                snapshot.symbol, self.kind, SignalAction.ENTER_LONG, 0.72, 0.0, regime
            )
        if fast < slow and momentum < 45:
            return TradeSignal(
                snapshot.symbol, self.kind, SignalAction.ENTER_SHORT, 0.72, 0.0, regime
            )
        return None

    def calculate_size(
        self, snapshot: MarketSnapshot, equity_usdt: float, base_notional_usdt: float
    ) -> float:
        return atr_scaled_notional(snapshot, equity_usdt, base_notional_usdt)

    def get_regime_suitability(self, regime: RegimeMode) -> float:
        return {
            RegimeMode.TREND: 0.90,
            RegimeMode.MEAN_REVERSION: 0.45,
            RegimeMode.HIGH_VOLATILITY: 0.35,
        }[regime]


class PositionStrategy(BaseStrategy):
    kind = StrategyKind.POSITION
    timeframes = ("1d", "1w")

    def check_signal(
        self, snapshot: MarketSnapshot, regime: RegimeMode
    ) -> TradeSignal | None:
        price = closes(snapshot.ohlcv)
        fast = ema(price, 50)
        slow = ema(price, 200)
        momentum = rsi(price, 21)
        if fast > slow and momentum >= 50:
            return TradeSignal(
                snapshot.symbol, self.kind, SignalAction.ENTER_LONG, 0.76, 0.0, regime
            )
        if fast < slow and momentum <= 50:
            return TradeSignal(
                snapshot.symbol, self.kind, SignalAction.ENTER_SHORT, 0.76, 0.0, regime
            )
        return None

    def calculate_size(
        self, snapshot: MarketSnapshot, equity_usdt: float, base_notional_usdt: float
    ) -> float:
        return atr_scaled_notional(snapshot, equity_usdt, base_notional_usdt)

    def get_regime_suitability(self, regime: RegimeMode) -> float:
        return {
            RegimeMode.TREND: 0.95,
            RegimeMode.MEAN_REVERSION: 0.30,
            RegimeMode.HIGH_VOLATILITY: 0.40,
        }[regime]
