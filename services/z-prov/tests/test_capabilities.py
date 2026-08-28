from __future__ import annotations

import httpx
import pytest

from zeaz_provider.capabilities import CapabilityRegistry, ModelLifecycle
from zeaz_provider.config import (
    ModelRoute,
    ProviderConfig,
    RouteTarget,
    Settings,
)
from zeaz_provider.providers import ProviderClient


def _settings() -> Settings:
    return Settings(
        providers={
            "anthropic": ProviderConfig(
                name="anthropic",
                api="anthropic",
                base_url="https://api.anthropic.test/v1",
            )
        },
        models={
            "zeaz-claude": ModelRoute(
                alias="zeaz-claude",
                primary=RouteTarget(provider="anthropic", model="claude-current"),
            )
        },
        client_key_hashes=frozenset(),
        default_model="zeaz-claude",
    )


def test_registry_seeds_conservative_config_records():
    registry = CapabilityRegistry(_settings())
    record = registry.get("anthropic", "claude-current")
    assert record is not None
    assert record.lifecycle == ModelLifecycle.UNKNOWN
    assert record.capabilities.tools is None


@pytest.mark.asyncio
async def test_live_refresh_records_provenance_ttl_and_known_fields():
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "data": [{
                "id": "claude-live",
                "status": "active",
                "max_input_tokens": 1_000_000,
                "max_tokens": 128_000,
                "capabilities": {
                    "tools": True,
                    "vision": True,
                    "mid_conversation_system": True,
                },
            }]
        })

    settings = _settings()
    registry = CapabilityRegistry(settings, ttl_seconds=60, clock=lambda: 100.0)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ProviderClient(settings.providers["anthropic"], http)
        assert await registry.refresh_provider("anthropic", client) == 1

    record = registry.get("anthropic", "claude-live")
    assert record is not None
    assert record.source == "provider_models_api"
    assert record.observed_at == 100
    assert record.expires_at == 160
    assert record.capabilities.context_window == 1_000_000
    assert record.capabilities.mid_conversation_system is True
    assert record.account == "default"
    assert record.region == "global"


@pytest.mark.asyncio
async def test_expired_live_record_falls_back_to_conservative_configuration():
    now = [100.0]

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "data": [{
                "id": "claude-current",
                "status": "active",
                "capabilities": {"tools": True},
            }]
        })

    settings = _settings()
    registry = CapabilityRegistry(settings, ttl_seconds=10, clock=lambda: now[0])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ProviderClient(settings.providers["anthropic"], http)
        await registry.refresh_provider("anthropic", client)
    assert registry.get("anthropic", "claude-current").capabilities.tools is True

    now[0] = 111
    expired = registry.get("anthropic", "claude-current")
    assert expired is not None
    assert expired.source == "configuration"
    assert expired.capabilities.tools is None
