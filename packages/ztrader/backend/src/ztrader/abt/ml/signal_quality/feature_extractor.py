"""
Feature extraction for signal quality scoring.
"""

from typing import Any, Dict

import numpy as np


class FeatureExtractor:
    """Extract features from trading signals for ML models."""

    def extract_signal_features(
        self, signal: Dict[str, Any], market_data: Dict[str, Any] = None
    ) -> Dict[str, float]:
        """
        Extract features from a trading signal.

        Args:
            signal: Trading signal dictionary
            market_data: Market data context (optional)

        Returns:
            Dictionary of feature values
        """
        features = {}

        # Extract indicator values from signal
        indicators = signal.get("indicators", {})

        # RSI feature
        features["rsi"] = float(indicators.get("rsi", 50.0))
        features["rsi_normalized"] = (features["rsi"] - 50) / 50  # Normalize around 50

        # Volume features
        volume = float(indicators.get("volume", 1000000))
        features["volume"] = volume
        features["volume_log"] = np.log1p(volume)

        # Trend features
        trend = indicators.get("trend", "NEUTRAL")
        features["trend_bullish"] = 1.0 if trend == "BULLISH" else 0.0
        features["trend_bearish"] = 1.0 if trend == "BEARISH" else 0.0

        # Signal type
        signal_type = signal.get("type", "NEUTRAL")
        features["signal_buy"] = 1.0 if signal_type == "BUY" else 0.0
        features["signal_sell"] = 1.0 if signal_type == "SELL" else 0.0

        # Price features
        price = float(signal.get("price", 0))
        features["price"] = price
        features["price_log"] = np.log1p(price) if price > 0 else 0

        # Market data features (if available)
        if market_data:
            features["market_volatility"] = float(market_data.get("volatility", 0.02))
            features["market_volume_ratio"] = float(
                market_data.get("volume_ratio", 1.0)
            )
            features["market_momentum"] = float(market_data.get("momentum", 0.0))
        else:
            # Default values if no market data
            features["market_volatility"] = 0.02
            features["market_volume_ratio"] = 1.0
            features["market_momentum"] = 0.0

        # Additional technical indicators
        features["ma_cross"] = float(indicators.get("ma_cross", 0.0))
        features["macd"] = float(indicators.get("macd", 0.0))
        features["bollinger_position"] = float(
            indicators.get("bollinger_position", 0.5)
        )

        # Risk features
        features["risk_reward_ratio"] = float(signal.get("risk_reward_ratio", 1.5))
        features["stop_loss_distance"] = float(signal.get("stop_loss_distance", 0.02))
        features["take_profit_distance"] = float(
            signal.get("take_profit_distance", 0.04)
        )

        # Time-based features
        timestamp = signal.get("timestamp")
        if timestamp:
            features["hour_of_day"] = float(timestamp.hour) / 24.0
            features["day_of_week"] = float(timestamp.weekday()) / 7.0
        else:
            features["hour_of_day"] = 0.5
            features["day_of_week"] = 0.5

        return features

    def extract_market_features(self, market_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract features from market data.

        Args:
            market_data: Market data dictionary

        Returns:
            Dictionary of market features
        """
        features = {}

        # Price features
        if "close" in market_data:
            close_prices = market_data["close"]
            features["price_mean"] = float(np.mean(close_prices))
            features["price_std"] = float(np.std(close_prices))
            features["price_current"] = float(close_prices[-1])

        # Volume features
        if "volume" in market_data:
            volumes = market_data["volume"]
            features["volume_mean"] = float(np.mean(volumes))
            features["volume_std"] = float(np.std(volumes))
            features["volume_current"] = float(volumes[-1])

        # Volatility
        if "high" in market_data and "low" in market_data:
            high_prices = market_data["high"]
            low_prices = market_data["low"]
            features["volatility"] = float(np.mean(high_prices - low_prices))

        return features
