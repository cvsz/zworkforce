"""Minimal OpenAI-compatible client for the Z Platform AI Gateway."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable


class GatewayError(RuntimeError):
    """The platform gateway rejected or could not process a request."""


class GatewayClient:
    """Send model requests without exposing upstream provider credentials."""

    def __init__(
        self,
        base_url: str,
        service_token: str,
        *,
        opener: Callable = urllib.request.urlopen,
    ):
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("Gateway URL must use HTTP or HTTPS")
        if not service_token:
            raise ValueError("Gateway service token is required")
        self.base_url = base_url.rstrip("/")
        self.service_token = service_token
        self._opener = opener

    def chat(self, *, model: str, prompt: str, timeout_seconds: float = 60) -> str:
        if not model.strip():
            raise ValueError("Model is required")
        if not prompt.strip():
            raise ValueError("Prompt is required")

        payload = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }
        ).encode()
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.service_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=timeout_seconds) as response:
                body = json.loads(response.read().decode())
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise GatewayError("AI gateway request failed") from exc
        except json.JSONDecodeError as exc:
            raise GatewayError("AI gateway returned invalid JSON") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GatewayError("AI gateway returned an unsupported response") from exc
        if not isinstance(content, str):
            raise GatewayError("AI gateway response content must be text")
        return content
