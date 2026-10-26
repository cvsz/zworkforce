from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PaperAccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    initial_cash_usd: float = Field(gt=0, le=1_000_000_000)


class PaperOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1, max_length=64)
    symbol: str = Field(min_length=1, max_length=64)
    chain: str = Field(min_length=1, max_length=64)
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0, le=1_000_000_000)
    reference_price: float = Field(gt=0, le=1_000_000_000)
    fee_bps: float = Field(default=10, ge=0, le=1_000)
    slippage_bps: float = Field(default=5, ge=0, le=1_000)
    idempotency_key: str = Field(min_length=8, max_length=128)


class PaperOrder(BaseModel):
    order_id: str
    account_id: str
    symbol: str
    chain: str
    side: Literal["buy", "sell"]
    quantity: float
    reference_price: float
    fill_price: float
    notional_usd: float
    fee_usd: float
    status: Literal["filled"]
    idempotency_key: str
    created_at: str


class PaperPosition(BaseModel):
    symbol: str
    chain: str
    quantity: float
    average_cost_usd: float
    mark_price_usd: float
    market_value_usd: float
    unrealized_pnl_usd: float


class PaperAccount(BaseModel):
    account_id: str
    initial_cash_usd: float
    cash_usd: float
    realized_pnl_usd: float
    unrealized_pnl_usd: float
    equity_usd: float
    total_fees_usd: float
    positions: list[PaperPosition]
    execution_mode: Literal["paper"] = "paper"
    live_execution_enabled: Literal[False] = False


class PaperTradingError(ValueError):
    """A simulated order failed a deterministic paper-trading validation."""


class PaperTradingStore:
    """SQLite-backed paper broker. This class never calls an external venue."""

    def __init__(self, path: str | None = None) -> None:
        configured = path or os.getenv("ZTRADER_PAPER_DB", "./data/ztrader_paper.db")
        self.path = Path(configured)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS paper_accounts (
                    account_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    initial_cash REAL NOT NULL CHECK(initial_cash > 0),
                    cash REAL NOT NULL CHECK(cash >= -0.00000001),
                    realized_pnl REAL NOT NULL DEFAULT 0,
                    total_fees REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS paper_positions (
                    account_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    chain TEXT NOT NULL,
                    quantity REAL NOT NULL CHECK(quantity >= -0.00000001),
                    average_cost REAL NOT NULL CHECK(average_cost >= 0),
                    mark_price REAL NOT NULL CHECK(mark_price > 0),
                    PRIMARY KEY(account_id, symbol, chain),
                    FOREIGN KEY(account_id) REFERENCES paper_accounts(account_id)
                );
                CREATE TABLE IF NOT EXISTS paper_orders (
                    order_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    chain TEXT NOT NULL,
                    side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
                    quantity REAL NOT NULL CHECK(quantity > 0),
                    reference_price REAL NOT NULL CHECK(reference_price > 0),
                    fill_price REAL NOT NULL CHECK(fill_price > 0),
                    notional REAL NOT NULL CHECK(notional > 0),
                    fee REAL NOT NULL CHECK(fee >= 0),
                    status TEXT NOT NULL CHECK(status = 'filled'),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(account_id, idempotency_key),
                    FOREIGN KEY(account_id) REFERENCES paper_accounts(account_id)
                );
                CREATE INDEX IF NOT EXISTS idx_paper_orders_account
                    ON paper_orders(account_id, created_at DESC);
                """
            )
            account_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(paper_accounts)")
            }
            if "tenant_id" not in account_columns:
                conn.execute(
                    "ALTER TABLE paper_accounts ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local'"
                )

    def create_account(self, request: PaperAccountCreate, tenant_id: str = "local") -> PaperAccount:
        if not tenant_id.strip():
            raise PaperTradingError("tenant_id is required")
        import uuid

        account_id = uuid.uuid4().hex
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO paper_accounts(account_id, tenant_id, initial_cash, cash) VALUES (?, ?, ?, ?)",
                (account_id, tenant_id, request.initial_cash_usd, request.initial_cash_usd),
            )
            conn.commit()
        return self.get_account(account_id, tenant_id)

    @staticmethod
    def _request_hash(request: PaperOrderRequest) -> str:
        encoded = json.dumps(
            request.model_dump(exclude={"idempotency_key"}),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def submit_order(self, request: PaperOrderRequest, tenant_id: str = "local") -> PaperOrder:
        import uuid

        fill_price = request.reference_price * (
            1 + request.slippage_bps / 10_000
            if request.side == "buy"
            else 1 - request.slippage_bps / 10_000
        )
        if fill_price <= 0:
            raise PaperTradingError("slippage produces a non-positive fill price")
        notional = request.quantity * fill_price
        fee = notional * request.fee_bps / 10_000
        request_hash = self._request_hash(request)

        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                account = conn.execute(
                    "SELECT * FROM paper_accounts WHERE account_id = ? AND tenant_id = ?",
                    (request.account_id, tenant_id),
                ).fetchone()
                if account is None:
                    raise PaperTradingError("paper account not found")

                existing = conn.execute(
                    "SELECT * FROM paper_orders WHERE account_id = ? AND idempotency_key = ?",
                    (request.account_id, request.idempotency_key),
                ).fetchone()
                if existing is not None:
                    if existing["request_hash"] != request_hash:
                        raise PaperTradingError(
                            "idempotency_key was already used for a different order"
                        )
                    conn.commit()
                    return self._order_from_row(existing)
                position = conn.execute(
                    "SELECT * FROM paper_positions WHERE account_id = ? AND symbol = ? AND chain = ?",
                    (request.account_id, request.symbol, request.chain),
                ).fetchone()

                if request.side == "buy":
                    total_cost = notional + fee
                    if total_cost > account["cash"]:
                        raise PaperTradingError("insufficient paper cash for notional plus fee")
                    old_qty = float(position["quantity"]) if position else 0.0
                    old_cost = float(position["average_cost"]) if position else 0.0
                    new_qty = old_qty + request.quantity
                    new_avg = (old_qty * old_cost + total_cost) / new_qty
                    new_cash = max(0.0, float(account["cash"]) - total_cost)
                    realized_delta = 0.0
                else:
                    old_qty = float(position["quantity"]) if position else 0.0
                    if request.quantity > old_qty:
                        raise PaperTradingError("insufficient position quantity to sell")
                    old_cost = float(position["average_cost"]) if position else 0.0
                    new_qty = max(0.0, old_qty - request.quantity)
                    new_avg = old_cost if new_qty > 1e-9 else 0.0
                    proceeds = notional - fee
                    new_cash = float(account["cash"]) + proceeds
                    realized_delta = proceeds - old_cost * request.quantity

                order_id = uuid.uuid4().hex
                conn.execute(
                    """
                    INSERT INTO paper_orders(
                        order_id, account_id, idempotency_key, request_hash, symbol, chain,
                        side, quantity, reference_price, fill_price, notional, fee, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'filled')
                    """,
                    (
                        order_id, request.account_id, request.idempotency_key, request_hash,
                        request.symbol, request.chain, request.side, request.quantity,
                        request.reference_price, fill_price, notional, fee,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO paper_positions(account_id, symbol, chain, quantity, average_cost, mark_price)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(account_id, symbol, chain) DO UPDATE SET
                        quantity=excluded.quantity,
                        average_cost=excluded.average_cost,
                        mark_price=excluded.mark_price
                    """,
                    (
                        request.account_id, request.symbol, request.chain,
                        new_qty, new_avg, fill_price,
                    ),
                )
                conn.execute(
                    """
                    UPDATE paper_accounts
                    SET cash = ?, realized_pnl = realized_pnl + ?, total_fees = total_fees + ?
                    WHERE account_id = ?
                    """,
                    (new_cash, realized_delta, fee, request.account_id),
                )
                row = conn.execute(
                    "SELECT * FROM paper_orders WHERE order_id = ?", (order_id,)
                ).fetchone()
                conn.commit()
                return self._order_from_row(row)
            except Exception:
                conn.rollback()
                raise

    @staticmethod
    def _order_from_row(row: sqlite3.Row) -> PaperOrder:
        return PaperOrder(
            order_id=row["order_id"],
            account_id=row["account_id"],
            symbol=row["symbol"],
            chain=row["chain"],
            side=row["side"],
            quantity=row["quantity"],
            reference_price=row["reference_price"],
            fill_price=row["fill_price"],
            notional_usd=row["notional"],
            fee_usd=row["fee"],
            status=row["status"],
            idempotency_key=row["idempotency_key"],
            created_at=row["created_at"],
        )

    def list_orders(self, account_id: str, tenant_id: str = "local", limit: int = 100) -> list[PaperOrder]:
        if not 1 <= limit <= 1000:
            raise PaperTradingError("limit must be between 1 and 1000")
        with self._lock, self._connect() as conn:
            account = conn.execute(
                "SELECT 1 FROM paper_accounts WHERE account_id = ? AND tenant_id = ?", (account_id, tenant_id)
            ).fetchone()
            if account is None:
                raise PaperTradingError("paper account not found")
            rows = conn.execute(
                "SELECT * FROM paper_orders WHERE account_id = ? ORDER BY rowid DESC LIMIT ?",
                (account_id, limit),
            ).fetchall()
        return [self._order_from_row(row) for row in rows]

    def get_account(self, account_id: str, tenant_id: str = "local") -> PaperAccount:
        with self._lock, self._connect() as conn:
            account = conn.execute(
                "SELECT * FROM paper_accounts WHERE account_id = ? AND tenant_id = ?", (account_id, tenant_id)
            ).fetchone()
            if account is None:
                raise PaperTradingError("paper account not found")
            rows = conn.execute(
                "SELECT * FROM paper_positions WHERE account_id = ? ORDER BY symbol, chain",
                (account_id,),
            ).fetchall()

        positions: list[PaperPosition] = []
        unrealized = 0.0
        for row in rows:
            quantity = max(0.0, float(row["quantity"]))
            avg_cost = float(row["average_cost"])
            mark = float(row["mark_price"])
            market_value = quantity * mark
            pnl = quantity * (mark - avg_cost)
            unrealized += pnl
            positions.append(
                PaperPosition(
                    symbol=row["symbol"],
                    chain=row["chain"],
                    quantity=quantity,
                    average_cost_usd=round(avg_cost, 10),
                    mark_price_usd=round(mark, 10),
                    market_value_usd=round(market_value, 8),
                    unrealized_pnl_usd=round(pnl, 8),
                )
            )

        cash = float(account["cash"])
        return PaperAccount(
            account_id=account_id,
            initial_cash_usd=round(float(account["initial_cash"]), 8),
            cash_usd=round(cash, 8),
            realized_pnl_usd=round(float(account["realized_pnl"]), 8),
            unrealized_pnl_usd=round(unrealized, 8),
            equity_usd=round(cash + sum(p.market_value_usd for p in positions), 8),
            total_fees_usd=round(float(account["total_fees"]), 8),
            positions=positions,
        )
