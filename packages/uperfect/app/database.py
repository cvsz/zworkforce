"""Small SQLite helper used for local and test persistence."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator
from decimal import Decimal


# SQLite has no native Decimal binding; store currency as text so reads remain exact.
sqlite3.register_adapter(Decimal, str)


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def initialize(self, *, seed: bool = True) -> None:
        """Create the local schema and optionally load the safe merchant seed."""

        with self.transaction() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS products (
                  id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  size TEXT NOT NULL,
                  price_thb NUMERIC,
                  description TEXT NOT NULL DEFAULT '',
                  seller TEXT NOT NULL DEFAULT '',
                  merchant_provided INTEGER NOT NULL DEFAULT 1,
                  available INTEGER NOT NULL DEFAULT 1,
                  stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
                  usage TEXT NOT NULL DEFAULT '',
                  warning TEXT NOT NULL DEFAULT '',
                  allergen_warning TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS product_keywords (
                  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                  keyword TEXT NOT NULL COLLATE NOCASE,
                  category TEXT NOT NULL DEFAULT 'alias',
                  position INTEGER NOT NULL DEFAULT 0,
                  PRIMARY KEY(product_id, keyword)
                );

                CREATE TABLE IF NOT EXISTS ingredients (
                  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                  name TEXT NOT NULL,
                  benefit_copy TEXT NOT NULL,
                  position INTEGER NOT NULL,
                  PRIMARY KEY(product_id, name)
                );

                CREATE TABLE IF NOT EXISTS product_inci (
                  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                  name TEXT NOT NULL,
                  position INTEGER NOT NULL,
                  PRIMARY KEY(product_id, name)
                );

                CREATE TABLE IF NOT EXISTS promotions (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                  minimum_quantity INTEGER NOT NULL CHECK (minimum_quantity > 0),
                  bundle_price_thb NUMERIC NOT NULL CHECK (bundle_price_thb >= 0),
                  original_price_thb NUMERIC,
                  label TEXT NOT NULL,
                  shipping_free INTEGER NOT NULL DEFAULT 0,
                  UNIQUE(product_id, minimum_quantity)
                );

                CREATE TABLE IF NOT EXISTS product_sources (
                  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                  listing_id TEXT PRIMARY KEY,
                  source_url TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversations (
                  id TEXT PRIMARY KEY,
                  platform TEXT NOT NULL,
                  customer_id TEXT NOT NULL,
                  active_product_id TEXT REFERENCES products(id),
                  selected_quantity INTEGER,
                  current_step TEXT NOT NULL DEFAULT 'greeting',
                  human_takeover INTEGER NOT NULL DEFAULT 0,
                  takeover_until TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE(platform, customer_id)
                );

                CREATE TABLE IF NOT EXISTS messages (
                  id TEXT PRIMARY KEY,
                  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                  direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
                  text TEXT NOT NULL,
                  intent TEXT NOT NULL DEFAULT 'fallback',
                  automated INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS orders (
                  id TEXT PRIMARY KEY,
                  conversation_id TEXT REFERENCES conversations(id),
                  customer_name TEXT NOT NULL,
                  status TEXT NOT NULL CHECK (status IN ('draft','awaiting_payment','pending_review','confirmed','fulfilled','cancelled')),
                  total_thb NUMERIC NOT NULL CHECK (total_thb >= 0),
                  payment_reference TEXT,
                  address_json TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS order_items (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                  product_id TEXT NOT NULL REFERENCES products(id),
                  quantity INTEGER NOT NULL CHECK (quantity > 0),
                  unit_price_thb NUMERIC NOT NULL CHECK (unit_price_thb >= 0),
                  line_total_thb NUMERIC NOT NULL CHECK (line_total_thb >= 0)
                );

                CREATE TABLE IF NOT EXISTS inventory_reservations (
                  product_id TEXT PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
                  reserved INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0)
                );

                CREATE TABLE IF NOT EXISTS integrations (
                  provider TEXT PRIMARY KEY,
                  status TEXT NOT NULL CHECK (status IN ('unconfigured','configured','verified','degraded','disabled')),
                  webhook_path TEXT NOT NULL,
                  last_verified_at TEXT
                );

                CREATE TABLE IF NOT EXISTS workspace_settings (
                  key TEXT PRIMARY KEY,
                  value_json TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS webhook_receipts (
                  provider TEXT NOT NULL,
                  event_id TEXT NOT NULL,
                  message_id TEXT,
                  received_at TEXT NOT NULL,
                  PRIMARY KEY(provider, event_id)
                );

                CREATE TABLE IF NOT EXISTS notification_outbox (
                  id TEXT PRIMARY KEY,
                  event_type TEXT NOT NULL,
                  destination TEXT NOT NULL,
                  body TEXT NOT NULL,
                  status TEXT NOT NULL CHECK (status IN ('pending','sent','failed')),
                  attempts INTEGER NOT NULL DEFAULT 0,
                  last_error TEXT,
                  created_at TEXT NOT NULL,
                  sent_at TEXT,
                  locked_until TEXT,
                  locked_by TEXT,
                  next_attempt_at TEXT
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                  id TEXT PRIMARY KEY,
                  event_type TEXT NOT NULL,
                  entity_id TEXT,
                  actor TEXT NOT NULL,
                  details_json TEXT NOT NULL DEFAULT '{}',
                  created_at TEXT NOT NULL
                );
                """,
            )
            from app.migrations import apply_migrations

            apply_migrations(connection)
            if seed:
                from app.seed import seed_database

                seed_database(connection)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
