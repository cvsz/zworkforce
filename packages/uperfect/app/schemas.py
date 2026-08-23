"""Domain values shared by persistence, services, and the HTTP layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal


class DomainError(ValueError):
    """A safe, user-facing domain failure with a stable API code."""

    code = "DOMAIN_ERROR"
    http_status = 400

    def __init__(self, message: str, *, code: str | None = None, http_status: int | None = None) -> None:
        super().__init__(message)
        self.public_message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status


class ProductNotFound(DomainError):
    code = "PRODUCT_NOT_FOUND"
    http_status = 404


class ConversationNotFound(DomainError):
    code = "CONVERSATION_NOT_FOUND"
    http_status = 404


class OrderNotFound(DomainError):
    code = "ORDER_NOT_FOUND"
    http_status = 404


class InvalidTransition(DomainError):
    code = "INVALID_ORDER_TRANSITION"
    http_status = 409

    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            f"ไม่สามารถเปลี่ยนสถานะจาก {current} เป็น {target} ได้",
        )
        self.current = current
        self.target = target


class IntegrationError(DomainError):
    code = "INTEGRATION_ERROR"
    http_status = 400


@dataclass(frozen=True)
class Ingredient:
    name: str
    benefit_copy: str
    position: int


@dataclass(frozen=True)
class Promotion:
    minimum_quantity: int
    bundle_price_thb: Decimal
    label: str
    original_price_thb: Decimal | None = None
    shipping_free: bool = False


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    size: str
    price_thb: Decimal | None
    aliases: tuple[str, ...] = ()
    ingredients: tuple[Ingredient, ...] = ()
    promotions: tuple[Promotion, ...] = ()
    description: str = ""
    seller: str = ""
    source_urls: tuple[str, ...] = ()
    source_listing_ids: tuple[str, ...] = ()
    merchant_provided: bool = True
    available: bool = True
    stock: int = 0
    allergen_warning: str = ""
    usage: str = ""
    warning: str = ""
    inci: tuple[str, ...] = ()
    matched_alias: str = field(default="", compare=False)


@dataclass(frozen=True)
class InboundMessage:
    platform: str
    customer_id: str
    text: str
    conversation_id: str | None = None


@dataclass(frozen=True)
class Conversation:
    id: str
    platform: str
    customer_id: str
    active_product_id: str | None
    selected_quantity: int | None
    current_step: str
    human_takeover: bool
    takeover_until: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AutomationResult:
    conversation: Conversation
    reply: str | None
    intent: str
    automated: bool
    active_product_id: str | None


OrderStatus = Literal[
    "draft",
    "awaiting_payment",
    "pending_review",
    "confirmed",
    "fulfilled",
    "cancelled",
]


@dataclass(frozen=True)
class Order:
    id: str
    customer_name: str
    status: OrderStatus
    total_thb: Decimal
    product_id: str
    quantity: int
    payment_reference: str | None
    conversation_id: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class IntegrationStatus:
    provider: str
    label: str
    status: str
    webhook_path: str
    setup_note: str


@dataclass(frozen=True)
class WebhookEvent:
    provider: str
    event_id: str
    customer_id: str
    text: str
    verified: bool = False


@dataclass(frozen=True)
class WebhookReceipt:
    accepted: bool
    duplicate: bool
    message_id: str | None


@dataclass(frozen=True)
class DeliverySummary:
    sent: int
    failed: int
    remaining: int


def decimal_value(value: Decimal | int | float | str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value)).quantize(Decimal("0.01"))


def decimal_json(value: Decimal | None) -> int | float | None:
    """Return a browser-friendly number without exposing Decimal internals."""

    if value is None:
        return None
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def parse_json_object(value: str | None) -> dict[str, Any]:
    import json

    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
