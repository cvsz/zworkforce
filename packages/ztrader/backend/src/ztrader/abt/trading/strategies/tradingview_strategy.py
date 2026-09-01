"""// ZeaZDev [Backend TradingView Strategy] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from typing import Any, Dict

from ztrader.abt.trading.strategy_interface import Strategy, StrategyRegistry


class TradingViewStrategy(Strategy):
    """
    Strategy that executes based on TradingView webhook alerts.

    This strategy acts as a bridge between TradingView alerts and the trading system.
    It processes alerts received via webhook and executes them as trading signals.

    Unlike other strategies that analyze market data, this strategy trusts the
    external TradingView signal and simply passes it through with proper formatting.
    """

    name = "TRADINGVIEW"

    def __init__(self, min_confidence: float = 0.7):
        """
        Initialize TradingView strategy.

        Args:
            min_confidence: Minimum confidence level to execute alerts (0.0 to 1.0)
        """
        self.min_confidence = min_confidence
        self.last_signal = "HOLD"
        self.last_alert = None

    def execute(
        self, ticker_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute strategy based on TradingView alert data.

        Args:
            ticker_data: Dictionary containing:
                - tradingview_alert: Dict with alert data (action, price, etc.)
                - closes: Optional list of recent close prices for validation
            context: Dictionary with symbol, timeframe, and other metadata

        Returns:
            Dictionary containing:
                - signal: str - One of "BUY", "SELL", or "HOLD"
                - confidence: float - Confidence level between 0.0 and 1.0
                - meta: dict - Additional metadata from TradingView alert
        """
        # Check if we have a TradingView alert in the data
        alert = ticker_data.get("tradingview_alert")

        if not alert:
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "meta": {
                    "reason": "No TradingView alert data provided",
                    "source": "TRADINGVIEW",
                },
            }

        # Extract alert information
        action = alert.get("action", "HOLD").upper()
        price = alert.get("price")
        strategy_name = alert.get("strategy", "Unknown")
        interval = alert.get("interval", context.get("timeframe", "unknown"))
        message = alert.get("message", "")

        # Validate action
        if action not in ["BUY", "SELL", "CLOSE", "HOLD"]:
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "meta": {
                    "reason": f"Invalid action: {action}",
                    "source": "TRADINGVIEW",
                },
            }

        # Convert CLOSE to SELL for compatibility
        signal = "SELL" if action == "CLOSE" else action

        # Calculate confidence based on alert metadata
        # If alert provides explicit confidence, use it; otherwise use default
        confidence = alert.get("confidence", 0.8)

        # Additional validation: check if price is reasonable
        closes = ticker_data.get("closes", [])
        if closes and price:
            last_close = closes[-1]
            price_deviation = abs(price - last_close) / last_close

            # If price deviates more than 10% from last close, reduce confidence
            if price_deviation > 0.1:
                confidence *= 0.7

        # Apply minimum confidence filter
        if confidence < self.min_confidence and signal != "HOLD":
            return {
                "signal": "HOLD",
                "confidence": confidence,
                "meta": {
                    "reason": (
                        f"Confidence {confidence:.2f} below minimum "
                        f"{self.min_confidence}"
                    ),
                    "original_signal": signal,
                    "tradingview_strategy": strategy_name,
                    "interval": interval,
                    "source": "TRADINGVIEW",
                },
            }

        # Store last signal to prevent duplicate executions
        self.last_signal = signal
        self.last_alert = alert

        return {
            "signal": signal,
            "confidence": round(float(confidence), 3),
            "meta": {
                "price": price,
                "tradingview_strategy": strategy_name,
                "interval": interval,
                "message": message,
                "source": "TRADINGVIEW",
            },
        }


# Register the strategy
StrategyRegistry.register(TradingViewStrategy)
