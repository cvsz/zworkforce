"""Provider-aware HMAC verification for normalized webhook intake."""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Mapping

from app.config import Settings


class WebhookVerifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @staticmethod
    def _header(headers: Mapping[str, str], name: str) -> str | None:
        return headers.get(name) or headers.get(name.lower())

    def verify(self, provider: str, raw_body: bytes, headers: Mapping[str, str]) -> bool:
        provider = provider.casefold().strip()
        secret = self.settings.webhook_secret(provider)
        if not secret:
            return False

        digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256)
        if provider == "line":
            provided = self._header(headers, "X-Line-Signature")
            expected = base64.b64encode(digest.digest()).decode("ascii")
        else:
            provided_header = self._header(
                headers,
                "X-Hub-Signature-256" if provider == "facebook" else "X-UPerfect-Webhook-Signature",
            )
            if not provided_header or not provided_header.startswith("sha256="):
                return False
            provided = provided_header.removeprefix("sha256=")
            expected = digest.hexdigest()
        return bool(provided) and hmac.compare_digest(provided, expected)
