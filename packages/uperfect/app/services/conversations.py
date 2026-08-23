"""Deterministic, product-fact-bound conversation automation."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from app.repositories import Repository
from app.schemas import AutomationResult, Conversation, DomainError, InboundMessage
from app.services.catalog import CatalogService
from app.services.sales_assets import language_for_text, load_sales_assets, render_asset


INTENTS = (
    "greeting",
    "product_lookup",
    "ingredients",
    "price",
    "delivery",
    "buy",
    "payment",
    "address",
    "objection",
    "takeover",
    "fallback",
)


INTENT_PRIORITY = (
    "takeover",
    "objection",
    "ingredients",
    "price",
    "delivery",
    "payment",
    "address",
    "buy",
    "greeting",
    "product_lookup",
)


def resolve_intent(text: str, sales_assets: Mapping[str, Any] | None = None) -> str:
    value = (text or "").casefold()
    assets = sales_assets or load_sales_assets()
    intents = assets["intents"]
    for intent in INTENT_PRIORITY:
        terms = intents[intent]["keywords"]["th"] + intents[intent]["keywords"]["en"]
        if any(term.casefold() in value for term in terms):
            return intent
    return "fallback"


def extract_quantity(text: str) -> int | None:
    match = re.search(r"(?:รับ|เอา|ซื้อ|สั่ง)?\s*(\d+)\s*(?:ชิ้น|ขวด|กระปุก|ชุด|อัน)?", text or "")
    if not match:
        return None
    quantity = int(match.group(1))
    return quantity if 1 <= quantity <= 100 else None


class ConversationService:
    def __init__(
        self,
        repository: Repository,
        catalog: CatalogService,
        *,
        context_ttl_minutes: int = 45,
        settings_provider: Callable[[], Mapping[str, object]] | None = None,
        sales_assets: Mapping[str, Any] | None = None,
    ) -> None:
        self.repository = repository
        self.catalog = catalog
        self.context_ttl = timedelta(minutes=context_ttl_minutes)
        self.settings_provider = settings_provider or (lambda: {"autobot_enabled": True})
        self.sales_assets = sales_assets or load_sales_assets()

    def receive(self, event: InboundMessage) -> AutomationResult:
        platform = (event.platform or "").strip().casefold()
        customer_id = (event.customer_id or "").strip()
        text = (event.text or "").strip()
        if not platform or not customer_id or not text:
            raise DomainError("ต้องระบุช่องทาง ลูกค้า และข้อความ", code="INVALID_MESSAGE")

        conversation = (
            self.repository.get_conversation(event.conversation_id)
            if event.conversation_id
            else self.repository.get_or_create_conversation(platform, customer_id)
        )
        self.repository.append_message(conversation.id, "inbound", text, "inbound", False)

        now = datetime.now(timezone.utc)
        if conversation.human_takeover and conversation.takeover_until and conversation.takeover_until <= now:
            conversation = self.repository.update_conversation(conversation.id, human_takeover=False)

        if conversation.human_takeover:
            return AutomationResult(
                conversation=conversation,
                reply=None,
                intent="fallback",
                automated=False,
                active_product_id=conversation.active_product_id,
            )

        if not bool(self.settings_provider().get("autobot_enabled", True)):
            return AutomationResult(
                conversation=conversation,
                reply=None,
                intent="autobot_disabled",
                automated=False,
                active_product_id=conversation.active_product_id,
            )

        explicit_product = self.catalog.find_by_text(text)
        product = explicit_product or self.catalog.get_optional(conversation.active_product_id)
        if explicit_product:
            conversation = self.repository.update_conversation(
                conversation.id,
                active_product_id=explicit_product.id,
                selected_quantity=extract_quantity(text) or conversation.selected_quantity,
                current_step="product_selected",
            )
        else:
            product = self.catalog.get_optional(conversation.active_product_id)

        intent = resolve_intent(text, self.sales_assets)
        quantity = extract_quantity(text)
        if quantity and product:
            conversation = self.repository.update_conversation(
                conversation.id,
                selected_quantity=quantity,
                current_step="quantity_selected",
            )

        language = language_for_text(
            text,
            str(self.settings_provider().get("default_language", self.sales_assets["default_language"])),
        )
        reply = self._reply(
            intent,
            product,
            quantity or conversation.selected_quantity,
            text,
            language,
        )
        if reply is None:
            reply = self._fallback(product, language)
            intent = "product_lookup" if product else "fallback"
        if intent == "takeover":
            conversation = self.set_takeover(conversation.id, True)
        self.repository.append_message(conversation.id, "outbound", reply, intent, True)
        conversation = self.repository.get_conversation(conversation.id)
        return AutomationResult(
            conversation=conversation,
            reply=reply,
            intent=intent,
            automated=True,
            active_product_id=product.id if product else conversation.active_product_id,
        )

    def set_takeover(self, conversation_id: str, enabled: bool) -> Conversation:
        timeout = self.settings_provider().get("human_takeover_timeout_minutes", 45)
        try:
            timeout_minutes = max(1, min(int(timeout), 1440))
        except (TypeError, ValueError):
            timeout_minutes = 45
        until = datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes) if enabled else None
        conversation = self.repository.update_conversation(
            conversation_id,
            human_takeover=enabled,
            takeover_until=until,
            current_step="human_takeover" if enabled else "automation_ready",
        )
        self.repository.audit(
            "conversation_takeover_changed",
            conversation_id,
            "admin",
            {"enabled": enabled},
        )
        return conversation

    def get_context(self, conversation_id: str) -> Conversation:
        return self.repository.get_conversation(conversation_id)

    def messages(self, conversation_id: str) -> list[dict[str, object]]:
        return self.repository.list_messages(conversation_id)

    def _reply(self, intent: str, product, quantity: int | None, text: str, language: str) -> str | None:
        replies = self.sales_assets["intents"].get(intent, {}).get("replies", {})
        template = replies.get(language) or replies.get("th")
        if intent == "greeting":
            return template
        if intent == "takeover":
            return template
        if intent == "objection":
            objection = self._objection_key(text)
            if objection:
                return self.sales_assets["objections"][objection]["replies"][language]
            return template
        if intent == "product_lookup" and not product:
            return template
        if intent == "ingredients" and product:
            if not product.ingredients:
                return render_asset(
                    template,
                    {"product_name": product.name, "ingredient_lines": "ข้อมูลส่วนประกอบเพิ่มเติมยังไม่พร้อมในระบบค่ะ"},
                )
            details = "\n".join(
                f"{index}. {item.name}: {item.benefit_copy}"
                for index, item in enumerate(product.ingredients, 1)
            )
            return render_asset(template, {"product_name": product.name, "ingredient_lines": details})
        if intent == "price" and product:
            return self._price_reply(product, quantity, language)
        if intent == "delivery":
            if product and product.promotions and any(p.shipping_free for p in product.promotions):
                return self.sales_assets["intents"]["delivery"]["free_promotion_replies"][language]
            return template
        if intent == "buy" and product:
            if product.price_thb is None:
                return render_asset(
                    self.sales_assets["intents"]["buy"]["unpriced_replies"][language],
                    {"product_name": product.name},
                )
            selected = quantity or 1
            return render_asset(template, {"product_name": product.name, "quantity": selected})
        if intent == "payment":
            return template
        if intent == "address":
            return template
        return None

    def _price_reply(self, product, quantity: int | None, language: str) -> str:
        if product.price_thb is None:
            return render_asset(
                self.sales_assets["intents"]["price"]["unpriced_replies"][language],
                {"product_name": product.name},
            )
        lines = []
        for promo in product.promotions:
            lines.append(
                (
                    f"{promo.label}: {promo.minimum_quantity} ชิ้น {promo.bundle_price_thb.normalize()} บาท"
                    + (" และข้อมูลโปรระบุว่าส่งฟรี" if promo.shipping_free else "")
                )
                if language == "th"
                else (
                    f"{promo.label}: {promo.minimum_quantity} items for {promo.bundle_price_thb.normalize()} THB"
                    + ("; the promotion states free shipping" if promo.shipping_free else "")
                )
            )
        promotion_lines = "\n".join(lines) or (
            "ยังไม่มีโปรโมชันที่ยืนยันในระบบค่ะ" if language == "th" else "No verified promotion is currently listed."
        )
        if quantity:
            promotion_lines += (
                f"\nจำนวนที่เลือก: {quantity} ชิ้น"
                if language == "th"
                else f"\nSelected quantity: {quantity} item(s)"
            )
        return render_asset(
            self.sales_assets["intents"]["price"]["replies"][language],
            {
                "product_name": product.name,
                "price": f"{product.price_thb.normalize()}" if language == "th" else f"{product.price_thb.normalize()}",
                "promotion_lines": promotion_lines,
            },
        )

    def _objection_key(self, text: str) -> str | None:
        value = (text or "").casefold()
        for objection_id in ("sensitive_skin", "price_objection", "hesitation"):
            terms = self.sales_assets["objections"][objection_id]["keywords"]["th"]
            terms += self.sales_assets["objections"][objection_id]["keywords"]["en"]
            if any(term.casefold() in value for term in terms):
                return objection_id
        return None

    def _fallback(self, product, language: str) -> str:
        if product:
            cta = self.sales_assets["products"].get(product.id, {}).get("closing_cta", {}).get(language)
            if cta:
                return render_asset(cta, {"product_name": product.name})
        return self.sales_assets["intents"]["fallback"]["replies"][language]
