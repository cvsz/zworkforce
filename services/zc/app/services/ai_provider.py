"""Default server-side AI provider adapter."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from collections.abc import AsyncIterator
from typing import Any

import aiohttp
import yaml

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"


@dataclass(frozen=True)
class ProviderGeneration:
    """Normalized provider output consumed by the application service."""

    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class ProviderStreamChunk:
    """One normalized text or usage update from a streaming provider."""

    text: str = ""
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class AnthropicCoderAdapter:
    """Small synchronous adapter executed by ``AIService`` in a worker thread."""

    def __init__(
        self,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
        personality_style: str | None = None,
        service_tier: str | None = None,
        inference_geo: str | None = None,
        fast_mode: bool = False,
    ) -> None:
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.service_tier = service_tier
        self.inference_geo = inference_geo
        self.fast_mode = fast_mode

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        file_content: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> ProviderGeneration | str:
        if not self.api_key:
            return "[ERROR] AI provider credential is not configured"

        user_content = prompt
        if file_content:
            user_content = f"File content:\n```\n{file_content}\n```\n\n{prompt}"

        messages: list[dict[str, Any]] = list(history or [])
        messages.append({"role": "user", "content": user_content})
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if system:
            payload["system"] = system
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.service_tier:
            payload["service_tier"] = self.service_tier
        if self.inference_geo:
            payload["inference_geo"] = self.inference_geo
        if self.fast_mode:
            payload["speed"] = "fast"

        try:
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    ANTHROPIC_MESSAGES_URL,
                    json=payload,
                    headers={
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                        "x-api-key": self.api_key,
                    },
                ) as response:
                    if response.status >= 400:
                        return (
                            f"[API ERROR {response.status}] "
                            "AI provider request failed"
                        )
                    body = json.loads(await response.text())
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return "[ERROR] AI provider request failed"

        content = body.get("content", [])
        text = "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
        if not text:
            return "[ERROR] AI provider returned no text"
        usage = body.get("usage", {})
        return ProviderGeneration(
            text=text,
            model=str(body.get("model") or self.model),
            input_tokens=_optional_non_negative_int(usage.get("input_tokens")),
            output_tokens=_optional_non_negative_int(usage.get("output_tokens")),
        )

    async def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        file_content: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[ProviderStreamChunk]:
        """Stream normalized Anthropic SSE text deltas."""
        if not self.api_key:
            raise RuntimeError("AI provider credential is not configured")

        user_content = prompt
        if file_content:
            user_content = f"File content:\n```\n{file_content}\n```\n\n{prompt}"
        messages: list[dict[str, Any]] = list(history or [])
        messages.append({"role": "user", "content": user_content})
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
            "stream": True,
        }
        if system:
            payload["system"] = system
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.service_tier:
            payload["service_tier"] = self.service_tier
        if self.inference_geo:
            payload["inference_geo"] = self.inference_geo
        if self.fast_mode:
            payload["speed"] = "fast"

        timeout = aiohttp.ClientTimeout(total=120)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    ANTHROPIC_MESSAGES_URL,
                    json=payload,
                    headers={
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                        "x-api-key": self.api_key,
                    },
                ) as response:
                    if response.status >= 400:
                        raise RuntimeError("AI provider request failed")
                    async for raw_line in response.content:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line.startswith("data:"):
                            continue
                        raw_data = line[5:].strip()
                        if not raw_data or raw_data == "[DONE]":
                            continue
                        event = json.loads(raw_data)
                        event_type = event.get("type")
                        if event_type == "message_start":
                            message = event.get("message") or {}
                            usage = message.get("usage") or {}
                            yield ProviderStreamChunk(
                                model=str(message.get("model") or self.model),
                                input_tokens=_optional_non_negative_int(
                                    usage.get("input_tokens")
                                ),
                            )
                        elif event_type == "content_block_delta":
                            delta = event.get("delta") or {}
                            text = delta.get("text")
                            if isinstance(text, str) and text:
                                yield ProviderStreamChunk(text=text)
                        elif event_type == "message_delta":
                            usage = event.get("usage") or {}
                            yield ProviderStreamChunk(
                                output_tokens=_optional_non_negative_int(
                                    usage.get("output_tokens")
                                )
                            )
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            raise RuntimeError("AI provider request failed") from exc


_router_cache: dict[Path, Any] = {}


class EmbeddedLiteLLMAdapter:
    """Process-local LiteLLM Router adapter with no proxy server."""

    def __init__(
        self,
        *,
        config_path: Path,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
        timeout_seconds: int = 120,
        personality_style: str | None = None,
        service_tier: str | None = None,
        inference_geo: str | None = None,
        fast_mode: bool = False,
        router: Any | None = None,
    ) -> None:
        del personality_style, service_tier, inference_geo, fast_mode
        self.config_path = config_path.resolve()
        self.model = model or "zc-default"
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self._router = router

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        file_content: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> ProviderGeneration | str:
        """Generate text through the embedded LiteLLM Router."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(history or [])

        user_content = prompt
        if file_content:
            user_content = f"File content:\n```\n{file_content}\n```\n\n{prompt}"
        messages.append({"role": "user", "content": user_content})

        options: dict[str, Any] = {"max_tokens": self.max_tokens}
        if self.temperature is not None:
            options["temperature"] = self.temperature

        try:
            response = await self._get_router().acompletion(
                model=self.model,
                messages=messages,
                timeout=self.timeout_seconds,
                **options,
            )
        except Exception:
            return "[ERROR] AI provider request failed"

        try:
            message = response.choices[0].message
            content = message.content
        except (AttributeError, IndexError, TypeError):
            return "[ERROR] AI provider returned no text"

        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(
                str(part.get("text", ""))
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        if not text:
            return "[ERROR] AI provider returned no text"

        usage = getattr(response, "usage", None)
        return ProviderGeneration(
            text=text,
            model=str(getattr(response, "model", None) or self.model),
            input_tokens=_optional_non_negative_int(
                getattr(usage, "prompt_tokens", None)
            ),
            output_tokens=_optional_non_negative_int(
                getattr(usage, "completion_tokens", None)
            ),
        )

    async def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        file_content: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[ProviderStreamChunk]:
        """Stream normalized deltas from the embedded LiteLLM Router."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(history or [])
        user_content = prompt
        if file_content:
            user_content = f"File content:\n```\n{file_content}\n```\n\n{prompt}"
        messages.append({"role": "user", "content": user_content})

        options: dict[str, Any] = {"max_tokens": self.max_tokens}
        if self.temperature is not None:
            options["temperature"] = self.temperature
        try:
            response = await self._get_router().acompletion(
                model=self.model,
                messages=messages,
                timeout=self.timeout_seconds,
                stream=True,
                **options,
            )
            async for chunk in response:
                choices = getattr(chunk, "choices", None) or []
                delta = getattr(choices[0], "delta", None) if choices else None
                content = getattr(delta, "content", None)
                usage = getattr(chunk, "usage", None)
                yield ProviderStreamChunk(
                    text=content if isinstance(content, str) else "",
                    model=str(getattr(chunk, "model", None) or self.model),
                    input_tokens=_optional_non_negative_int(
                        getattr(usage, "prompt_tokens", None)
                    ),
                    output_tokens=_optional_non_negative_int(
                        getattr(usage, "completion_tokens", None)
                    ),
                )
        except Exception as exc:
            raise RuntimeError("AI provider request failed") from exc

    async def list_models(self) -> list[str]:
        """Return configured model aliases without a network round trip."""
        return sorted(set(self._get_router().get_model_names()))

    async def is_live(self) -> bool:
        """Return whether the embedded router initialized with at least one model."""
        try:
            return bool(self._get_router().get_model_names())
        except Exception:
            return False

    def _get_router(self) -> Any:
        """Lazily create and reuse one Router for each configuration file."""
        if self._router is not None:
            return self._router
        cached = _router_cache.get(self.config_path)
        if cached is None:
            cached = _load_litellm_router(self.config_path)
            _router_cache[self.config_path] = cached
        self._router = cached
        return cached


def _load_litellm_router(config_path: Path) -> Any:
    """Build a LiteLLM Router from the zc-owned YAML configuration."""
    from litellm import Router

    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    model_list = config.get("model_list")
    if not isinstance(model_list, list) or not model_list:
        raise RuntimeError("LiteLLM config must define a non-empty model_list")
    router_settings = config.get("router_settings") or {}
    if not isinstance(router_settings, dict):
        raise RuntimeError("LiteLLM router_settings must be a mapping")
    return Router(model_list=model_list, **router_settings)


async def close_embedded_litellm() -> None:
    """Close LiteLLM's cached async clients during application shutdown."""
    if not _router_cache:
        return
    from litellm.llms.custom_httpx.async_client_cleanup import (
        close_litellm_async_clients,
    )

    await close_litellm_async_clients()
    _router_cache.clear()


def _optional_non_negative_int(value: object) -> int | None:
    """Normalize optional provider token counts without accepting booleans."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


__all__ = [
    "ANTHROPIC_MESSAGES_URL",
    "AnthropicCoderAdapter",
    "EmbeddedLiteLLMAdapter",
    "ProviderGeneration",
    "ProviderStreamChunk",
    "close_embedded_litellm",
]
