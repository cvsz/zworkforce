"""// ZeaZDev [Core Strategy Base] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from abc import ABC, abstractmethod
from typing import Any


class Strategy(ABC):
    """
    Abstract base class for all trading strategies.

    All strategy implementations must:
    1. Define a unique 'name' attribute (string)
    2. Implement the execute() method
    3. Handle insufficient data gracefully
    4. Return proper signal dict with meta information
    """

    name: str

    @abstractmethod
    def execute(
        self, ticker_data: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute strategy logic on ticker data.

        Args:
            ticker_data: Dictionary containing market data (closes, volumes,
                OHLCV, etc.)
            context: Dictionary with symbol, timeframe, and other metadata

        Returns:
            Dictionary containing:
                - signal: str - One of "BUY", "SELL", or "HOLD"
                - confidence: float - Confidence level between 0.0 and 1.0
                - meta: dict - Additional metadata (indicators, reasons, etc.)

        The implementation should:
        - Check for sufficient data (return HOLD with meta.reason if insufficient)
        - Handle NaN values gracefully
        - Include reason in meta when returning HOLD
        - Scale confidence appropriately based on signal strength
        """
        pass
