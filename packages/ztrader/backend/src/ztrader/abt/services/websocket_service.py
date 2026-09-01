"""// ZeaZDev [Backend WebSocket Market Data Service] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 2) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Set

import ccxt.pro as ccxtpro

logger = logging.getLogger(__name__)


class MarketDataWebSocket:
    """WebSocket service for streaming real-time market data."""

    def __init__(self, exchange_name: str = "binance"):
        """
        Initialize WebSocket connection.

        Args:
            exchange_name: Name of the exchange (e.g., 'binance', 'kraken')
        """
        self.exchange_name = exchange_name
        self.exchange: Optional[ccxtpro.Exchange] = None
        self.subscriptions: Dict[str, Set[Callable]] = {}  # symbol -> set of callbacks
        self._running = False
        self._tasks: Dict[str, asyncio.Task] = {}

    async def connect(
        self, api_key: Optional[str] = None, api_secret: Optional[str] = None
    ):
        """Connect to exchange WebSocket."""
        try:
            exchange_class = getattr(ccxtpro, self.exchange_name)
            config = {"enableRateLimit": True}

            if api_key and api_secret:
                config["apiKey"] = api_key
                config["secret"] = api_secret

            self.exchange = exchange_class(config)
            self._running = True
            logger.info(f"Connected to {self.exchange_name} WebSocket")
        except Exception as e:
            logger.error(f"Failed to connect to {self.exchange_name} WebSocket: {e}")
            raise

    async def disconnect(self):
        """Disconnect from exchange WebSocket."""
        self._running = False

        # Cancel all streaming tasks
        for task in self._tasks.values():
            task.cancel()

        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)

        if self.exchange:
            await self.exchange.close()
            logger.info(f"Disconnected from {self.exchange_name} WebSocket")

    async def subscribe_ticker(
        self, symbol: str, callback: Callable[[Dict[str, Any]], None]
    ):
        """
        Subscribe to ticker updates for a symbol.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            callback: Async function to call with ticker data
        """
        if symbol not in self.subscriptions:
            self.subscriptions[symbol] = set()

        self.subscriptions[symbol].add(callback)

        # Start streaming task if not already running for this symbol
        if symbol not in self._tasks:
            task = asyncio.create_task(self._stream_ticker(symbol))
            self._tasks[symbol] = task
            logger.info(f"Started ticker stream for {symbol}")

    def unsubscribe_ticker(self, symbol: str, callback: Callable):
        """Unsubscribe from ticker updates."""
        if symbol in self.subscriptions:
            self.subscriptions[symbol].discard(callback)

            # Stop streaming if no more callbacks
            if not self.subscriptions[symbol]:
                if symbol in self._tasks:
                    self._tasks[symbol].cancel()
                    del self._tasks[symbol]
                del self.subscriptions[symbol]
                logger.info(f"Stopped ticker stream for {symbol}")

    async def _stream_ticker(self, symbol: str):
        """Internal method to stream ticker data."""
        if not self.exchange:
            logger.error("Exchange not connected")
            return

        try:
            while self._running and symbol in self.subscriptions:
                ticker = await self.exchange.watch_ticker(symbol)

                # Normalize ticker data
                normalized_ticker = {
                    "symbol": symbol,
                    "timestamp": ticker.get(
                        "timestamp", datetime.utcnow().timestamp() * 1000
                    ),
                    "datetime": ticker.get("datetime", datetime.utcnow().isoformat()),
                    "high": ticker.get("high"),
                    "low": ticker.get("low"),
                    "bid": ticker.get("bid"),
                    "ask": ticker.get("ask"),
                    "last": ticker.get("last"),
                    "close": ticker.get("close"),
                    "baseVolume": ticker.get("baseVolume"),
                    "quoteVolume": ticker.get("quoteVolume"),
                    "change": ticker.get("change"),
                    "percentage": ticker.get("percentage"),
                }

                # Call all registered callbacks
                if symbol in self.subscriptions:
                    for callback in self.subscriptions[symbol]:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(normalized_ticker)
                            else:
                                callback(normalized_ticker)
                        except Exception as e:
                            logger.error(f"Error in ticker callback for {symbol}: {e}")

        except asyncio.CancelledError:
            logger.info(f"Ticker stream cancelled for {symbol}")
        except Exception as e:
            logger.error(f"Error streaming ticker for {symbol}: {e}")

    async def subscribe_trades(self, symbol: str, callback: Callable[[list], None]):
        """
        Subscribe to trade updates for a symbol.

        Args:
            symbol: Trading pair symbol
            callback: Async function to call with list of trades
        """
        key = f"{symbol}_trades"
        if key not in self.subscriptions:
            self.subscriptions[key] = set()

        self.subscriptions[key].add(callback)

        if key not in self._tasks:
            task = asyncio.create_task(self._stream_trades(symbol))
            self._tasks[key] = task
            logger.info(f"Started trades stream for {symbol}")

    async def _stream_trades(self, symbol: str):
        """Internal method to stream trades."""
        if not self.exchange:
            logger.error("Exchange not connected")
            return

        key = f"{symbol}_trades"

        try:
            while self._running and key in self.subscriptions:
                trades = await self.exchange.watch_trades(symbol)

                # Normalize trades data
                normalized_trades = []
                for trade in trades:
                    normalized_trades.append(
                        {
                            "id": trade.get("id"),
                            "timestamp": trade.get("timestamp"),
                            "datetime": trade.get("datetime"),
                            "symbol": trade.get("symbol"),
                            "side": trade.get("side"),
                            "price": trade.get("price"),
                            "amount": trade.get("amount"),
                            "cost": trade.get("cost"),
                        }
                    )

                # Call all registered callbacks
                if key in self.subscriptions:
                    for callback in self.subscriptions[key]:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(normalized_trades)
                            else:
                                callback(normalized_trades)
                        except Exception as e:
                            logger.error(f"Error in trades callback for {symbol}: {e}")

        except asyncio.CancelledError:
            logger.info(f"Trades stream cancelled for {symbol}")
        except Exception as e:
            logger.error(f"Error streaming trades for {symbol}: {e}")

    def get_active_subscriptions(self) -> Dict[str, int]:
        """Get count of active subscriptions per symbol."""
        result = {}
        for key, callbacks in self.subscriptions.items():
            result[key] = len(callbacks)
        return result


# Singleton instance for global access
_websocket_instance: Optional[MarketDataWebSocket] = None


def get_websocket_instance(exchange_name: str = "binance") -> MarketDataWebSocket:
    """Get or create the global WebSocket instance."""
    global _websocket_instance
    if _websocket_instance is None:
        _websocket_instance = MarketDataWebSocket(exchange_name)
    return _websocket_instance
