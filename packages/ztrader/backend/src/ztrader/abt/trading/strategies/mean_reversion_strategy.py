"""// ZeaZDev [Backend Strategy Mean Reversion] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 2 Enhanced) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from typing import Any, Dict

import numpy as np
import pandas as pd

from ztrader.abt.trading.strategy_interface import Strategy, StrategyRegistry


class MeanReversionStrategy(Strategy):
    name = "MEAN_REVERSION"

    def __init__(
        self,
        window: int = 20,
        std_dev_factor: float = 2.0,
        z_entry: float = 2.0,
        z_exit: float = 0.5,
    ):
        """
        Mean Reversion Strategy using Bollinger Bands and Z-score logic.

        Combines Bollinger Bands with Z-score analysis and hysteresis
        to identify overbought/oversold conditions and mean reversion opportunities.

        Args:
            window: Moving average window period for calculations
            std_dev_factor: Standard deviation multiplier for Bollinger Bands
            z_entry: Z-score threshold for entry signals (oversold/overbought)
            z_exit: Z-score threshold for exit (hysteresis - mean reversion)
        """
        self.window = window
        self.std_dev_factor = std_dev_factor
        self.z_entry = z_entry
        self.z_exit = z_exit
        self.last_signal = "HOLD"

    def execute(  # noqa: C901
        self, ticker_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute mean reversion strategy with Bollinger Bands and Z-score analysis.

        Args:
            ticker_data: Dictionary containing 'closes' (price series)
            context: Dictionary with symbol, timeframe, and other metadata

        Returns:
            Dictionary with signal, confidence, and meta information
        """
        closes = ticker_data.get("closes")

        # Validate input data
        if not closes:
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "meta": {"reason": "No price data provided"},
            }

        if len(closes) < self.window + 5:
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "meta": {
                    "reason": (
                        f"Insufficient data: need {self.window + 5}, got {len(closes)}"
                    )
                },
            }

        # Convert to pandas Series for calculations
        try:
            series = pd.Series(closes, dtype=float)
        except (ValueError, TypeError) as e:
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "meta": {"reason": f"Invalid price data: {str(e)}"},
            }

        # Calculate Bollinger Bands
        ma = series.rolling(window=self.window).mean()
        std = series.rolling(window=self.window).std()

        upper_band = ma + (std * self.std_dev_factor)
        lower_band = ma - (std * self.std_dev_factor)

        # Calculate Z-score (standardized distance from mean)
        z_score = (series - ma) / std.replace(0, np.nan)

        # Get current values
        current_price = series.iloc[-1]
        current_ma = ma.iloc[-1]
        current_std = std.iloc[-1]
        current_upper = upper_band.iloc[-1]
        current_lower = lower_band.iloc[-1]
        current_z = z_score.iloc[-1]

        # Check for NaN values
        if pd.isna([current_price, current_ma, current_std, current_z]).any():
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "meta": {
                    "reason": (
                        "Insufficient historical data for calculation (NaN values)"
                    )
                },
            }

        # Determine signal using Z-score with hysteresis
        signal = "HOLD"
        reason = "No signal threshold met"

        # Entry conditions (strong oversold/overbought)
        if current_z < -self.z_entry and self.last_signal != "BUY":
            # Price significantly below mean (oversold) -> BUY signal
            signal = "BUY"
            reason = f"Oversold: Z-score {current_z:.2f} < -{self.z_entry}"
        elif current_z > self.z_entry and self.last_signal != "SELL":
            # Price significantly above mean (overbought) -> SELL signal
            signal = "SELL"
            reason = f"Overbought: Z-score {current_z:.2f} > {self.z_entry}"

        # Exit conditions (hysteresis - reversion to mean)
        elif abs(current_z) < self.z_exit and self.last_signal in ["BUY", "SELL"]:
            # Price reverted close to mean -> exit position
            signal = "HOLD"
            reason = (
                f"Mean reversion: Z-score {current_z:.2f} near 0 "
                f"(exit threshold {self.z_exit})"
            )
            self.last_signal = "HOLD"

        # Update last signal if we have a new entry
        if signal in ["BUY", "SELL"]:
            self.last_signal = signal

        # Calculate confidence based on Z-score magnitude and band position
        # Higher confidence for stronger deviation from mean
        z_confidence = (
            min(abs(current_z) / self.z_entry, 1.0) if self.z_entry > 0 else 0.0
        )

        # Additional confidence from Bollinger Band position
        band_width = current_upper - current_lower
        if band_width > 0:
            distance_from_mean = abs(current_price - current_ma)
            band_confidence = min(distance_from_mean / (band_width / 2), 1.0)
        else:
            band_confidence = 0.0

        # Combined confidence (weighted average)
        confidence = z_confidence * 0.6 + band_confidence * 0.4

        # Reduce confidence for HOLD signals
        if signal == "HOLD":
            confidence *= 0.3

        return {
            "signal": signal,
            "confidence": round(float(confidence), 3),
            "meta": {
                "reason": reason,
                "z_score": round(float(current_z), 3),
                "bands": {
                    "upper": round(float(current_upper), 2),
                    "middle": round(float(current_ma), 2),
                    "lower": round(float(current_lower), 2),
                },
                "current_price": round(float(current_price), 2),
                "window": self.window,
                "std_dev_factor": self.std_dev_factor,
                "z_entry": self.z_entry,
                "z_exit": self.z_exit,
            },
        }


StrategyRegistry.register(MeanReversionStrategy)
