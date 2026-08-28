import httpx
import pytest

from zeaz_provider.capabilities import CapabilityRecord, ModelLifecycle
from zeaz_provider.config import ModelRoute, ProviderConfig, RouteTarget, Settings
from zeaz_provider.providers import ProviderError
from zeaz_provider.router import ProviderRouter


@pytest.fixture
def gateway():
    settings = Settings(
        providers={"local": ProviderConfig(name="local", api="openai", base_url="http://local/v1")},
        models={
            "alias": ModelRoute(
                alias="alias",
                primary=RouteTarget(provider="local", model="backend"),
            )
        },
        client_key_hashes=frozenset(),
        default_model="alias",
    )
    return ProviderRouter(settings, httpx.AsyncClient(trust_env=False))


def test_model_alias(gateway):
    assert gateway.route("alias").primary.model == "backend"


def test_unknown_model(gateway):
    with pytest.raises(ProviderError) as error:
        gateway.route("missing")
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_fallback_uses_provider_specific_model():
    settings = Settings(
        providers={
            "primary": ProviderConfig(name="primary", api="openai", base_url="http://primary/v1"),
            "free": ProviderConfig(name="free", api="openai", base_url="http://free/v1"),
        },
        models={
            "zeaz-free": ModelRoute(
                alias="zeaz-free",
                primary=RouteTarget(provider="primary", model="local-model"),
                fallbacks=(RouteTarget(provider="free", model="cloud-free-model"),),
            )
        },
        client_key_hashes=frozenset(),
        default_model="zeaz-free",
    )
    gateway = ProviderRouter(settings, httpx.AsyncClient(trust_env=False))
    seen = []

    async def operation(client, model):
        seen.append((client.config.name, model))
        if client.config.name == "primary":
            raise ProviderError("model unavailable", 404, retryable=True)
        return "ok"

    assert await gateway.execute(gateway.route("zeaz-free"), operation) == "ok"
    assert seen == [
        ("primary", "local-model"),
        ("free", "cloud-free-model"),
    ]


@pytest.mark.asyncio
async def test_stream_falls_back_only_before_first_byte():
    settings = Settings(
        providers={
            "primary": ProviderConfig(name="primary", api="openai", base_url="http://primary/v1"),
            "free": ProviderConfig(name="free", api="openai", base_url="http://free/v1"),
        },
        models={
            "zeaz-free": ModelRoute(
                alias="zeaz-free",
                primary=RouteTarget(provider="primary", model="local-model"),
                fallbacks=(RouteTarget(provider="free", model="cloud-free-model"),),
            )
        },
        client_key_hashes=frozenset(),
        default_model="zeaz-free",
    )
    gateway = ProviderRouter(settings, httpx.AsyncClient(trust_env=False))
    seen = []

    async def operation(client, model):
        seen.append((client.config.name, model))
        if client.config.name == "primary":
            raise ProviderError("unavailable", 503, fallback_allowed=True)
        yield b"data: ok\n\n"

    assert [chunk async for chunk in gateway.stream(gateway.route("zeaz-free"), operation)] == [
        b"data: ok\n\n"
    ]
    assert seen == [
        ("primary", "local-model"),
        ("free", "cloud-free-model"),
    ]


@pytest.mark.asyncio
async def test_stream_does_not_replay_after_first_byte():
    settings = Settings(
        providers={
            "primary": ProviderConfig(name="primary", api="openai", base_url="http://primary/v1"),
            "free": ProviderConfig(name="free", api="openai", base_url="http://free/v1"),
        },
        models={
            "zeaz-free": ModelRoute(
                alias="zeaz-free",
                primary=RouteTarget(provider="primary", model="local-model"),
                fallbacks=(RouteTarget(provider="free", model="cloud-free-model"),),
            )
        },
        client_key_hashes=frozenset(),
        default_model="zeaz-free",
    )
    gateway = ProviderRouter(settings, httpx.AsyncClient(trust_env=False))

    async def operation(client, _model):
        if client.config.name == "primary":
            yield b"data: partial\n\n"
            raise ProviderError("disconnected", 503, fallback_allowed=True)
        yield b"data: duplicate\n\n"

    stream = gateway.stream(gateway.route("zeaz-free"), operation)
    assert await anext(stream) == b"data: partial\n\n"
    with pytest.raises(ProviderError):
        await anext(stream)


def test_alias_resolution_skips_confirmed_retired_primary():
    settings = Settings(
        providers={
            "old": ProviderConfig(name="old", api="openai", base_url="http://old/v1"),
            "new": ProviderConfig(name="new", api="openai", base_url="http://new/v1"),
        },
        models={
            "zeaz-auto": ModelRoute(
                alias="zeaz-auto",
                primary=RouteTarget(provider="old", model="retired-model"),
                fallbacks=(RouteTarget(provider="new", model="active-model"),),
            )
        },
        client_key_hashes=frozenset(),
        default_model="zeaz-auto",
    )
    gateway = ProviderRouter(settings, httpx.AsyncClient(trust_env=False))
    gateway.capabilities._records[("old", "retired-model")] = CapabilityRecord(
        provider="old",
        model="retired-model",
        lifecycle=ModelLifecycle.RETIRED,
        source="provider_models_api",
    )
    assert gateway.route("zeaz-auto").primary == RouteTarget(
        provider="new",
        model="active-model",
    )
