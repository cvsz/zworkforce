from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import ccxt.pro as ccxtpro
from ztrader.abt.binance_perp_bot.config import BotConfig
from ztrader.abt.binance_perp_bot.data_buffer import MarketDataBuffer
from ztrader.abt.binance_perp_bot.models import MarketSnapshot, PositionIntent
from ztrader.abt.binance_perp_bot.runtime import BotRuntimeState
from prometheus_client import Counter, Gauge

SnapshotHandler = Callable[[MarketSnapshot], Awaitable[None]]

STREAM_RECONNECTS = Counter(
    "omega_stream_reconnects_total",
    "WebSocket reconnect attempts",
    ["symbol", "timeframe"],
)
STREAM_HEARTBEAT = Gauge(
    "omega_stream_last_heartbeat_timestamp", "Last successful exchange heartbeat epoch"
)
SNAPSHOTS = Counter(
    "omega_market_snapshots_total", "Market snapshots emitted", ["symbol", "timeframe"]
)


class BinancePerpStream:
    def __init__(
        self,
        config: BotConfig,
        on_snapshot: SnapshotHandler,
        runtime_state: BotRuntimeState | None = None,
        buffer: MarketDataBuffer | None = None,
    ) -> None:
        self.config = config
        self.on_snapshot = on_snapshot
        self.runtime_state = runtime_state
        self.buffer = buffer or MarketDataBuffer(config.max_candles_per_stream)
        self.exchange = self._build_exchange()
        self.logger = logging.getLogger(__name__)
        self._stopping = asyncio.Event()
        self._reconnect_lock = asyncio.Lock()
        self._markets_loaded = False

    def _build_exchange(self):
        return ccxtpro.binanceusdm(
            {
                "apiKey": self.config.binance_api_key.get_secret_value(),
                "secret": self.config.binance_api_secret.get_secret_value(),
                "enableRateLimit": True,
                "options": {"defaultType": "swap", "adjustForTimeDifference": True},
            }
        )

    async def close(self) -> None:
        self._stopping.set()
        if self.runtime_state is not None:
            self.runtime_state.mark_stopping()
        await self.exchange.close()

    async def stream_symbol(self, symbol: str, timeframe: str) -> None:
        backoff = 1.0
        stream_id = f"{symbol}:{timeframe}"
        while not self._stopping.is_set():
            heartbeat_task = asyncio.create_task(self._heartbeat(symbol, timeframe))
            try:
                await self._ensure_markets_loaded()
                if self.runtime_state is not None:
                    self.runtime_state.mark_stream_ready()
                while not self._stopping.is_set():
                    if heartbeat_task.done():
                        heartbeat_task.result()
                    await self._stream_once(symbol, timeframe, stream_id)
                    backoff = 1.0
            except (asyncio.CancelledError, KeyboardInterrupt):
                raise
            except Exception as exc:
                if self.runtime_state is not None:
                    self.runtime_state.mark_error(exc)
                STREAM_RECONNECTS.labels(symbol=symbol, timeframe=timeframe).inc()
                self.logger.warning(
                    "websocket_reconnect",
                    extra={
                        "symbol": symbol,
                        "trace_id": "stream",
                        "strategy": timeframe,
                    },
                    exc_info=exc,
                )
                await self._recreate_exchange()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, self.config.max_reconnect_backoff_seconds)
            finally:
                heartbeat_task.cancel()
                await asyncio.gather(heartbeat_task, return_exceptions=True)

    async def _stream_once(
        self, symbol: str, timeframe: str, stream_id: str
    ) -> None:
        orderbook_task = asyncio.create_task(
            self.exchange.watch_order_book(symbol, limit=20)
        )
        ticker_task = asyncio.create_task(self.exchange.watch_ticker(symbol))
        try:
            orderbook, ticker = await asyncio.wait_for(
                asyncio.gather(orderbook_task, ticker_task),
                timeout=self.config.websocket_timeout_seconds,
            )
        except TimeoutError as exc:
            for task in (orderbook_task, ticker_task):
                task.cancel()
            await asyncio.gather(
                orderbook_task, ticker_task, return_exceptions=True
            )
            raise TimeoutError(
                f"WebSocket stalled for {stream_id}"
            ) from exc
        ohlcv = await self.exchange.fetch_ohlcv(
            symbol, timeframe=timeframe, limit=250
        )
        buffered = await self.buffer.upsert(
            MarketSnapshot(symbol, timeframe, ohlcv, ticker, orderbook)
        )
        if self.runtime_state is not None:
            self.runtime_state.mark_snapshot()
        SNAPSHOTS.labels(symbol=symbol, timeframe=timeframe).inc()
        await self.on_snapshot(buffered.latest)

    async def _ensure_markets_loaded(self) -> None:
        if self._markets_loaded:
            return
        async with self._reconnect_lock:
            if not self._markets_loaded:
                await self.exchange.load_markets()
                self._markets_loaded = True

    async def _heartbeat(self, symbol: str, timeframe: str) -> None:
        while not self._stopping.is_set():
            await asyncio.sleep(self.config.heartbeat_interval_seconds)
            await asyncio.wait_for(self.exchange.fetch_time(), timeout=10)
            if self.runtime_state is not None:
                self.runtime_state.mark_heartbeat()
            STREAM_HEARTBEAT.set_to_current_time()
            self.logger.info(
                "websocket_heartbeat_ok",
                extra={
                    "symbol": symbol,
                    "trace_id": "heartbeat",
                    "strategy": timeframe,
                },
            )

    async def _recreate_exchange(self) -> None:
        async with self._reconnect_lock:
            old_exchange = self.exchange
            self.exchange = self._build_exchange()
            self._markets_loaded = False
            await old_exchange.close()

    async def fetch_equity_usdt(self) -> float:
        balance = await self.exchange.fetch_balance({"type": "swap"})
        return float(balance["USDT"]["total"])

    async def execute(self, intent: PositionIntent) -> dict[str, Any]:
        if self.config.dry_run:
            return {
                "id": f"dry-{intent.signal.trace_id}",
                "average": intent.signal.metadata.get("price"),
                "status": "closed",
            }
        return await self.exchange.create_order(
            intent.signal.symbol,
            "market",
            intent.side.value,
            intent.amount,
            None,
            {"reduceOnly": intent.reduce_only, "leverage": intent.leverage},
        )
