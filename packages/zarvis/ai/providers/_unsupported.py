from __future__ import annotations

from typing import Any


class UnsupportedProviderError(RuntimeError):
    """Raised when a provider is inventoried but has no safe runtime adapter."""


class UnsupportedProvider:
    """Explicit fail-closed base for providers that are not implemented yet."""

    supported = False

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name

    def generate(self, _prompt: str, _system_prompt: str = "", **_kwargs: Any) -> str:
        raise UnsupportedProviderError(
            f"provider '{self.provider_name}' has no production adapter; refusing to fabricate a response"
        )
