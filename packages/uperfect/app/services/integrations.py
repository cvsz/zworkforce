"""Truthful provider state and idempotent inbound webhook intake."""

from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import LOCAL_OLLAMA_BASE_URL, Settings
from app.repositories import Repository
from app.schemas import IntegrationError, IntegrationStatus, InboundMessage, WebhookEvent, WebhookReceipt
from app.services.conversations import ConversationService
from app.services.webhook_auth import WebhookVerifier


SUPPORTED_PROVIDERS = {"facebook", "line", "tiktok", "shopee"}


class IntegrationService:
    def __init__(self, repository: Repository, settings: Settings, conversations: ConversationService) -> None:
        self.repository = repository
        self.settings = settings
        self.conversations = conversations
        self.webhook_verifier = WebhookVerifier(settings)

    def verify_request(self, provider: str, raw_body: bytes, headers) -> bool:
        return self.webhook_verifier.verify(provider, raw_body, headers)

    def statuses(self) -> list[IntegrationStatus]:
        values = []
        for item in self.repository.list_integration_statuses():
            status = self._local_ai_status() if item.provider == "local_ai" else self.settings.integration_status(item.provider)
            self.repository.update_integration_status(item.provider, status)
            values.append(
                IntegrationStatus(
                    provider=item.provider,
                    label=item.label,
                    status=status,
                    webhook_path=item.webhook_path,
                    setup_note=item.setup_note,
                )
            )
        return values

    def _local_ai_status(self) -> str:
        """Report Ollama availability without contacting any external provider."""

        if self.settings.integration_status("local_ai") != "configured":
            return "unconfigured"
        if self.settings.local_ai_base_url != LOCAL_OLLAMA_BASE_URL:
            return "unconfigured"

        request = Request(f"{self.settings.local_ai_base_url.rstrip('/')}/api/tags", method="GET")
        try:
            with urlopen(request, timeout=2) as response:
                payload = json.load(response)
        except (OSError, URLError, TimeoutError, ValueError):
            return "degraded"

        models = payload.get("models", []) if isinstance(payload, dict) else []
        names = {item.get("name") for item in models if isinstance(item, dict)}
        return "configured" if self.settings.local_ai_model in names else "degraded"

    def accept(self, event: WebhookEvent) -> WebhookReceipt:
        provider = event.provider.casefold().strip()
        if provider not in SUPPORTED_PROVIDERS:
            raise IntegrationError("ไม่รองรับช่องทางนี้", code="UNSUPPORTED_PROVIDER")
        if not event.verified:
            raise IntegrationError("webhook ยังไม่ผ่านการตรวจสอบลายเซ็น", code="WEBHOOK_SIGNATURE_INVALID", http_status=401)
        if not event.event_id.strip() or not event.customer_id.strip() or not event.text.strip():
            raise IntegrationError("ข้อมูล webhook ไม่ครบถ้วน", code="INVALID_WEBHOOK")
        if not self.repository.claim_webhook(provider, event.event_id):
            return WebhookReceipt(accepted=True, duplicate=True, message_id=None)
        result = self.conversations.receive(
            InboundMessage(provider, event.customer_id.strip(), event.text.strip())
        )
        self.repository.audit("webhook_accepted", result.conversation.id, provider, {"event_id": event.event_id})
        return WebhookReceipt(accepted=True, duplicate=False, message_id=result.conversation.id)
