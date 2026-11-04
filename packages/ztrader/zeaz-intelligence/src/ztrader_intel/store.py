from __future__ import annotations

import os
import re
import sqlite3
import threading
from pathlib import Path

from .models import IntelligenceResponse, TokenRef, WatchlistEntry

_TENANT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,63}$")


def normalize_tenant_id(tenant_id: str | None) -> str:
    candidate = (tenant_id or "default").strip().lower()
    if not _TENANT_ID_RE.match(candidate):
        raise ValueError("invalid tenant_id")
    return candidate


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
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    symbol TEXT NOT NULL,
                    chain TEXT NOT NULL,
                    address TEXT,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            analyses_cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(analyses)").fetchall()
            }
            if "tenant_id" not in analyses_cols:
                conn.execute(
                    "ALTER TABLE analyses ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'"
                )
            conn.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_analyses_symbol
                    ON analyses(symbol, chain, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_analyses_tenant_symbol
                    ON analyses(tenant_id, symbol, chain, created_at DESC);

                CREATE TABLE IF NOT EXISTS watchlist (
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    symbol TEXT NOT NULL,
                    chain TEXT NOT NULL,
                    address TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(tenant_id, symbol, chain, address)
                );
                """
            )
            watchlist_cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(watchlist)").fetchall()
            }
            if "tenant_id" not in watchlist_cols:
                conn.executescript(
                    """
                    ALTER TABLE watchlist RENAME TO watchlist_legacy;
                    CREATE TABLE watchlist (
                        tenant_id TEXT NOT NULL DEFAULT 'default',
                        symbol TEXT NOT NULL,
                        chain TEXT NOT NULL,
                        address TEXT NOT NULL DEFAULT '',
                        note TEXT NOT NULL DEFAULT '',
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY(tenant_id, symbol, chain, address)
                    );
                    INSERT INTO watchlist(tenant_id, symbol, chain, address, note, updated_at)
                    SELECT 'default', symbol, chain, address, note, updated_at FROM watchlist_legacy;
                    DROP TABLE watchlist_legacy;
                    """
                )

    def save(self, result: IntelligenceResponse, tenant_id: str = "default") -> None:
        scoped_tenant = normalize_tenant_id(tenant_id)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO analyses(tenant_id, symbol, chain, address, payload) VALUES (?, ?, ?, ?, ?)",
                (
                    scoped_tenant,
                    result.token.symbol,
                    result.token.chain,
                    result.token.address,
                    result.model_dump_json(),
                ),
            )

    def history(
        self,
        symbol: str,
        chain: str | None = None,
        limit: int = 100,
        tenant_id: str = "default",
    ) -> list[dict[str, str]]:
        scoped_tenant = normalize_tenant_id(tenant_id)
        query = "SELECT payload, created_at FROM analyses WHERE tenant_id = ? AND symbol = ?"
        params: list[object] = [scoped_tenant, symbol]
        if chain:
            query += " AND chain = ?"
            params.append(chain)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._lock, self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [{"created_at": row["created_at"], "payload": row["payload"]} for row in rows]

    def upsert_watchlist(self, entry: WatchlistEntry, tenant_id: str = "default") -> None:
        scoped_tenant = normalize_tenant_id(tenant_id)
        address = entry.token.address or ""
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO watchlist(tenant_id, symbol, chain, address, note)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, symbol, chain, address)
                DO UPDATE SET note=excluded.note, updated_at=CURRENT_TIMESTAMP
                """,
                (scoped_tenant, entry.token.symbol, entry.token.chain, address, entry.note),
            )

    def list_watchlist(self, tenant_id: str = "default") -> list[WatchlistEntry]:
        scoped_tenant = normalize_tenant_id(tenant_id)
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT symbol, chain, address, note FROM watchlist WHERE tenant_id = ? ORDER BY updated_at DESC",
                (scoped_tenant,),
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
