from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

from .models import IntelligenceResponse, TokenRef, WatchlistEntry


class AnalysisStore:
    def __init__(self, path: str | None = None):
        configured = path or os.getenv("ZTRADER_INTEL_DB", "./data/ztrader_intel.db")
        self.path = Path(configured)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    chain TEXT NOT NULL,
                    address TEXT,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_analyses_symbol
                    ON analyses(symbol, chain, created_at DESC);

                CREATE TABLE IF NOT EXISTS watchlist (
                    symbol TEXT NOT NULL,
                    chain TEXT NOT NULL,
                    address TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(symbol, chain, address)
                );
                """
            )

    def save(self, result: IntelligenceResponse) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO analyses(symbol, chain, address, payload) VALUES (?, ?, ?, ?)",
                (
                    result.token.symbol,
                    result.token.chain,
                    result.token.address,
                    result.model_dump_json(),
                ),
            )

    def history(self, symbol: str, chain: str | None = None, limit: int = 100) -> list[dict[str, str]]:
        query = "SELECT payload, created_at FROM analyses WHERE symbol = ?"
        params: list[object] = [symbol]
        if chain:
            query += " AND chain = ?"
            params.append(chain)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._lock, self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [{"created_at": row["created_at"], "payload": row["payload"]} for row in rows]

    def upsert_watchlist(self, entry: WatchlistEntry) -> None:
        address = entry.token.address or ""
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO watchlist(symbol, chain, address, note)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(symbol, chain, address)
                DO UPDATE SET note=excluded.note, updated_at=CURRENT_TIMESTAMP
                """,
                (entry.token.symbol, entry.token.chain, address, entry.note),
            )

    def list_watchlist(self) -> list[WatchlistEntry]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT symbol, chain, address, note FROM watchlist ORDER BY updated_at DESC"
            ).fetchall()
        return [
            WatchlistEntry(
                token=TokenRef(
                    symbol=row["symbol"],
                    chain=row["chain"],
                    address=row["address"] or None,
                ),
                note=row["note"],
            )
            for row in rows
        ]
