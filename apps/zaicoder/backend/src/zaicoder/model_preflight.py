"""Account-aware, opt-in model capability preflight."""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable


class ModelUnavailableError(ValueError):
    """The configured model cannot be verified."""


class ModelCapabilityResolver:
    """Fetch model metadata once per resolver without retaining credentials."""

    def __init__(
        self,
        api_key: str,
        *,
        known_models: dict[str, dict] | None = None,
        opener: Callable = urllib.request.urlopen,
    ):
        self.api_key = api_key
        self.known_models = known_models or {}
        self._opener = opener
        self._cache: dict[str, dict] = {}

    def resolve(self, model: str) -> dict:
        if model in self._cache:
            return self._cache[model]

        request = urllib.request.Request(
            f"https://api.anthropic.com/v1/models/{model}",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            with self._opener(request, timeout=10) as response:
                metadata = json.loads(response.read().decode())
        except Exception as exc:
            if model in self.known_models:
                return dict(self.known_models[model])
            raise ModelUnavailableError(
                f"Unable to verify model '{model}'. Check account access or connectivity."
            ) from exc

        self._cache[model] = metadata
        return metadata
