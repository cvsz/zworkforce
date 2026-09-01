from __future__ import annotations

from ztrader.abt.binance_perp_bot.indicators import adx, atr, closes
from ztrader.abt.binance_perp_bot.models import MarketSnapshot, RegimeMode


class ADXRegimeDetector:
    def detect(self, snapshot: MarketSnapshot) -> RegimeMode:
        price = closes(snapshot.ohlcv)[-1]
        volatility = atr(snapshot.ohlcv) / max(price, 1e-9)
        trend_strength = adx(snapshot.ohlcv)
        if volatility > 0.045:
            return RegimeMode.HIGH_VOLATILITY
        if trend_strength >= 25:
            return RegimeMode.TREND
        return RegimeMode.MEAN_REVERSION
