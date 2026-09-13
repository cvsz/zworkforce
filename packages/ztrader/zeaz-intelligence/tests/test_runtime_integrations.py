from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from ztrader_intel.api import app
from ztrader_intel.providers import ProviderError, ZKsatoProvider, ZWalletProvider


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
    monkeypatch.setenv("ZWALLET_EVIDENCE_VERSION", "1.1")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == (
            "http://zwallet.internal/v1/integrations/ztrader/onchain-evidence"
        )
        assert request.headers["Authorization"] == "Bearer service-token"
        assert request.headers["X-Request-ID"] == "trace-002"
        assert json.loads(request.content)["version"] == "1.1"
        return httpx.Response(
            200,
            json={
                "version": "1.1",
                "trace_id": "trace-002",
                "chain": "ethereum",
                "address": "0x1111111111111111111111111111111111111111",
                "collector_version": "zwallet-evidence/1.0.0",
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
        assert result["collector_version"] == "zwallet-evidence/1.0.0"
        assert result["quality"] == "UNAVAILABLE"


@pytest.mark.asyncio
async def test_zwallet_provider_rejects_v11_without_collector_provenance(monkeypatch) -> None:
    monkeypatch.setenv("ZWALLET_BASE_URL", "http://zwallet.internal")
    monkeypatch.setenv("ZWALLET_SERVICE_TOKEN", "service-token")
    monkeypatch.setenv("ZWALLET_EVIDENCE_VERSION", "1.1")

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "version": "1.1",
                "trace_id": "trace-003",
                "chain": "ethereum",
                "address": "0x1111111111111111111111111111111111111111",
                "observed_at": "2026-09-12T11:00:00Z",
                "freshness_seconds": 0,
                "quality": "UNAVAILABLE",
                "sources": [],
                "evidence": {},
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError, match="collector_version"):
            await ZWalletProvider(client).onchain_evidence(
                trace_id="trace-003",
                chain="ethereum",
                address="0x1111111111111111111111111111111111111111",
            )


@pytest.mark.asyncio
async def test_zwallet_provider_keeps_v1_legacy_default(monkeypatch) -> None:
    monkeypatch.setenv("ZWALLET_BASE_URL", "http://zwallet.internal")
    monkeypatch.setenv("ZWALLET_SERVICE_TOKEN", "service-token")
    monkeypatch.delenv("ZWALLET_EVIDENCE_VERSION", raising=False)

    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["version"] == "1.0"
        return httpx.Response(
            200,
            json={
                "version": "1.0",
                "trace_id": "trace-legacy",
                "chain": "ethereum",
                "address": "0x1111111111111111111111111111111111111111",
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ZWalletProvider(client).onchain_evidence(
            trace_id="trace-legacy",
            chain="ethereum",
            address="0x1111111111111111111111111111111111111111",
        )
        assert result["version"] == "1.0"


def _integration_headers() -> dict[str, str]:
    return {"X-API-Key": "inbound-service-key"}


def _valid_advisory() -> dict[str, object]:
    return {
        "version": "1.1",
        "tenant_id": "tenant-demo",
        "account_ref": "paper-account-1",
        "portfolio_ref": "portfolio-alpha",
        "signal_id": "signal-route-001",
        "trace_id": "trace-route-001",
        "symbol": "ABC",
        "chain": "ethereum",
        "address": "0x1111111111111111111111111111111111111111",
        "scores": {"opportunity": 72, "risk": 30, "confidence": 68},
        "narrative": "EARLY",
        "whales": "NEUTRAL",
        "rug_risk": "LOW",
        "action": "WATCH",
        "evidence_timestamp": "2026-09-12T11:00:00Z",
        "invalidations": ["risk >= 55"],
        "proposed_trade": {
            "mode": "paper",
            "side": "buy",
            "order_type": "limit",
            "entry_low": 1.0,
            "entry_high": 1.1,
            "stop_loss": 0.9,
            "take_profit_levels": [1.3],
            "max_position_usd": 100.0,
        },
        "evidence": {"source": "test"},
    }


def test_onchain_route_requires_auth_and_reaches_zwallet_provider(monkeypatch) -> None:
    monkeypatch.setenv("ZTRADER_INTEL_SERVICE_TOKEN", "inbound-service-key")

    async def fake_onchain(self, *, trace_id: str, chain: str, address: str):
        assert trace_id == "trace-route-001"
        return {
            "version": "1.0",
            "trace_id": trace_id,
            "chain": chain,
            "address": address,
            "quality": "UNAVAILABLE",
            "sources": [{"provider": "zwallet:test"}],
            "evidence": {},
        }

    monkeypatch.setattr(ZWalletProvider, "onchain_evidence", fake_onchain)
    client = TestClient(app)
    payload = {
        "trace_id": "trace-route-001",
        "token": {
            "symbol": "ABC",
            "chain": "ethereum",
            "address": "0x1111111111111111111111111111111111111111",
        },
    }
    assert client.post("/v1/integrations/zwallet/evidence", json=payload).status_code == 401
    response = client.post(
        "/v1/integrations/zwallet/evidence",
        json=payload,
        headers=_integration_headers(),
    )
    assert response.status_code == 200
    assert response.json()["trace_id"] == "trace-route-001"


def test_advisory_route_validates_scope_and_contract_before_forwarding(monkeypatch) -> None:
    monkeypatch.setenv("ZTRADER_INTEL_SERVICE_TOKEN", "inbound-service-key")

    async def fake_submit(self, intent: dict[str, object]):
        assert intent["signal_id"] == "signal-route-001"
        assert intent["proposed_trade"]["mode"] == "paper"  # type: ignore[index]
        return {
            "accepted": True,
            "execution_allowed": False,
            "risk_review_required": True,
            "signal_id": "signal-route-001",
            "canonical_executor": "zksato",
            "mode": "paper",
            "reason": "recorded",
        }

    monkeypatch.setattr(ZKsatoProvider, "submit_advisory", fake_submit)
    client = TestClient(app)
    headers = {
        **_integration_headers(),
        "X-Tenant-ID": "tenant-demo",
        "X-Account-Ref": "paper-account-1",
    }
    response = client.post(
        "/v1/integrations/zksato/advisory",
        json={"intent": _valid_advisory()},
        headers=headers,
    )
    assert response.status_code == 202
    assert response.json()["execution_allowed"] is False

    bad = _valid_advisory()
    bad["proposed_trade"] = {
        **bad["proposed_trade"],  # type: ignore[arg-type]
        "mode": "live",
    }
    assert (
        client.post(
            "/v1/integrations/zksato/advisory",
            json={"intent": bad},
            headers=headers,
        ).status_code
        == 422
    )

    wrong_scope = {**headers, "X-Tenant-ID": "other-tenant"}
    assert (
        client.post(
            "/v1/integrations/zksato/advisory",
            json={"intent": _valid_advisory()},
            headers=wrong_scope,
        ).status_code
        == 403
    )


def test_integration_http_errors_return_503(monkeypatch) -> None:
    monkeypatch.setenv("ZTRADER_INTEL_SERVICE_TOKEN", "inbound-service-key")

    async def fail_onchain(self, *, trace_id: str, chain: str, address: str):
        request = httpx.Request("POST", "http://zwallet.invalid")
        raise httpx.ConnectError("unavailable", request=request)

    monkeypatch.setattr(ZWalletProvider, "onchain_evidence", fail_onchain)
    client = TestClient(app)
    response = client.post(
        "/v1/integrations/zwallet/evidence",
        json={
            "trace_id": "trace-route-002",
            "token": {
                "symbol": "ABC",
                "chain": "ethereum",
                "address": "0x1111111111111111111111111111111111111111",
            },
        },
        headers=_integration_headers(),
    )
    assert response.status_code == 503
