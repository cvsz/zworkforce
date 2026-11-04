import asyncio

from ztrader_intel.events import EventBus
from ztrader_intel.models import (
    Action,
    IntelligenceResponse,
    NarrativeStage,
    RugRisk,
    Scores,
    TokenRef,
    WatchlistEntry,
    WhaleState,
)
from ztrader_intel.store import AnalysisStore


def _sample_response(symbol: str = "ABC") -> IntelligenceResponse:
    return IntelligenceResponse(
        token=TokenRef(symbol=symbol, chain="base", address="0x1"),
        narrative=NarrativeStage.HEATING_UP,
        whales=WhaleState.NEUTRAL,
        rug_risk=RugRisk.MEDIUM,
        action=Action.WAIT,
        scores=Scores(opportunity=50, risk=40, confidence=60),
        reasons=[],
        red_flags=[],
        invalidations=[],
        watch_next=[],
    )


def test_store_history_and_watchlist(tmp_path):
    store = AnalysisStore(str(tmp_path / "intel.db"))
    response = _sample_response("ABC")
    store.save(response)
    assert len(store.history("ABC")) == 1

    store.upsert_watchlist(WatchlistEntry(token=response.token, note="watch"))
    items = store.list_watchlist()
    assert len(items) == 1
    assert items[0].note == "watch"


def test_store_isolates_history_and_watchlist_by_tenant(tmp_path):
    store = AnalysisStore(str(tmp_path / "intel_tenant.db"))
    response_alpha = _sample_response("ABC")
    store.save(response_alpha, tenant_id="tenant-alpha")

    assert len(store.history("ABC", tenant_id="tenant-alpha")) == 1
    assert len(store.history("ABC", tenant_id="tenant-beta")) == 0

    store.upsert_watchlist(
        WatchlistEntry(token=response_alpha.token, note="alpha-note"),
        tenant_id="tenant-alpha",
    )
    store.upsert_watchlist(
        WatchlistEntry(token=response_alpha.token, note="beta-note"),
        tenant_id="tenant-beta",
    )

    alpha_items = store.list_watchlist(tenant_id="tenant-alpha")
    beta_items = store.list_watchlist(tenant_id="tenant-beta")
    assert len(alpha_items) == 1
    assert alpha_items[0].note == "alpha-note"
    assert len(beta_items) == 1
    assert beta_items[0].note == "beta-note"


def test_event_bus_isolates_sse_streams_by_tenant():
    async def _run():
        bus = EventBus()
        alpha_gen = bus.stream(tenant_id="tenant-alpha")
        beta_gen = bus.stream(tenant_id="tenant-beta")

        alpha_task = asyncio.create_task(alpha_gen.__anext__())
        beta_task = asyncio.create_task(beta_gen.__anext__())
        await asyncio.sleep(0)

        await bus.publish('{"tenant":"alpha"}', tenant_id="tenant-alpha")
        msg = await asyncio.wait_for(alpha_task, timeout=1.0)
        assert msg == '{"tenant":"alpha"}'
        assert not beta_task.done()

        beta_task.cancel()
        try:
            await beta_task
        except asyncio.CancelledError:
            pass
        await alpha_gen.aclose()
        await beta_gen.aclose()

    asyncio.run(_run())


def test_api_tenant_isolation_and_optional_auth_enforcement(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from ztrader_intel import api

    test_store = AnalysisStore(str(tmp_path / "api_intel.db"))
    monkeypatch.setattr(api, "store", test_store)

    client = TestClient(api.app)
    entry_payload = {
        "token": {"symbol": "ZWF", "chain": "base", "address": "0xabc"},
        "note": "alpha-secret-watch",
    }

    res_a = client.post(
        "/v1/watchlist",
        json=entry_payload,
        headers={"X-Tenant-ID": "tenant-alpha"},
    )
    assert res_a.status_code == 200

    list_a = client.get("/v1/watchlist", headers={"X-Tenant-ID": "tenant-alpha"})
    list_b = client.get("/v1/watchlist", headers={"X-Tenant-ID": "tenant-beta"})
    assert list_a.status_code == 200
    assert len(list_a.json()) == 1
    assert list_b.status_code == 200
    assert list_b.json() == []

    bad_tenant = client.get("/v1/watchlist", headers={"X-Tenant-ID": "../bad-tenant"})
    assert bad_tenant.status_code == 400

    monkeypatch.setenv("ZTRADER_REQUIRE_AUTH", "true")
    monkeypatch.setenv("ZTRADER_INTEL_SERVICE_TOKEN", "ztrader-service-secret-123")

    unauth = client.get("/v1/watchlist", headers={"X-Tenant-ID": "tenant-alpha"})
    assert unauth.status_code == 401

    missing_tenant = client.get(
        "/v1/watchlist",
        headers={"X-API-Key": "ztrader-service-secret-123"},
    )
    assert missing_tenant.status_code == 400

    authed = client.get(
        "/v1/watchlist",
        headers={
            "X-API-Key": "ztrader-service-secret-123",
            "X-Tenant-ID": "tenant-alpha",
        },
    )
    assert authed.status_code == 200
    assert len(authed.json()) == 1
