"""// ZeaZDev [Backend Strategy Breakout] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 2) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from typing import Any, Dict

import numpy as np

from ztrader.abt.trading.strategy_interface import Strategy, StrategyRegistry


class BreakoutStrategy(Strategy):
    name = "BREAKOUT"

    def __init__(self, lookback: int = 20, volume_factor: float = 1.5):
        """
        Breakout Strategy based on price breaking out of recent highs/lows.

        Args:
            lookback: Number of periods to look back for high/low
            volume_factor: Volume multiplier to confirm breakout
        """
        self.lookback = lookback
        self.volume_factor = volume_factor
        self.last_signal = "HOLD"

    def execute(
        self, ticker_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        closes = ticker_data.get("closes")
        highs = ticker_data.get(
            "highs", closes
        )  # Fallback to closes if highs not available
        lows = ticker_data.get(
            "lows", closes
        )  # Fallback to closes if lows not available
        volumes = ticker_data.get("volumes", [])

        if not closes or len(closes) < self.lookback + 5:
            return {"signal": "HOLD", "reason": "Insufficient data"}

        # Calculate recent high and low
        recent_high = (
            max(highs[-self.lookback - 1 : -1])
            if len(highs) > self.lookback
            else max(highs[:-1])
        )
        recent_low = (
            min(lows[-self.lookback - 1 : -1])
            if len(lows) > self.lookback
            else min(lows[:-1])
        )

        current_price = closes[-1]

        # Volume confirmation if available
        volume_confirmed = True
        if len(volumes) > self.lookback:
            avg_volume = np.mean(volumes[-self.lookback - 1 : -1])
            current_volume = volumes[-1]
            volume_confirmed = current_volume > (avg_volume * self.volume_factor)

        signal = "HOLD"
        # Upward breakout
        if (
            current_price > recent_high
            and volume_confirmed
            and self.last_signal != "BUY"
        ):
            signal = "BUY"
        # Downward breakout
        elif (
            current_price < recent_low
            and volume_confirmed
            and self.last_signal != "SELL"
        ):
            signal = "SELL"

        if signal != "HOLD":
            self.last_signal = signal

        # Confidence based on breakout strength
        price_range = recent_high - recent_low
        if signal == "BUY":
            breakout_strength = (
                (current_price - recent_high) / price_range if price_range > 0 else 0
            )
        elif signal == "SELL":
            breakout_strength = (
                (recent_low - current_price) / price_range if price_range > 0 else 0
            )
        else:
            breakout_strength = 0

        confidence = min(breakout_strength * 2, 1.0)  # Scale and cap at 1.0

        return {
            "signal": signal,
            "current_price": round(float(current_price), 2),
            "recent_high": round(float(recent_high), 2),
            "recent_low": round(float(recent_low), 2),
            "volume_confirmed": volume_confirmed,
            "confidence": round(float(confidence), 3),
            "meta": {"lookback": self.lookback, "volume_factor": self.volume_factor},
        }


StrategyRegistry.register(BreakoutStrategy)
