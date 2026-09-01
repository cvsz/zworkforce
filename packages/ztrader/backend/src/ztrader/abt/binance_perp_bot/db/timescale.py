from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

import psycopg2
from ztrader.abt.binance_perp_bot.models import MarketSnapshot, TradeSignal
from psycopg2 import errors
from psycopg2.extras import Json


class TimescaleJournal:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    async def migrate(self) -> None:
        await asyncio.to_thread(self._migrate_sync)

    async def write_ohlcv(self, snapshot: MarketSnapshot) -> None:
        await asyncio.to_thread(self._write_ohlcv_sync, snapshot)

    async def write_signal(
        self, signal: TradeSignal, status: str, payload: dict[str, Any]
    ) -> None:
        await asyncio.to_thread(self._write_signal_sync, signal, status, payload)

    def _connect(self):
        return psycopg2.connect(self.dsn)

    def _migrate_sync(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            timescale_enabled = True
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
            except (errors.InsufficientPrivilege, errors.UndefinedFile):
                conn.rollback()
                timescale_enabled = False
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ohlcv (
                    time TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    open DOUBLE PRECISION NOT NULL,
                    high DOUBLE PRECISION NOT NULL,
                    low DOUBLE PRECISION NOT NULL,
                    close DOUBLE PRECISION NOT NULL,
                    volume DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (time, symbol, timeframe)
                )
                """
            )
            if timescale_enabled:
                cur.execute(
                    "SELECT create_hypertable('ohlcv', 'time', if_not_exists => TRUE)"
                )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS trade_journal (
                    time TIMESTAMPTZ NOT NULL DEFAULT now(),
                    trace_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload JSONB NOT NULL
                )
                """
            )
            if timescale_enabled:
                cur.execute(
                    "SELECT create_hypertable("
                    "'trade_journal', 'time', if_not_exists => TRUE)"
                )

    def _write_ohlcv_sync(self, snapshot: MarketSnapshot) -> None:
        rows = self._rows(snapshot)
        with self._connect() as conn, conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO ohlcv (
                    time, symbol, timeframe, open, high, low, close, volume
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
                    open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
                    close = EXCLUDED.close, volume = EXCLUDED.volume
                """,
                rows,
            )

    def _write_signal_sync(
        self, signal: TradeSignal, status: str, payload: dict[str, Any]
    ) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO trade_journal (
                    trace_id, symbol, strategy, action, status, payload
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    signal.trace_id,
                    signal.symbol,
                    signal.strategy.value,
                    signal.action.value,
                    status,
                    Json(payload),
                ),
            )

    def _rows(self, snapshot: MarketSnapshot) -> Iterable[tuple[Any, ...]]:
        for candle in snapshot.ohlcv:
            yield (
                datetime.fromtimestamp(candle[0] / 1000, timezone.utc),
                snapshot.symbol,
                snapshot.timeframe,
                candle[1],
                candle[2],
                candle[3],
                candle[4],
                candle[5],
            )
