"""
Feature extraction for volatility prediction.
"""

from typing import Any, Dict

import numpy as np


class VolatilityFeatures:
    """Extract features for volatility prediction."""

    def extract(
        self, market_data: Dict[str, Any], window: int = 24
    ) -> Dict[str, float]:
        """
        Extract volatility prediction features.

        Args:
            market_data: Market data dictionary
            window: Lookback window for feature calculation

        Returns:
            Dictionary of feature values
        """
        features = {}

        # Get price data
        if isinstance(market_data, dict) and "close" in market_data:
            close_prices = np.array(market_data["close"])
            high_prices = np.array(market_data.get("high", close_prices))
            low_prices = np.array(market_data.get("low", close_prices))
            volumes = np.array(market_data.get("volume", [1000000] * len(close_prices)))
        else:
            # Mock data for testing
            close_prices = np.array([100.0] * window)
            high_prices = close_prices * 1.01
            low_prices = close_prices * 0.99
            volumes = np.array([1000000] * window)

        # Calculate returns
        returns = np.diff(close_prices) / close_prices[:-1]

        # Historical volatility features (annualized)
        if len(returns) >= 1:
            features["realized_vol_1h"] = float(
                np.std(returns[-1:]) * np.sqrt(8760)
            )  # Hourly to annual
        else:
            features["realized_vol_1h"] = 0.02

        if len(returns) >= 6:
            features["realized_vol_6h"] = float(np.std(returns[-6:]) * np.sqrt(1460))
        else:
            features["realized_vol_6h"] = 0.02

        if len(returns) >= 24:
            features["realized_vol_24h"] = float(np.std(returns[-24:]) * np.sqrt(365))
        else:
            features["realized_vol_24h"] = 0.02

        # Return features
        features["returns_mean"] = float(np.mean(returns)) if len(returns) > 0 else 0.0
        features["returns_std"] = float(np.std(returns)) if len(returns) > 0 else 0.0
        features["abs_returns_mean"] = (
            float(np.mean(np.abs(returns))) if len(returns) > 0 else 0.0
        )

        # Volume features
        features["volume_mean"] = float(np.mean(volumes))
        features["volume_std"] = float(np.std(volumes))
        features["volume_current_ratio"] = (
            float(volumes[-1] / np.mean(volumes)) if np.mean(volumes) > 0 else 1.0
        )

        # Range features
        high_low_range = high_prices - low_prices
        features["high_low_range_mean"] = float(np.mean(high_low_range))
        features["high_low_range_std"] = float(np.std(high_low_range))

        # Momentum features
        if len(close_prices) >= 2:
            features["momentum_1h"] = float((close_prices[-1] / close_prices[-2]) - 1)
        else:
            features["momentum_1h"] = 0.0

        if len(close_prices) >= 7:
            features["momentum_6h"] = float((close_prices[-1] / close_prices[-7]) - 1)
        else:
            features["momentum_6h"] = 0.0

        if len(close_prices) >= 25:
            features["momentum_24h"] = float((close_prices[-1] / close_prices[-25]) - 1)
        else:
            features["momentum_24h"] = 0.0

        # Price jump features
        features["price_jumps"] = float(self._count_price_jumps(returns))
        features["max_jump"] = (
            float(np.max(np.abs(returns))) if len(returns) > 0 else 0.0
        )

        # Trend features
        features["trend_strength"] = float(self._calculate_trend_strength(close_prices))

        return features

    def _count_price_jumps(self, returns: np.ndarray, threshold: float = 0.01) -> int:
        """Count significant price jumps."""
        if len(returns) == 0:
            return 0
        return int(np.sum(np.abs(returns) > threshold))

    def _calculate_trend_strength(self, prices: np.ndarray) -> float:
        """Calculate trend strength using linear regression."""
        if len(prices) < 2:
            return 0.0

        x = np.arange(len(prices))
        # Simple linear regression
        slope = (len(prices) * np.sum(x * prices) - np.sum(x) * np.sum(prices)) / (
            len(prices) * np.sum(x**2) - np.sum(x) ** 2
        )

        # Normalize by price level
        normalized_slope = slope / np.mean(prices) if np.mean(prices) > 0 else 0

        return float(normalized_slope)
