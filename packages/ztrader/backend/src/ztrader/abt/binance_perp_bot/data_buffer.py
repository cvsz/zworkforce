from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass

from ztrader.abt.binance_perp_bot.models import MarketSnapshot


@dataclass(frozen=True)
class BufferedMarketState:
    latest: MarketSnapshot
    retained_candles: int


class MarketDataBuffer:
    """Bounded async buffer that serializes updates per symbol/timeframe.

    WebSocket orderbook/ticker events arrive independently from REST OHLCV refreshes.
    This buffer gives the engine a single latest snapshot per stream and caps candle
    retention so mixed M1-through-W1 workers do not grow memory without bounds.
    """

    def __init__(self, max_candles_per_stream: int = 500) -> None:
        self.max_candles_per_stream = max_candles_per_stream
        self._snapshots: OrderedDict[tuple[str, str], MarketSnapshot] = OrderedDict()
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

    async def upsert(self, snapshot: MarketSnapshot) -> BufferedMarketState:
        key = (snapshot.symbol, snapshot.timeframe)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            bounded = snapshot.with_bounded_ohlcv(self.max_candles_per_stream)
            self._snapshots[key] = bounded
            self._snapshots.move_to_end(key)
            return BufferedMarketState(bounded, len(bounded.ohlcv))

    async def latest(self, symbol: str, timeframe: str) -> MarketSnapshot | None:
        key = (symbol, timeframe)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            return self._snapshots.get(key)
