from __future__ import annotations

import httpx
import pytest

from zeaz_provider.config import ProviderConfig
from zeaz_provider.errors import ErrorKind, ProviderError, classify_http_error
from zeaz_provider.providers import ProviderClient


def test_http_error_classification_separates_retry_and_fallback():
    missing = classify_http_error(404, "missing")
    assert not missing.retryable
    assert missing.fallback_allowed
    assert not missing.circuit_failure

    invalid = classify_http_error(400, "invalid")
    assert invalid.kind == ErrorKind.BAD_REQUEST
    assert not invalid.retryable
    assert not invalid.fallback_allowed

    limited = classify_http_error(429, "limited", retry_after=2)
    assert limited.kind == ErrorKind.RATE_LIMIT
    assert limited.retryable
    assert limited.fallback_allowed
    assert limited.retry_after == 2

    invalid_retry_after = classify_http_error(429, "limited", retry_after=float("nan"))
    assert invalid_retry_after.retry_after is None


@pytest.mark.asyncio
async def test_provider_retries_network_timeout_then_succeeds():
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json={"ok": True})

    config = ProviderConfig(
        name="test",
        api="openai",
        base_url="https://provider.example/v1",
        max_attempts=2,
        retry_base_seconds=0,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ProviderClient(config, http)
        assert await client.chat({"model": "test"}) == {"ok": True}
    assert calls == 2


@pytest.mark.asyncio
async def test_provider_does_not_retry_bad_request():
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"error": "invalid"})

    config = ProviderConfig(
        name="test",
        api="openai",
        base_url="https://provider.example/v1",
        max_attempts=3,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ProviderClient(config, http)
        with pytest.raises(ProviderError) as error:
            await client.chat({"model": "test"})
    assert error.value.kind == ErrorKind.BAD_REQUEST
    assert calls == 1


@pytest.mark.asyncio
async def test_provider_json_response_is_bounded_before_parsing():
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"data":"' + (b"x" * 2048) + b'"}')

    config = ProviderConfig(
        name="test",
        api="openai",
        base_url="https://provider.example/v1",
        max_attempts=1,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ProviderClient(config, http, max_response_bytes=1024)
        with pytest.raises(ProviderError, match="exceeded configured byte limit") as error:
            await client.chat({"model": "test"})
    assert error.value.kind == ErrorKind.PROTOCOL


@pytest.mark.asyncio
async def test_provider_stream_stops_before_exceeding_limit():
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"123456789")

    config = ProviderConfig(
        name="test",
        api="openai",
        base_url="https://provider.example/v1",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ProviderClient(config, http, max_response_bytes=8)
        with pytest.raises(ProviderError, match="exceeded configured byte limit"):
            await anext(client.stream("chat/completions", {"model": "test"}))
