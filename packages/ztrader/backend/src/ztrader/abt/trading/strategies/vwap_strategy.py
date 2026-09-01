"""// ZeaZDev [Backend Strategy VWAP] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 2) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from typing import Any, Dict

import numpy as np

from ztrader.abt.trading.strategy_interface import Strategy, StrategyRegistry


class VWAPStrategy(Strategy):
    name = "VWAP"

    def __init__(self, threshold: float = 0.02):
        """
        Volume Weighted Average Price Strategy.

        Args:
            threshold: Percentage deviation from VWAP to trigger signal
                (e.g., 0.02 = 2%)
        """
        self.threshold = threshold
        self.last_signal = "HOLD"

    def calculate_vwap(self, highs, lows, closes, volumes):
        """Calculate VWAP from OHLCV data."""
        typical_prices = (np.array(highs) + np.array(lows) + np.array(closes)) / 3
        vwap = np.cumsum(typical_prices * np.array(volumes)) / np.cumsum(volumes)
        return vwap

    def execute(
        self, ticker_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        closes = ticker_data.get("closes")
        highs = ticker_data.get("highs", closes)
        lows = ticker_data.get("lows", closes)
        volumes = ticker_data.get("volumes")

        if not closes or not volumes or len(closes) < 5:
            return {"signal": "HOLD", "reason": "Insufficient data"}

        if len(volumes) != len(closes):
            return {"signal": "HOLD", "reason": "Volume data mismatch"}

        # Calculate VWAP
        vwap = self.calculate_vwap(highs, lows, closes, volumes)
        current_price = closes[-1]
        current_vwap = vwap[-1]

        # Calculate deviation from VWAP
        deviation = (current_price - current_vwap) / current_vwap

        signal = "HOLD"
        # Price significantly below VWAP -> potential BUY
        if deviation < -self.threshold and self.last_signal != "BUY":
            signal = "BUY"
        # Price significantly above VWAP -> potential SELL
        elif deviation > self.threshold and self.last_signal != "SELL":
            signal = "SELL"

        if signal != "HOLD":
            self.last_signal = signal

        # Confidence based on deviation magnitude
        confidence = min(abs(deviation) / self.threshold, 1.0)

        return {
            "signal": signal,
            "current_price": round(float(current_price), 2),
            "vwap": round(float(current_vwap), 2),
            "deviation": round(float(deviation * 100), 2),  # as percentage
            "confidence": round(float(confidence), 3),
            "meta": {"threshold_percent": self.threshold * 100},
        }


StrategyRegistry.register(VWAPStrategy)
