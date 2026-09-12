from __future__ import annotations

import httpx
import pytest

from ztrader_intel.providers import ZKsatoProvider, ZWalletProvider


@pytest.mark.asyncio
async def test_zksato_provider_enforces_non_execution_response(monkeypatch) -> None:
    monkeypatch.setenv("ZKSATO_BASE_URL", "http://zksato.internal")
    monkeypatch.setenv("ZKSATO_API_KEY", "service-key")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == (
            "http://zksato.internal/v1/integrations/ztrader/advisory-intents"
        )
        assert request.headers["X-API-Key"] == "service-key"
        assert request.headers["X-Request-ID"] == "trace-001"
        return httpx.Response(
            202,
            json={
                "accepted": True,
                "execution_allowed": False,
                "risk_review_required": True,
                "signal_id": "signal-001",
                "trace_id": "trace-001",
                "canonical_executor": "zksato",
                "mode": "paper",
                "reason": "recorded",
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ZKsatoProvider(client)
        result = await provider.submit_advisory(
            {"signal_id": "signal-001", "trace_id": "trace-001"}
        )
        assert result["execution_allowed"] is False


@pytest.mark.asyncio
async def test_zksato_provider_rejects_unsafe_execution_response(monkeypatch) -> None:
    monkeypatch.setenv("ZKSATO_BASE_URL", "http://zksato.internal")
    monkeypatch.setenv("ZKSATO_API_KEY", "service-key")

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            202,
            json={"execution_allowed": True},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError):
            await ZKsatoProvider(client).submit_advisory(
                {"signal_id": "signal-001", "trace_id": "trace-001"}
            )


@pytest.mark.asyncio
async def test_zwallet_provider_propagates_trace_and_read_only_request(monkeypatch) -> None:
    monkeypatch.setenv("ZWALLET_BASE_URL", "http://zwallet.internal")
    monkeypatch.setenv("ZWALLET_SERVICE_TOKEN", "service-token")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == (
            "http://zwallet.internal/v1/integrations/ztrader/onchain-evidence"
        )
        assert request.headers["Authorization"] == "Bearer service-token"
        assert request.headers["X-Request-ID"] == "trace-002"
        return httpx.Response(
            200,
            json={
                "version": "1.0",
                "trace_id": "trace-002",
                "chain": "ethereum",
                "address": "0x1111111111111111111111111111111111111111",
                "observed_at": "2026-09-12T11:00:00Z",
                "freshness_seconds": 0,
                "quality": "UNAVAILABLE",
                "sources": [
                    {
                        "provider": "zwallet:collector-status",
                        "reference": None,
                        "observed_at": "2026-09-12T11:00:00Z",
                    }
                ],
                "evidence": {},
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ZWalletProvider(client).onchain_evidence(
            trace_id="trace-002",
            chain="ethereum",
            address="0x1111111111111111111111111111111111111111",
        )
        assert result["trace_id"] == "trace-002"
        assert result["quality"] == "UNAVAILABLE"
