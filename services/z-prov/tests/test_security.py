import hashlib
import json

import pytest
from redis.exceptions import ConnectionError

from zeaz_provider.audit import audit_method, audit_path, emit_request_audit
from zeaz_provider.security import (
    InMemoryRateLimiter,
    RateLimitBackendError,
    RedisRateLimiter,
    TrustedProxyPolicy,
    client_key_digest,
    redact,
    request_id,
    verify_client_key,
)


def test_redaction_and_request_id_validation():
    assert redact("token sk-secretsecretsecret value") == "token [REDACTED] value"
    assert request_id("safe-id.1") == "safe-id.1"
    generated = request_id("../../bad")
    assert len(generated) == 32
    assert generated.isalnum()


@pytest.mark.asyncio
async def test_rate_limiter_window_is_deterministic():
    now = [0.0]
    limiter = InMemoryRateLimiter(2, 60, clock=lambda: now[0])
    assert await limiter.allow("client") == (True, 1)
    assert await limiter.allow("client") == (True, 0)
    assert await limiter.allow("client") == (False, 0)
    now[0] = 61
    assert await limiter.allow("client") == (True, 1)


class FakeRedis:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []
        self.closed = False

    async def eval(self, *args):
        self.calls.append(args)
        if self.error:
            raise self.error
        return self.result

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_redis_rate_limiter_uses_atomic_script_and_hashed_bucket():
    redis = FakeRedis([1, 4])
    limiter = RedisRateLimiter(redis, 5, key_prefix="test:")
    assert await limiter.allow("hashed-bucket") == (True, 4)
    assert redis.calls[0][1:4] == (1, "test:hashed-bucket", 60000)
    await limiter.close()
    assert redis.closed


@pytest.mark.asyncio
async def test_redis_rate_limiter_fails_closed_without_leaking_connection_details():
    redis = FakeRedis(error=ConnectionError("redis://user:secret@example.invalid"))
    limiter = RedisRateLimiter(redis, 5)
    with pytest.raises(RateLimitBackendError) as error:
        await limiter.allow("bucket")
    assert "secret" not in str(error.value)


def test_forwarded_ip_is_ignored_without_explicitly_trusted_proxy():
    policy = TrustedProxyPolicy()
    assert policy.client_ip("198.51.100.10", "203.0.113.5") == "198.51.100.10"


def test_cloudflare_ip_is_accepted_only_from_matching_direct_peer():
    policy = TrustedProxyPolicy.from_cidrs(("192.0.2.0/24", "2001:db8::/32"))
    assert policy.client_ip("192.0.2.10", "203.0.113.5") == "203.0.113.5"
    assert policy.client_ip("2001:db8::10", "2001:db8:ffff::5") == "2001:db8:ffff::5"
    assert policy.client_ip("198.51.100.10", "203.0.113.5") == "198.51.100.10"


def test_malformed_or_multiple_forwarded_ips_fall_back_to_direct_peer():
    policy = TrustedProxyPolicy.from_cidrs(("192.0.2.0/24",))
    assert policy.client_ip("192.0.2.10", "not-an-ip") == "192.0.2.10"
    assert policy.client_ip("192.0.2.10", "203.0.113.5, 198.51.100.2") == "192.0.2.10"


def test_client_key_verification_uses_hashes():
    configured = frozenset({client_key_digest("correct-key"), client_key_digest("another-key")})
    assert verify_client_key("correct-key", configured)
    assert not verify_client_key("wrong-key", configured)
    assert not verify_client_key("", configured)


def test_client_key_verification_compares_every_configured_hash(monkeypatch):
    calls: list[bytes] = []

    def compare(left, right):
        calls.append(right)
        return hashlib.sha256(b"correct-key").digest() == right

    monkeypatch.setattr("zeaz_provider.security.hmac.compare_digest", compare)
    configured = frozenset({b"a" * 32, b"b" * 32, b"c" * 32})
    verify_client_key("correct-key", configured)
    assert len(calls) == len(configured)


def test_audit_event_has_allowlisted_metadata_only(caplog):
    caplog.set_level("INFO", logger="uvicorn.error")
    emit_request_audit(
        request_id="request-1",
        method="POST",
        path="/v1/messages",
        status_code=200,
        duration_ms=1.23456,
        client_id="hashed-client",
        rate_limited=False,
    )

    event = json.loads(caplog.records[-1].message)
    assert event.keys() == {
        "schema_version",
        "timestamp",
        "event",
        "request_id",
        "method",
        "path",
        "status_code",
        "duration_ms",
        "client_id",
        "rate_limited",
    }
    assert event["path"] == "/v1/messages"
    assert event["duration_ms"] == 1.235
    assert event["request_id"] != "request-1"


def test_audit_path_does_not_log_unknown_user_input():
    assert audit_path("/v1/messages") == "/v1/messages"
    assert audit_path("/secret-in-path?token=credential") == "unmatched"
    assert audit_method("POST") == "POST"
    assert audit_method("secret-in-method") == "OTHER"


def test_audit_hashes_client_supplied_request_id(caplog):
    secret_request_id = "credential-in-request-id"
    caplog.set_level("INFO", logger="uvicorn.error")
    emit_request_audit(
        request_id=secret_request_id,
        method="GET",
        path="/health/live",
        status_code=200,
        duration_ms=0,
        client_id="hashed-client",
        rate_limited=False,
    )
    assert secret_request_id not in caplog.records[-1].message
