"""Server-only LINE push transport for the notification worker."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


class LineNotificationSender:
    def __init__(self, channel_access_token: str | None) -> None:
        self._channel_access_token = channel_access_token

    def __call__(self, destination: str, body: str) -> None:
        if not self._channel_access_token:
            raise RuntimeError("LINE channel access token is not configured")
        request = Request(
            LINE_PUSH_URL,
            method="POST",
            data=json.dumps(
                {
                    "to": destination,
                    "messages": [{"type": "text", "text": body[:5000]}],
                },
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._channel_access_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                if response.status >= 300:
                    raise RuntimeError(f"LINE push failed with HTTP {response.status}")
        except HTTPError as error:
            raise RuntimeError(f"LINE push failed with HTTP {error.code}") from error
        except (OSError, URLError, TimeoutError) as error:
            raise RuntimeError("LINE push transport failed") from error
