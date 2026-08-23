"""Order creation, promotion pricing, inventory reservation, and review gates."""

from __future__ import annotations

from decimal import Decimal

from app.repositories import Repository
from app.schemas import DomainError, InvalidTransition, Order, Product
from app.services.catalog import CatalogService


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"awaiting_payment", "cancelled"},
    "awaiting_payment": {"pending_review", "cancelled"},
    "pending_review": {"confirmed", "cancelled"},
    "confirmed": {"fulfilled", "cancelled"},
    "fulfilled": set(),
    "cancelled": set(),
}


class OrderService:
    def __init__(self, repository: Repository, catalog: CatalogService, notifications=None, *, line_destination: str | None = None) -> None:
        self.repository = repository
        self.catalog = catalog
        self.notifications = notifications
        self.line_destination = line_destination or "line:pending-configuration"

    def create_draft(
        self,
        *,
        product_id: str,
        quantity: int,
        customer_name: str,
        conversation_id: str | None = None,
    ) -> Order:
        if quantity <= 0 or quantity > 100:
            raise DomainError("จำนวนสินค้าต้องอยู่ระหว่าง 1 ถึง 100", code="INVALID_QUANTITY")
        if not customer_name.strip():
            raise DomainError("ต้องระบุชื่อลูกค้า", code="CUSTOMER_NAME_REQUIRED")
        product = self.catalog.get(product_id)
        if not product.available:
            raise DomainError("สินค้านี้ไม่พร้อมขาย", code="PRODUCT_UNAVAILABLE")
        if product.price_thb is None:
            raise DomainError("PRICE_UNAVAILABLE: สินค้านี้ยังไม่มีราคาที่ยืนยัน", code="PRICE_UNAVAILABLE")

        total = self._calculate_total(product, quantity)
        self.repository.reserve_inventory(product.id, quantity)
        order = self.repository.create_order(
            customer_name=customer_name.strip(),
            status="awaiting_payment",
            total_thb=total,
            product_id=product.id,
            quantity=quantity,
            unit_price_thb=product.price_thb,
            conversation_id=conversation_id,
        )
        self.repository.audit("order_created", order.id, "autobot", {"total_thb": str(total)})
        return order

    def submit_payment_evidence(self, order_id: str, reference: str) -> Order:
        reference = reference.strip()
        if not reference:
            raise DomainError("ต้องระบุหลักฐานการชำระเงิน", code="PAYMENT_REFERENCE_REQUIRED")
        order = self.repository.get_order(order_id)
        if order.status != "awaiting_payment":
            raise InvalidTransition(order.status, "pending_review")
        updated = self.repository.update_order_payment(order_id, reference)
        self.repository.audit("payment_evidence_submitted", order_id, "customer", {})
        return updated

    def transition(self, order_id: str, target: str, actor: str) -> Order:
        order = self.repository.get_order(order_id)
        if target not in ALLOWED_TRANSITIONS.get(order.status, set()):
            raise InvalidTransition(order.status, target)
        updated = self.repository.update_order_status(order_id, target)
        self.repository.audit("order_status_changed", order_id, actor or "admin", {"target": target})
        if target == "confirmed" and self.notifications:
            self.notifications.enqueue(
                self.line_destination,
                f"U.Perfect order {order.id} confirmed: {order.total_thb.normalize()} THB",
                event_type="order_confirmed",
            )
        return updated

    def list_orders(self) -> list[Order]:
        return self.repository.list_orders()

    @staticmethod
    def _calculate_total(product: Product, quantity: int) -> Decimal:
        base_price = product.price_thb
        if base_price is None:
            raise DomainError("PRICE_UNAVAILABLE: สินค้านี้ยังไม่มีราคาที่ยืนยัน", code="PRICE_UNAVAILABLE")
        applicable = max(
            (promotion for promotion in product.promotions if quantity >= promotion.minimum_quantity),
            key=lambda promotion: promotion.minimum_quantity,
            default=None,
        )
        if applicable is None:
            return (base_price * quantity).quantize(Decimal("0.01"))
        remainder = quantity - applicable.minimum_quantity
        return (applicable.bundle_price_thb + base_price * remainder).quantize(Decimal("0.01"))
