import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from zeaz_enterprise.wif import (
    AnthropicWIFConfig,
    AnthropicWIFExchange,
    WIFExchangeError,
)

ASSERTION = "header.payload.signature"
ACCESS_TOKEN = "sk-ant-oat01-short-lived-test-token"
ORG_UUID = "abcdef01-2345-6789-abcd-ef0123456789"


def config(**changes) -> AnthropicWIFConfig:
    values = {
        "federation_rule_id": "fdrl_rule1",
        "organization_id": ORG_UUID,
        "service_account_id": "svac_account1",
        "workspace_id": "wrkspc_workspace1",
    }
    values.update(changes)
    return AnthropicWIFConfig(**values)


def response(**changes) -> dict:
    values = {
        "access_token": ACCESS_TOKEN,
        "token_type": "Bearer",
        "expires_in": 600,
        "scope": "workspace:inference",
    }
    values.update(changes)
    return values


def exchange(handler, provider=None, **changes) -> AnthropicWIFExchange:
    async def default_provider() -> SecretStr:
        return SecretStr(ASSERTION)

    values = {
        "config": config(),
        "identity_token_provider": provider or default_provider,
        "client": httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            trust_env=False,
        ),
        "clock": lambda: datetime(2026, 7, 26, tzinfo=UTC),
    }
    values.update(changes)
    return AnthropicWIFExchange(**values)


@pytest.mark.asyncio
async def test_exchange_uses_rfc7523_body_and_returns_secret_credential() -> None:
    seen: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen = request
        return httpx.Response(200, json=response())

    client = exchange(handler)
    result = await client.credential()
    assert seen is not None
    assert seen.url.path == "/v1/oauth/token"
    assert "authorization" not in seen.headers
    assert json.loads(seen.content) == {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": ASSERTION,
        "federation_rule_id": "fdrl_rule1",
        "organization_id": ORG_UUID,
        "service_account_id": "svac_account1",
        "workspace_id": "wrkspc_workspace1",
    }
    assert result.authorization_header() == f"Bearer {ACCESS_TOKEN}"
    assert ACCESS_TOKEN not in repr(result)
    assert ASSERTION not in repr(vars(client))
    await client.aclose()


@pytest.mark.asyncio
async def test_default_workspace_is_sent_and_omitted_workspace_stays_absent() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=response())

    for workspace_id in ("default", None):
        client = exchange(handler, config=config(workspace_id=workspace_id))
        await client.credential()
        await client.aclose()
    assert bodies[0]["workspace_id"] == "default"
    assert "workspace_id" not in bodies[1]


@pytest.mark.asyncio
async def test_cached_token_avoids_reusing_upstream_assertion() -> None:
    exchanges = 0
    provisions = 0

    async def provider() -> SecretStr:
        nonlocal provisions
        provisions += 1
        return SecretStr(ASSERTION)

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal exchanges
        exchanges += 1
        return httpx.Response(200, json=response())

    client = exchange(handler, provider)
    first = await client.credential()
    second = await client.credential()
    assert first is second
    assert exchanges == provisions == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_concurrent_refresh_is_single_flight() -> None:
    exchanges = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal exchanges
        exchanges += 1
        return httpx.Response(200, json=response())

    client = exchange(handler)
    results = await asyncio.gather(*(client.credential() for _ in range(20)))
    assert len({item.access_token.get_secret_value() for item in results}) == 1
    assert exchanges == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_refresh_margin_causes_expiring_token_to_be_reexchanged() -> None:
    exchanges = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal exchanges
        exchanges += 1
        return httpx.Response(200, json=response(expires_in=30))

    client = exchange(handler, refresh_margin_seconds=30)
    await client.credential()
    await client.credential()
    assert exchanges == 2
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_response",
    (
        response(token_type="bearer"),
        response(expires_in=True),
        response(expires_in=86401),
        response(access_token="ordinary-token"),
        response(scope="invalid scope"),
        {**response(), "extra": True},
    ),
)
async def test_invalid_token_responses_fail_closed(bad_response: dict) -> None:
    client = exchange(lambda _: httpx.Response(200, json=bad_response))
    with pytest.raises(WIFExchangeError, match="invalid response"):
        await client.credential()
    await client.aclose()


@pytest.mark.asyncio
async def test_bad_assertion_and_provider_failure_are_sanitized() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    async def bad_type():  # type intentionally violates the contract
        return ASSERTION

    async def failed() -> SecretStr:
        raise RuntimeError("upstream-token-secret")

    for provider in (bad_type, failed):
        client = exchange(handler, provider)
        with pytest.raises(WIFExchangeError) as raised:
            await client.credential()
        assert ASSERTION not in str(raised.value)
        assert "upstream-token-secret" not in str(raised.value)
        await client.aclose()
    assert calls == 0


@pytest.mark.asyncio
async def test_redirect_size_and_provider_errors_are_sanitized() -> None:
    cases = [
        (lambda _: httpx.Response(302, headers={"location": "https://elsewhere"}), "redirect"),
        (lambda _: httpx.Response(400, text="invalid secret assertion"), "HTTP 400"),
    ]
    for handler, message in cases:
        client = exchange(handler)
        with pytest.raises(WIFExchangeError, match=message) as raised:
            await client.credential()
        assert "invalid secret assertion" not in str(raised.value)
        await client.aclose()

    client = exchange(
        lambda _: httpx.Response(200, content=b"{" + b"x" * 2048),
        max_response_bytes=1024,
    )
    with pytest.raises(WIFExchangeError, match="byte limit"):
        await client.credential()
    await client.aclose()


def test_configuration_is_closed_and_role_identifiers_are_validated() -> None:
    with pytest.raises(ValidationError):
        config(federation_rule_id="wrong")
    with pytest.raises(ValidationError):
        config(workspace_id="other")
    with pytest.raises(ValidationError):
        AnthropicWIFConfig(
            federation_rule_id="fdrl_rule1",
            organization_id=ORG_UUID,
            service_account_id="svac_account1",
            extra=True,
        )
    with pytest.raises(TypeError, match="configuration"):
        AnthropicWIFExchange(  # type: ignore[arg-type]
            {"federation_rule_id": "fdrl_rule1"},
            lambda: None,  # type: ignore[arg-type]
        )
