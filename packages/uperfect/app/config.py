"""Runtime configuration that deliberately keeps secret values private."""

from __future__ import annotations

import os
from dataclasses import dataclass, fields


LOCAL_ONLY_HOST = "192.168.74.130"
LOCAL_OLLAMA_BASE_URL = f"http://{LOCAL_ONLY_HOST}:11434"
DEFAULT_LOCAL_AI_MODEL = "zCoder:latest"
SECRET_FIELDS = frozenset(
    {
        "line_admin_destination",
        "line_channel_access_token",
        "line_channel_secret",
        "facebook_page_access_token",
        "facebook_verify_token",
        "facebook_app_secret",
        "tiktok_app_key",
        "tiktok_app_secret",
        "tiktok_refresh_token",
        "tiktok_webhook_secret",
        "shopee_partner_id",
        "shopee_partner_key",
        "shopee_shop_id",
        "shopee_webhook_secret",
        "n8n_webhook_url",
        "gemini_api_key",
    }
)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, repr=False)
class Settings:
    """Configuration loaded only from the process environment."""

    database_path: str
    line_channel_access_token: str | None
    line_admin_destination: str | None = None
    line_channel_secret: str | None = None
    facebook_page_access_token: str | None = None
    facebook_verify_token: str | None = None
    facebook_app_secret: str | None = None
    tiktok_app_key: str | None = None
    tiktok_app_secret: str | None = None
    tiktok_refresh_token: str | None = None
    tiktok_webhook_secret: str | None = None
    shopee_partner_id: str | None = None
    shopee_partner_key: str | None = None
    shopee_shop_id: str | None = None
    shopee_webhook_secret: str | None = None
    n8n_webhook_url: str | None = None
    gemini_api_key: str | None = None
    local_only_mode: bool = False
    local_ai_base_url: str = LOCAL_OLLAMA_BASE_URL
    local_ai_model: str = DEFAULT_LOCAL_AI_MODEL

    def __repr__(self) -> str:
        values = []
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name in SECRET_FIELDS:
                value = "***" if value else None
            values.append(f"{field.name}={value!r}")
        return f"{type(self).__name__}({', '.join(values)})"

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            database_path=os.getenv("UPERFECT_DATABASE_PATH", "uperfect.db"),
            line_channel_access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN") or None,
            line_admin_destination=os.getenv("LINE_ADMIN_DESTINATION") or None,
            line_channel_secret=os.getenv("LINE_CHANNEL_SECRET") or None,
            facebook_page_access_token=os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN") or None,
            facebook_verify_token=os.getenv("FACEBOOK_VERIFY_TOKEN") or None,
            facebook_app_secret=os.getenv("FACEBOOK_APP_SECRET") or None,
            tiktok_app_key=os.getenv("TIKTOK_APP_KEY") or None,
            tiktok_app_secret=os.getenv("TIKTOK_APP_SECRET") or None,
            tiktok_refresh_token=os.getenv("TIKTOK_REFRESH_TOKEN") or None,
            tiktok_webhook_secret=os.getenv("TIKTOK_WEBHOOK_SECRET") or None,
            shopee_partner_id=os.getenv("SHOPEE_PARTNER_ID") or None,
            shopee_partner_key=os.getenv("SHOPEE_PARTNER_KEY") or None,
            shopee_shop_id=os.getenv("SHOPEE_SHOP_ID") or None,
            shopee_webhook_secret=os.getenv("SHOPEE_WEBHOOK_SECRET") or None,
            n8n_webhook_url=os.getenv("N8N_WEBHOOK_URL") or None,
            gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
            local_only_mode=_env_bool("UPERFECT_LOCAL_ONLY"),
            local_ai_base_url=os.getenv("UPERFECT_LOCAL_AI_BASE_URL", LOCAL_OLLAMA_BASE_URL).strip(),
            local_ai_model=os.getenv("UPERFECT_LOCAL_AI_MODEL", DEFAULT_LOCAL_AI_MODEL).strip(),
        )

    def integration_status(self, name: str) -> str:
        requirements = {
            "facebook": (self.facebook_page_access_token, self.facebook_verify_token),
            "tiktok": (self.tiktok_app_key, self.tiktok_app_secret, self.tiktok_refresh_token),
            "shopee": (self.shopee_partner_id, self.shopee_partner_key, self.shopee_shop_id),
            "line": (self.line_channel_access_token,),
            "n8n": (self.n8n_webhook_url,),
            "gemini": (self.gemini_api_key,),
        }
        if name == "local_ai":
            return (
                "configured"
                if self.local_only_mode
                and self.local_ai_base_url == LOCAL_OLLAMA_BASE_URL
                and bool(self.local_ai_model)
                else "unconfigured"
            )
        values = requirements.get(name, ())
        if not values or not all(values):
            return "unconfigured"
        if name in {"facebook", "tiktok", "shopee"} and not self.webhook_secret(name):
            return "degraded"
        return "configured"

    def webhook_secret(self, provider: str) -> str | None:
        return {
            "facebook": self.facebook_app_secret,
            "line": self.line_channel_secret,
            "tiktok": self.tiktok_webhook_secret,
            "shopee": self.shopee_webhook_secret,
        }.get(provider.casefold().strip())
