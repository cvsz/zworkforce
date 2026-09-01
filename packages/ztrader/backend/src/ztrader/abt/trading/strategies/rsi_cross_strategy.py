"""// ZeaZDev [Backend Strategy RSI Cross] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Omega Scaffolding) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from typing import Any, Dict

import numpy as np
import pandas as pd

from ztrader.abt.trading.strategy_interface import Strategy, StrategyRegistry


class RSICrossStrategy(Strategy):
    name = "RSI_CROSS"

    def __init__(self, period: int = 14, overbought: float = 70, oversold: float = 30):
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
        self.last_signal = "HOLD"

    def compute_rsi(self, closes):
        series = pd.Series(closes)
        delta = series.diff().dropna()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(alpha=1 / self.period, adjust=False).mean()
        ema_down = down.ewm(alpha=1 / self.period, adjust=False).mean()
        rs = ema_up / ema_down.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    def execute(
        self, ticker_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        closes = ticker_data.get("closes")
        if not closes or len(closes) < self.period + 5:
            return {"signal": "HOLD", "rsi": None, "reason": "Insufficient data"}

        rsi = self.compute_rsi(closes)
        signal = "HOLD"
        if rsi < self.oversold and self.last_signal != "BUY":
            signal = "BUY"
        elif rsi > self.overbought and self.last_signal != "SELL":
            signal = "SELL"

        if signal != "HOLD":
            self.last_signal = signal

        confidence = abs(rsi - 50) / 50  # simplistic confidence metric

        return {
            "signal": signal,
            "rsi": round(float(rsi), 2),
            "confidence": round(float(confidence), 3),
            "meta": {"overbought": self.overbought, "oversold": self.oversold},
        }


StrategyRegistry.register(RSICrossStrategy)
