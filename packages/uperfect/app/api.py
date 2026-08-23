"""HTTP transport for the local U.Perfect admin and webhook APIs."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.schemas import InboundMessage, IntegrationError, Product, WebhookEvent, decimal_json
from app.services.sales_assets import public_sales_assets


class ProductPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    size: str = Field(default="", max_length=100)
    price_thb: Decimal | None = Field(default=None, ge=0)
    description: str = Field(default="", max_length=4000)
    seller: str = Field(default="", max_length=255)
    aliases: list[str] = Field(default_factory=list, max_length=100)
    available: bool = True
    stock: int = Field(default=0, ge=0, le=1_000_000)
    usage: str = Field(default="", max_length=1000)
    warning: str = Field(default="", max_length=1000)
    allergen_warning: str = Field(default="", max_length=1000)


class MessagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: str = Field(min_length=1, max_length=40)
    customer_id: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None


class TakeoverPayload(BaseModel):
    enabled: bool


class OrderPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=2, max_length=80)
    quantity: int = Field(ge=1, le=100)
    customer_name: str = Field(min_length=1, max_length=255)
    conversation_id: str | None = None


class PaymentPayload(BaseModel):
    reference: str = Field(min_length=1, max_length=255)


class TransitionPayload(BaseModel):
    target: str = Field(min_length=1, max_length=40)
    actor: str = Field(default="admin", min_length=1, max_length=80)


class WorkspaceSettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_name: str | None = Field(default=None, min_length=1, max_length=120)
    store_handle: str | None = Field(default=None, min_length=1, max_length=120)
    timezone: Literal["Asia/Bangkok", "Asia/Singapore", "UTC"] | None = None
    default_language: Literal["th", "en"] | None = None
    assistant_tone: Literal["warm", "formal", "concise"] | None = None
    autobot_enabled: bool | None = None
    human_takeover_timeout_minutes: int | None = Field(default=None, ge=1, le=1440)
    n8n_auto_post_enabled: bool | None = None
    n8n_comment_reply_enabled: bool | None = None
    line_notifications_enabled: bool | None = None
    payment_review_alerts_enabled: bool | None = None


router = APIRouter(prefix="/api")


INTEGRATION_COPY = {
    "facebook": {
        "label_th": "Facebook",
        "label_en": "Facebook",
        "setup_note_th": "ตั้งค่าบัญชีและตรวจสอบ webhook ที่ฝั่ง server ก่อนใช้งาน",
        "setup_note_en": "Configure the account and verify the webhook server-side before use.",
    },
    "tiktok": {
        "label_th": "TikTok Shop",
        "label_en": "TikTok Shop",
        "setup_note_th": "ตั้งค่า Partner Center และตรวจสอบ webhook ที่ฝั่ง server ก่อนใช้งาน",
        "setup_note_en": "Configure Partner Center and verify the webhook server-side before use.",
    },
    "shopee": {
        "label_th": "Shopee",
        "label_en": "Shopee",
        "setup_note_th": "ตั้งค่า Open Platform และตรวจสอบ signature ที่ฝั่ง server ก่อนใช้งาน",
        "setup_note_en": "Configure Open Platform and verify signatures server-side before use.",
    },
    "line": {
        "label_th": "LINE",
        "label_en": "LINE",
        "setup_note_th": "ตั้งค่า channel ฝั่ง server; release นี้ใช้เป็น notification outbox",
        "setup_note_en": "Configure the channel server-side; this release uses the notification outbox.",
    },
    "n8n": {
        "label_th": "n8n",
        "label_en": "n8n",
        "setup_note_th": "ตั้งค่า workflow และตรวจ webhook ที่ฝั่ง server ก่อนใช้งาน",
        "setup_note_en": "Configure the workflow and verify its webhook server-side before use.",
    },
    "gemini": {
        "label_th": "Gemini",
        "label_en": "Gemini",
        "setup_note_th": "ยังไม่เปิดใช้ใน local-only release",
        "setup_note_en": "Not enabled in the local-only release.",
    },
    "local_ai": {
        "label_th": "Ollama local AI",
        "label_en": "Ollama local AI",
        "setup_note_th": "ใช้ Ollama บน 192.168.74.130 โดยไม่ส่งข้อมูลออกนอกเครื่อง",
        "setup_note_en": "Uses Ollama on 192.168.74.130 without sending data outside the LAN.",
    },
}


def _services(request: Request):
    return request.app.state.services


def _product(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "name": product.name,
        "size": product.size,
        "price_thb": decimal_json(product.price_thb),
        "description": product.description,
        "seller": product.seller,
        "aliases": list(product.aliases),
        "ingredients": [
            {"name": item.name, "benefit_copy": item.benefit_copy, "position": item.position}
            for item in product.ingredients
        ],
        "promotions": [
            {
                "minimum_quantity": item.minimum_quantity,
                "bundle_price_thb": decimal_json(item.bundle_price_thb),
                "original_price_thb": decimal_json(item.original_price_thb),
                "label": item.label,
                "shipping_free": item.shipping_free,
            }
            for item in product.promotions
        ],
        "source_urls": list(product.source_urls),
        "source_listing_ids": list(product.source_listing_ids),
        "merchant_provided": product.merchant_provided,
        "available": product.available,
        "stock": product.stock,
        "usage": product.usage,
        "warning": product.warning,
        "allergen_warning": product.allergen_warning,
        "inci": list(product.inci),
        "price_note": "merchant brief; verify before live checkout" if product.price_thb is not None else "price not supplied",
    }


def _conversation(conversation) -> dict[str, Any]:
    return {
        "id": conversation.id,
        "platform": conversation.platform,
        "customer_id": conversation.customer_id,
        "active_product_id": conversation.active_product_id,
        "selected_quantity": conversation.selected_quantity,
        "current_step": conversation.current_step,
        "human_takeover": conversation.human_takeover,
        "takeover_until": conversation.takeover_until.isoformat() if conversation.takeover_until else None,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }


def _order(order) -> dict[str, Any]:
    return {
        "id": order.id,
        "customer_name": order.customer_name,
        "status": order.status,
        "total_thb": decimal_json(order.total_thb),
        "product_id": order.product_id,
        "quantity": order.quantity,
        "payment_reference": order.payment_reference,
        "conversation_id": order.conversation_id,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "brand": "U.Perfect"}


@router.get("/dashboard")
def dashboard(request: Request) -> dict[str, Any]:
    services = _services(request)
    products = services.catalog.list_products()
    conversations = services.conversations.repository.list_conversations()
    orders = services.orders.list_orders()
    return {
        "brand": "U.Perfect",
        "products": len(products),
        "conversations": len(conversations),
        "orders": len(orders),
        "pending_review": sum(order.status == "pending_review" for order in orders),
        "pending_notifications": services.notifications.pending_count(),
        "integrations": [item.__dict__ for item in services.integrations.statuses()],
    }


@router.get("/products")
def list_products(request: Request, q: str | None = Query(default=None, max_length=120)) -> dict[str, Any]:
    return {"items": [_product(item) for item in _services(request).catalog.list_products(q)]}


@router.post("/products", status_code=201)
def save_product(payload: ProductPayload, request: Request) -> dict[str, Any]:
    product = Product(
        id=payload.id.strip(),
        name=payload.name.strip(),
        size=payload.size.strip(),
        price_thb=payload.price_thb,
        description=payload.description.strip(),
        seller=payload.seller.strip(),
        aliases=tuple(dict.fromkeys(item.strip() for item in payload.aliases if item.strip())),
        available=payload.available,
        stock=payload.stock,
        usage=payload.usage.strip(),
        warning=payload.warning.strip(),
        allergen_warning=payload.allergen_warning.strip(),
    )
    return _product(_services(request).catalog.save(product))


@router.get("/products/{product_id}")
def get_product(product_id: str, request: Request) -> dict[str, Any]:
    return _product(_services(request).catalog.get(product_id))


@router.get("/conversations")
def list_conversations(request: Request) -> dict[str, Any]:
    services = _services(request)
    items = []
    for item in services.conversations.repository.list_conversations():
        value = _conversation(item)
        value["messages"] = services.conversations.messages(item.id)
        items.append(value)
    return {"items": items}


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, request: Request) -> dict[str, Any]:
    services = _services(request)
    value = _conversation(services.conversations.get_context(conversation_id))
    value["messages"] = services.conversations.messages(conversation_id)
    return value


@router.post("/conversations/{conversation_id}/takeover")
def set_takeover(conversation_id: str, payload: TakeoverPayload, request: Request) -> dict[str, Any]:
    return _conversation(_services(request).conversations.set_takeover(conversation_id, payload.enabled))


@router.post("/messages")
def receive_message(payload: MessagePayload, request: Request) -> dict[str, Any]:
    result = _services(request).conversations.receive(
        InboundMessage(payload.platform, payload.customer_id, payload.text, payload.conversation_id)
    )
    return {
        "conversation": _conversation(result.conversation),
        "reply": result.reply,
        "intent": result.intent,
        "automated": result.automated,
        "active_product_id": result.active_product_id,
    }


@router.get("/orders")
def list_orders(request: Request) -> dict[str, Any]:
    return {"items": [_order(item) for item in _services(request).orders.list_orders()]}


@router.post("/orders", status_code=201)
def create_order(payload: OrderPayload, request: Request) -> dict[str, Any]:
    return _order(
        _services(request).orders.create_draft(
            product_id=payload.product_id,
            quantity=payload.quantity,
            customer_name=payload.customer_name,
            conversation_id=payload.conversation_id,
        )
    )


@router.post("/orders/{order_id}/payment-evidence")
def submit_payment(order_id: str, payload: PaymentPayload, request: Request) -> dict[str, Any]:
    return _order(_services(request).orders.submit_payment_evidence(order_id, payload.reference))


@router.post("/orders/{order_id}/transition")
def transition_order(order_id: str, payload: TransitionPayload, request: Request) -> dict[str, Any]:
    return _order(_services(request).orders.transition(order_id, payload.target, payload.actor))


@router.get("/integrations")
def integrations(request: Request) -> dict[str, Any]:
    # Deliberately omit credential names and values from browser responses.
    return {
        "items": [
            {
                "provider": item.provider,
                "label": item.label,
                **INTEGRATION_COPY.get(item.provider, {}),
                "status": item.status,
                "webhook_path": item.webhook_path,
                "setup_note": item.setup_note,
            }
            for item in _services(request).integrations.statuses()
        ]
    }


@router.get("/sales-assets")
def sales_assets() -> dict[str, Any]:
    """Expose only validated, local sales-response content to the dashboard."""

    return public_sales_assets()


@router.get("/integration-guides")
def integration_guides() -> dict[str, Any]:
    """Point operators to bilingual setup guides without exposing credentials."""

    return {
        "items": [
            {
                "provider": "facebook",
                "name": "Facebook Messenger / Meta",
                "th": "สร้าง Meta App, Page access token และตรวจสอบ Messenger webhook",
                "en": "Create the Meta app, Page access token, and verify the Messenger webhook.",
                "guide_th": "/guides/API_ONBOARDING_TH.md#facebook-messenger-meta",
                "guide_en": "/guides/API_ONBOARDING_EN.md#facebook-messenger-meta",
                "approval_th": "/guides/PROVIDER-APPROVAL-FORM_TH.md#facebook-messenger-meta",
                "approval_en": "/guides/PROVIDER-APPROVAL-FORM_EN.md#facebook-messenger-meta",
            },
            {
                "provider": "tiktok",
                "name": "TikTok Shop Open Platform",
                "th": "สร้างแอปใน Partner Center, authorize shop และตั้งค่า HTTPS webhook",
                "en": "Create a Partner Center app, authorize the shop, and configure an HTTPS webhook.",
                "guide_th": "/guides/API_ONBOARDING_TH.md#tiktok-shop-open-platform",
                "guide_en": "/guides/API_ONBOARDING_EN.md#tiktok-shop-open-platform",
                "approval_th": "/guides/PROVIDER-APPROVAL-FORM_TH.md#tiktok-shop-open-platform",
                "approval_en": "/guides/PROVIDER-APPROVAL-FORM_EN.md#tiktok-shop-open-platform",
            },
            {
                "provider": "shopee",
                "name": "Shopee Open Platform",
                "th": "สร้าง Open Platform app, authorize ร้านค้า และเก็บ Partner ID/Key ที่ server",
                "en": "Create the Open Platform app, authorize the shop, and keep Partner ID/Key server-side.",
                "guide_th": "/guides/API_ONBOARDING_TH.md#shopee-open-platform",
                "guide_en": "/guides/API_ONBOARDING_EN.md#shopee-open-platform",
                "approval_th": "/guides/PROVIDER-APPROVAL-FORM_TH.md#shopee-open-platform",
                "approval_en": "/guides/PROVIDER-APPROVAL-FORM_EN.md#shopee-open-platform",
            },
            {
                "provider": "line",
                "name": "LINE Messaging API",
                "th": "สร้าง Messaging API channel, ออก channel access token และตั้ง webhook ตามขอบเขตที่เปิดใช้",
                "en": "Create a Messaging API channel, issue a channel access token, and configure a webhook for the enabled scope.",
                "guide_th": "/guides/API_ONBOARDING_TH.md#line-messaging-api",
                "guide_en": "/guides/API_ONBOARDING_EN.md#line-messaging-api",
                "approval_th": "/guides/PROVIDER-APPROVAL-FORM_TH.md#line-messaging-api",
                "approval_en": "/guides/PROVIDER-APPROVAL-FORM_EN.md#line-messaging-api",
            },
        ]
    }


@router.get("/settings")
def get_settings(request: Request) -> dict[str, Any]:
    return _services(request).workspace_settings.get()


@router.patch("/settings")
def update_settings(payload: WorkspaceSettingsPayload, request: Request) -> dict[str, Any]:
    values = payload.model_dump(exclude_unset=True, exclude_none=True)
    return _services(request).workspace_settings.update(values)


@router.get("/notifications")
def notifications(request: Request) -> dict[str, Any]:
    items = _services(request).notifications.list_pending()
    return {
        "pending": len(items),
        "items": [
            {
                "id": item["id"],
                "event_type": item["event_type"],
                "status": item["status"],
                "attempts": item["attempts"],
                "last_error": item["last_error"],
                "created_at": item["created_at"],
            }
            for item in items
        ],
    }


@router.get("/skills")
def skills() -> dict[str, Any]:
    return {
        "items": [
            {"id": "product-memory", "name": "Product Memory", "status": "ready", "description": "ค้น alias และข้อเท็จจริงจาก catalog", "th": "ค้น alias และข้อเท็จจริงจาก catalog", "en": "Find aliases and product facts from the catalog."},
            {"id": "safe-closing", "name": "Safe Closing", "status": "ready", "description": "สรุปยอดโดยไม่ข้าม payment review", "th": "สรุปยอดโดยไม่ข้าม payment review", "en": "Summarize totals without bypassing payment review."},
            {"id": "human-takeover", "name": "Human Takeover", "status": "ready", "description": "หยุดข้อความอัตโนมัติเมื่อแอดมินรับช่วง", "th": "หยุดข้อความอัตโนมัติเมื่อแอดมินรับช่วง", "en": "Pause automated replies when a human admin takes over."},
            {"id": "line-outbox", "name": "LINE Notify", "status": "outbox", "description": "เก็บเหตุการณ์เพื่อส่ง LINE เมื่อบัญชีพร้อม", "th": "เก็บเหตุการณ์เพื่อส่ง LINE เมื่อบัญชีพร้อม", "en": "Queue events for LINE delivery when the account is configured."},
        ]
    }


@router.get("/agents")
def agents(request: Request) -> dict[str, Any]:
    statuses = {item.provider: item.status for item in _services(request).integrations.statuses()}
    return {
        "items": [
            {"id": "autobot-core", "name": "U.Perfect Autobot", "status": "ready", "scope": "ตอบแชทและปิดการขายแบบมี review", "th": "ตอบแชทและปิดการขายแบบมี review", "en": "Reply to chats and close sales with review gates."},
            {"id": "line-notifier", "name": "LINE Notification Agent", "status": statuses.get("line", "unconfigured"), "scope": "ส่งเหตุการณ์ออเดอร์ที่ยืนยันแล้ว", "th": "ส่งเหตุการณ์ออเดอร์ที่ยืนยันแล้ว", "en": "Deliver confirmed-order events."},
            {"id": "n8n-automation", "name": "n8n Content Automation", "status": statuses.get("n8n", "unconfigured"), "scope": "ตั้งเวลา post/comment เมื่อ webhook พร้อม", "th": "ตั้งเวลา post/comment เมื่อ webhook พร้อม", "en": "Schedule posts and comment replies when the webhook is verified."},
        ]
    }


@router.get("/automation/workflows")
def workflows(request: Request) -> dict[str, Any]:
    status = {item.provider: item.status for item in _services(request).integrations.statuses()}.get("n8n", "unconfigured")
    return {
        "items": [
            {"id": "scheduled-post", "name": "ตั้งเวลาโพส", "status": status, "note": "ยังไม่ส่งโพสต์ออกไปจนกว่าจะตั้งค่า n8n webhook", "th": "ตั้งเวลาโพส", "en": "Scheduled posts", "th_note": "ยังไม่ส่งโพสต์ออกไปจนกว่าจะตั้งค่า n8n webhook", "en_note": "Posts remain disabled until the n8n webhook is configured."},
            {"id": "comment-reply", "name": "ตอบคอมเมนต์", "status": status, "note": "ใช้ catalog/memory เดียวกับ inbox", "th": "ตอบคอมเมนต์", "en": "Comment replies", "th_note": "ใช้ catalog/memory เดียวกับ inbox", "en_note": "Uses the same catalog and memory as the inbox."},
            {"id": "social-update", "name": "Auto Update", "status": status, "note": "ต้องผ่าน account-owner verification", "th": "Auto Update", "en": "Auto Update", "th_note": "ต้องผ่าน account-owner verification", "en_note": "Requires account-owner verification."},
        ]
    }


@router.post("/webhooks/{provider}")
async def accept_webhook(
    provider: str,
    payload: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    integrations = _services(request).integrations
    if not integrations.verify_request(provider, await request.body(), request.headers):
        if provider.casefold().strip() not in {"facebook", "line", "tiktok", "shopee"}:
            return integrations.accept(
                WebhookEvent(provider=provider, event_id="", customer_id="", text="", verified=False)
            )
        raise IntegrationError(
            "webhook signature is missing or invalid",
            code="WEBHOOK_SIGNATURE_INVALID",
            http_status=401,
        )
    event_id = str(payload.get("event_id") or payload.get("id") or "").strip()
    customer_id = str(payload.get("customer_id") or payload.get("sender_id") or "").strip()
    text = str(payload.get("text") or payload.get("message") or "").strip()
    event = WebhookEvent(
        provider=provider,
        event_id=event_id,
        customer_id=customer_id,
        text=text,
        verified=True,
    )
    receipt = integrations.accept(event)
    return {
        "accepted": receipt.accepted,
        "duplicate": receipt.duplicate,
        "message_id": receipt.message_id,
    }
