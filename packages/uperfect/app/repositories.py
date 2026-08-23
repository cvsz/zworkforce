"""SQLite persistence primitives; services keep business policy out of SQL."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.database import Database
from app.schemas import (
    Conversation,
    ConversationNotFound,
    Ingredient,
    IntegrationStatus,
    Order,
    OrderNotFound,
    Product,
    ProductNotFound,
    Promotion,
    decimal_value,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def timestamp(value: datetime | None = None) -> str:
    return (value or utcnow()).isoformat()


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


class Repository:
    def __init__(self, database: Database) -> None:
        self.database = database

    # Product catalogue -------------------------------------------------
    def list_products(self, query: str | None = None) -> list[Product]:
        with self.database.transaction() as connection:
            if query:
                rows = connection.execute(
                    "SELECT id FROM products WHERE name LIKE ? OR description LIKE ? ORDER BY name",
                    (f"%{query}%", f"%{query}%"),
                ).fetchall()
            else:
                rows = connection.execute("SELECT id FROM products ORDER BY name").fetchall()
            return [self._product(connection, row["id"]) for row in rows]

    def get_product(self, product_id: str) -> Product:
        with self.database.transaction() as connection:
            return self._product(connection, product_id)

    def get_product_optional(self, product_id: str | None) -> Product | None:
        if not product_id:
            return None
        try:
            return self.get_product(product_id)
        except ProductNotFound:
            return None

    def find_keyword_matches(self, text: str) -> list[Product]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT product_id, keyword
                FROM product_keywords
                WHERE instr(lower(?), lower(keyword)) > 0
                ORDER BY length(keyword) DESC
                """,
                (text,),
            ).fetchall()
            products: list[Product] = []
            seen: set[str] = set()
            for row in rows:
                if row["product_id"] in seen:
                    continue
                product = self._product(connection, row["product_id"])
                products.append(
                    Product(
                        **{**product.__dict__, "matched_alias": row["keyword"]},
                    )
                )
                seen.add(product.id)
            return products

    def save_product(self, product: Product) -> Product:
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO products(id, name, size, price_thb, description, seller,
                  merchant_provided, available, stock, usage, warning, allergen_warning)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  name=excluded.name, size=excluded.size, price_thb=excluded.price_thb,
                  description=excluded.description, seller=excluded.seller,
                  merchant_provided=excluded.merchant_provided, available=excluded.available,
                  stock=excluded.stock, usage=excluded.usage, warning=excluded.warning,
                  allergen_warning=excluded.allergen_warning
                """,
                (
                    product.id,
                    product.name,
                    product.size,
                    product.price_thb,
                    product.description,
                    product.seller,
                    int(product.merchant_provided),
                    int(product.available),
                    product.stock,
                    product.usage,
                    product.warning,
                    product.allergen_warning,
                ),
            )
            connection.execute("DELETE FROM product_keywords WHERE product_id = ?", (product.id,))
            connection.executemany(
                "INSERT INTO product_keywords(product_id, keyword, category, position) VALUES (?, ?, 'alias', ?)",
                [(product.id, alias, position) for position, alias in enumerate(product.aliases, 1)],
            )
            connection.execute("DELETE FROM ingredients WHERE product_id = ?", (product.id,))
            connection.executemany(
                "INSERT INTO ingredients(product_id, name, benefit_copy, position) VALUES (?, ?, ?, ?)",
                [(product.id, item.name, item.benefit_copy, item.position) for item in product.ingredients],
            )
        return self.get_product(product.id)

    def _product(self, connection: sqlite3.Connection, product_id: str) -> Product:
        row = connection.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if row is None:
            raise ProductNotFound(f"ไม่พบสินค้า {product_id}")
        keywords = tuple(
            item["keyword"]
            for item in connection.execute(
                "SELECT keyword FROM product_keywords WHERE product_id = ? ORDER BY position, keyword",
                (product_id,),
            ).fetchall()
        )
        ingredients = tuple(
            Ingredient(item["name"], item["benefit_copy"], item["position"])
            for item in connection.execute(
                "SELECT name, benefit_copy, position FROM ingredients WHERE product_id = ? ORDER BY position",
                (product_id,),
            ).fetchall()
        )
        promotions = tuple(
            Promotion(
                minimum_quantity=item["minimum_quantity"],
                bundle_price_thb=decimal_value(item["bundle_price_thb"]) or Decimal("0"),
                label=item["label"],
                original_price_thb=decimal_value(item["original_price_thb"]),
                shipping_free=bool(item["shipping_free"]),
            )
            for item in connection.execute(
                "SELECT minimum_quantity, bundle_price_thb, original_price_thb, label, shipping_free "
                "FROM promotions WHERE product_id = ? ORDER BY minimum_quantity DESC",
                (product_id,),
            ).fetchall()
        )
        sources = connection.execute(
            "SELECT listing_id, source_url FROM product_sources WHERE product_id = ? ORDER BY listing_id",
            (product_id,),
        ).fetchall()
        inci = tuple(
            item["name"]
            for item in connection.execute(
                "SELECT name FROM product_inci WHERE product_id = ? ORDER BY position",
                (product_id,),
            ).fetchall()
        )
        return Product(
            id=row["id"],
            name=row["name"],
            size=row["size"],
            price_thb=decimal_value(row["price_thb"]),
            aliases=keywords,
            ingredients=ingredients,
            promotions=promotions,
            description=row["description"],
            seller=row["seller"],
            source_urls=tuple(item["source_url"] for item in sources),
            source_listing_ids=tuple(item["listing_id"] for item in sources),
            merchant_provided=bool(row["merchant_provided"]),
            available=bool(row["available"]),
            stock=row["stock"],
            allergen_warning=row["allergen_warning"],
            usage=row["usage"],
            warning=row["warning"],
            inci=inci,
        )

    # Conversations and messages --------------------------------------
    def get_or_create_conversation(self, platform: str, customer_id: str) -> Conversation:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT id FROM conversations WHERE platform = ? AND customer_id = ?",
                (platform, customer_id),
            ).fetchone()
            if row is None:
                now = timestamp()
                conversation_id = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO conversations(id, platform, customer_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (conversation_id, platform, customer_id, now, now),
                )
                row = {"id": conversation_id}
            return self._conversation(connection, row["id"])

    def get_conversation(self, conversation_id: str) -> Conversation:
        with self.database.transaction() as connection:
            return self._conversation(connection, conversation_id)

    def list_conversations(self) -> list[Conversation]:
        with self.database.transaction() as connection:
            rows = connection.execute("SELECT id FROM conversations ORDER BY updated_at DESC").fetchall()
            return [self._conversation(connection, row["id"]) for row in rows]

    def update_conversation(
        self,
        conversation_id: str,
        *,
        active_product_id: str | None = None,
        selected_quantity: int | None = None,
        current_step: str | None = None,
        human_takeover: bool | None = None,
        takeover_until: datetime | None = None,
    ) -> Conversation:
        with self.database.transaction() as connection:
            current = self._conversation(connection, conversation_id)
            connection.execute(
                """
                UPDATE conversations SET
                  active_product_id = ?, selected_quantity = ?, current_step = ?,
                  human_takeover = ?, takeover_until = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    active_product_id if active_product_id is not None else current.active_product_id,
                    selected_quantity if selected_quantity is not None else current.selected_quantity,
                    current_step if current_step is not None else current.current_step,
                    int(human_takeover if human_takeover is not None else current.human_takeover),
                    timestamp(takeover_until) if takeover_until else None,
                    timestamp(),
                    conversation_id,
                ),
            )
            return self._conversation(connection, conversation_id)

    def append_message(
        self,
        conversation_id: str,
        direction: str,
        text: str,
        intent: str,
        automated: bool,
    ) -> str:
        message_id = str(uuid.uuid4())
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO messages(id, conversation_id, direction, text, intent, automated, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (message_id, conversation_id, direction, text, intent, int(automated), timestamp()),
            )
            connection.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (timestamp(), conversation_id))
        return message_id

    def list_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT id, direction, text, intent, automated, created_at FROM messages "
                "WHERE conversation_id = ? ORDER BY created_at",
                (conversation_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def _conversation(self, connection: sqlite3.Connection, conversation_id: str) -> Conversation:
        row = connection.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if row is None:
            raise ConversationNotFound(f"ไม่พบบทสนทนา {conversation_id}")
        return Conversation(
            id=row["id"],
            platform=row["platform"],
            customer_id=row["customer_id"],
            active_product_id=row["active_product_id"],
            selected_quantity=row["selected_quantity"],
            current_step=row["current_step"],
            human_takeover=bool(row["human_takeover"]),
            takeover_until=parse_timestamp(row["takeover_until"]) if row["takeover_until"] else None,
            created_at=parse_timestamp(row["created_at"]),
            updated_at=parse_timestamp(row["updated_at"]),
        )

    # Orders and inventory ---------------------------------------------
    def reserve_inventory(self, product_id: str, quantity: int) -> None:
        with self.database.transaction() as connection:
            product = connection.execute("SELECT stock FROM products WHERE id = ?", (product_id,)).fetchone()
            if product is None:
                raise ProductNotFound(f"ไม่พบสินค้า {product_id}")
            reservation = connection.execute(
                "SELECT reserved FROM inventory_reservations WHERE product_id = ?", (product_id,)
            ).fetchone()
            reserved = reservation["reserved"] if reservation else 0
            if product["stock"] - reserved < quantity:
                raise ValueError("OUT_OF_STOCK: สินค้ามีจำนวนไม่พอ")
            connection.execute(
                """
                INSERT INTO inventory_reservations(product_id, reserved) VALUES (?, ?)
                ON CONFLICT(product_id) DO UPDATE SET reserved = inventory_reservations.reserved + excluded.reserved
                """,
                (product_id, quantity),
            )

    def create_order(
        self,
        *,
        customer_name: str,
        status: str,
        total_thb: Decimal,
        product_id: str,
        quantity: int,
        unit_price_thb: Decimal,
        conversation_id: str | None,
    ) -> Order:
        order_id = str(uuid.uuid4())
        now = timestamp()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO orders(id, conversation_id, customer_name, status, total_thb, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (order_id, conversation_id, customer_name, status, total_thb, now, now),
            )
            connection.execute(
                """
                INSERT INTO order_items(order_id, product_id, quantity, unit_price_thb, line_total_thb)
                VALUES (?, ?, ?, ?, ?)
                """,
                (order_id, product_id, quantity, unit_price_thb, total_thb),
            )
        return self.get_order(order_id)

    def get_order(self, order_id: str) -> Order:
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT o.*, i.product_id, i.quantity
                FROM orders o JOIN order_items i ON i.order_id = o.id
                WHERE o.id = ?
                """,
                (order_id,),
            ).fetchone()
            if row is None:
                raise OrderNotFound(f"ไม่พบคำสั่งซื้อ {order_id}")
            return self._order(row)

    def list_orders(self) -> list[Order]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT o.*, i.product_id, i.quantity
                FROM orders o JOIN order_items i ON i.order_id = o.id
                ORDER BY o.created_at DESC
                """,
            ).fetchall()
            return [self._order(row) for row in rows]

    def update_order_payment(self, order_id: str, reference: str) -> Order:
        with self.database.transaction() as connection:
            if connection.execute("SELECT id FROM orders WHERE id = ?", (order_id,)).fetchone() is None:
                raise OrderNotFound(f"ไม่พบคำสั่งซื้อ {order_id}")
            connection.execute(
                "UPDATE orders SET payment_reference = ?, status = 'pending_review', updated_at = ? WHERE id = ?",
                (reference, timestamp(), order_id),
            )
        return self.get_order(order_id)

    def update_order_status(self, order_id: str, status: str) -> Order:
        with self.database.transaction() as connection:
            if connection.execute("SELECT id FROM orders WHERE id = ?", (order_id,)).fetchone() is None:
                raise OrderNotFound(f"ไม่พบคำสั่งซื้อ {order_id}")
            connection.execute("UPDATE orders SET status = ?, updated_at = ? WHERE id = ?", (status, timestamp(), order_id))
        return self.get_order(order_id)

    def _order(self, row: sqlite3.Row) -> Order:
        return Order(
            id=row["id"],
            customer_name=row["customer_name"],
            status=row["status"],
            total_thb=decimal_value(row["total_thb"]) or Decimal("0"),
            product_id=row["product_id"],
            quantity=row["quantity"],
            payment_reference=row["payment_reference"],
            conversation_id=row["conversation_id"],
            created_at=parse_timestamp(row["created_at"]),
            updated_at=parse_timestamp(row["updated_at"]),
        )

    # Integrations and notifications ----------------------------------
    def claim_webhook(self, provider: str, event_id: str, message_id: str | None = None) -> bool:
        with self.database.transaction() as connection:
            try:
                connection.execute(
                    "INSERT INTO webhook_receipts(provider, event_id, message_id, received_at) VALUES (?, ?, ?, ?)",
                    (provider, event_id, message_id, timestamp()),
                )
            except sqlite3.IntegrityError:
                return False
            return True

    def update_integration_status(self, provider: str, status: str) -> None:
        with self.database.transaction() as connection:
            connection.execute("UPDATE integrations SET status = ? WHERE provider = ?", (status, provider))

    # Workspace settings -----------------------------------------------
    def load_workspace_settings(self) -> tuple[dict[str, Any], str | None]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT key, value_json, updated_at FROM workspace_settings"
            ).fetchall()
            values: dict[str, Any] = {}
            updated_at: str | None = None
            for row in rows:
                try:
                    values[row["key"]] = json.loads(row["value_json"])
                except (TypeError, json.JSONDecodeError):
                    continue
                updated_at = max(updated_at or row["updated_at"], row["updated_at"])
            return values, updated_at

    def save_workspace_settings(self, values: dict[str, Any]) -> None:
        now = timestamp()
        with self.database.transaction() as connection:
            connection.executemany(
                """
                INSERT INTO workspace_settings(key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  value_json=excluded.value_json, updated_at=excluded.updated_at
                """,
                [(key, json.dumps(value, ensure_ascii=False), now) for key, value in values.items()],
            )

    def list_integration_statuses(self) -> list[IntegrationStatus]:
        with self.database.transaction() as connection:
            rows = connection.execute("SELECT * FROM integrations ORDER BY provider").fetchall()
            return [
                IntegrationStatus(
                    provider=row["provider"],
                    label={"local_ai": "Ollama local AI"}.get(
                        row["provider"], row["provider"].replace("_", " ").title()
                    ),
                    status=row["status"],
                    webhook_path=row["webhook_path"],
                    setup_note=(
                        "ใช้ Ollama บน 192.168.74.130 โดยไม่ส่งข้อมูลออกนอกเครื่อง"
                        if row["provider"] == "local_ai"
                        else "ตั้งค่าบัญชีและตรวจสอบ webhook ที่ฝั่ง server ก่อนใช้งาน"
                    ),
                )
                for row in rows
            ]

    def add_notification(self, event_type: str, destination: str, body: str) -> str:
        notification_id = str(uuid.uuid4())
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO notification_outbox(id, event_type, destination, body, status, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
                """,
                (notification_id, event_type, destination, body, timestamp()),
            )
        return notification_id

    def claim_next_notification(self, worker_id: str, lease_seconds: int = 60) -> dict[str, Any] | None:
        if not worker_id.strip():
            raise ValueError("worker_id must not be empty")
        now = utcnow()
        now_value = timestamp(now)
        lease_until = timestamp(now + timedelta(seconds=max(1, lease_seconds)))
        with self.database.transaction() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT id
                FROM notification_outbox
                WHERE status IN ('pending', 'failed')
                  AND (locked_until IS NULL OR locked_until <= ?)
                  AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                ORDER BY created_at
                LIMIT 1
                """,
                (now_value, now_value),
            ).fetchone()
            if row is None:
                return None
            updated = connection.execute(
                """
                UPDATE notification_outbox
                SET locked_until = ?, locked_by = ?
                WHERE id = ?
                  AND status IN ('pending', 'failed')
                  AND (locked_until IS NULL OR locked_until <= ?)
                  AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                """,
                (lease_until, worker_id, row["id"], now_value, now_value),
            )
            if updated.rowcount != 1:
                return None
            claimed = connection.execute(
                "SELECT * FROM notification_outbox WHERE id = ?",
                (row["id"],),
            ).fetchone()
            return dict(claimed) if claimed else None

    def pending_notifications(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.database.transaction() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM notification_outbox WHERE status IN ('pending','failed') "
                    "ORDER BY created_at LIMIT ?",
                    (limit,),
                ).fetchall()
            ]

    def mark_notification_sent(self, notification_id: str) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE notification_outbox SET status='sent', sent_at=?, attempts=attempts+1, "
                "locked_until=NULL, locked_by=NULL, next_attempt_at=NULL WHERE id = ?",
                (timestamp(), notification_id),
            )

    def record_notification_failure(self, notification_id: str, error: str) -> None:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT attempts FROM notification_outbox WHERE id = ?",
                (notification_id,),
            ).fetchone()
            if row is None:
                return
            attempts = int(row["attempts"]) + 1
            delay_seconds = min(300, 2 ** min(attempts, 8))
            next_attempt = timestamp(utcnow() + timedelta(seconds=delay_seconds))
            connection.execute(
                "UPDATE notification_outbox SET status='failed', attempts=?, last_error=?, "
                "locked_until=NULL, locked_by=NULL, next_attempt_at=? WHERE id = ?",
                (attempts, error[:240], next_attempt, notification_id),
            )

    def pending_notification_count(self) -> int:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT count(*) AS count FROM notification_outbox WHERE status IN ('pending','failed')",
            ).fetchone()
            return int(row["count"])

    def audit(self, event_type: str, entity_id: str | None, actor: str, details: dict[str, Any] | None = None) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO audit_events(id, event_type, entity_id, actor, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), event_type, entity_id, actor, json.dumps(details or {}, ensure_ascii=False), timestamp()),
            )
