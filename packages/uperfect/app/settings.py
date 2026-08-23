"""Safe, non-secret workspace preferences persisted by the admin UI."""

from __future__ import annotations

from typing import Any


DEFAULT_WORKSPACE_SETTINGS: dict[str, Any] = {
    "store_name": "U.Perfect",
    "store_handle": "@spookyuperfect",
    "facebook_page_url": "https://www.facebook.com/spookyuperfect",
    "timezone": "Asia/Bangkok",
    "default_language": "th",
    "assistant_tone": "warm",
    "autobot_enabled": True,
    "human_takeover_timeout_minutes": 30,
    "n8n_auto_post_enabled": False,
    "n8n_comment_reply_enabled": False,
    "line_notifications_enabled": False,
    "payment_review_alerts_enabled": True,
    "local_only_mode": True,
    "local_host": "192.168.74.130",
    "local_ai_base_url": "http://192.168.74.130:11434",
    "local_ai_model": "zCoder:latest",
}


def default_workspace_settings() -> dict[str, Any]:
    """Return a copy so callers cannot mutate the process-wide defaults."""

    return dict(DEFAULT_WORKSPACE_SETTINGS)
