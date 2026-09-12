from __future__ import annotations

import httpx
import pytest

from ztrader_intel.providers import ZaimanProvider


@pytest.mark.asyncio
async def test_zaiman_provider_requires_authenticated_complete_config(monkeypatch) -> None:
    monkeypatch.delenv("ZAIMAN_BASE_URL", raising=False)
    monkeypatch.delenv("ZAIMAN_API_KEY", raising=False)
    monkeypatch.delenv("ZAIMAN_MODEL", raising=False)
    async with httpx.AsyncClient() as client:
        assert ZaimanProvider(client).enabled is False


@pytest.mark.asyncio
async def test_zaiman_provider_uses_responses_api_and_bearer_key(monkeypatch) -> None:
    monkeypatch.setenv("ZAIMAN_BASE_URL", "http://zaiman.internal/v1")
    monkeypatch.setenv("ZAIMAN_API_KEY", "test-service-key")
    monkeypatch.setenv("ZAIMAN_MODEL", "provider/model")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://zaiman.internal/v1/responses"
        assert request.headers["Authorization"] == "Bearer test-service-key"
        return httpx.Response(200, json={"output_text": "EARLY"}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ZaimanProvider(client)
        assert provider.enabled is True
        result = await provider.summarize_evidence("TOKEN", ["organic discussion"])
        assert result == "EARLY"
