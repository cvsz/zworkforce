import hashlib
import json

from fastapi.testclient import TestClient

from zeaz_provider.main import app
from zeaz_provider.security import RateLimitBackendError


def test_health_and_authenticated_models(monkeypatch):
    monkeypatch.setenv("ZEAZ_CONFIG", "config/providers.example.yaml")
    monkeypatch.setenv("ZEAZ_CLIENT_KEYS", "test-client-key")
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").json()["status"] == "ready"
        assert client.get("/v1/models").status_code == 401
        response = client.get(
            "/v1/models",
            headers={"Authorization": "Bearer test-client-key"},
        )
        assert response.status_code == 200
        assert "zeaz-codex" in {item["id"] for item in response.json()["data"]}


def test_model_discovery_exposes_aliases_only(monkeypatch):
    monkeypatch.setenv("ZEAZ_CONFIG", "config/providers.example.yaml")
    monkeypatch.setenv("ZEAZ_CLIENT_KEYS", "test-client-key")
    with TestClient(app) as client:
        response = client.get(
            "/v1/models",
            headers={"Authorization": "bearer test-client-key"},
        )
    assert response.status_code == 200
    body = response.json()
    assert all(set(item) == {"id", "object", "owned_by"} for item in body["data"])
    assert all(item["owned_by"] == "zeaz" for item in body["data"])
    assert "qwen3:8b" not in response.text
    assert "fallbacks" not in response.text


def test_invalid_json_is_rejected_before_provider_call(monkeypatch):
    monkeypatch.setenv("ZEAZ_CONFIG", "config/providers.example.yaml")
    monkeypatch.setenv("ZEAZ_CLIENT_KEYS", "test-client-key")
    with TestClient(app) as client:
        response = client.post(
            "/v1/messages",
            content=b"{",
            headers={
                "content-type": "application/json",
                "x-api-key": "test-client-key",
            },
        )
        assert response.status_code == 400


def test_invalid_protocol_conversion_is_rejected_as_bad_request(monkeypatch):
    monkeypatch.setenv("ZEAZ_CONFIG", "config/providers.example.yaml")
    monkeypatch.setenv("ZEAZ_CLIENT_KEYS", "test-client-key")
    with TestClient(app) as client:
        response = client.post(
            "/v1/messages",
            json={
                "model": "zeaz-local",
                "messages": [{"role": "user", "content": [{"type": "image", "source": "invalid"}]}],
            },
            headers={"x-api-key": "test-client-key"},
        )
    assert response.status_code == 400


def test_request_boundary_adds_safe_headers_and_preserves_valid_request_id(monkeypatch):
    monkeypatch.setenv("ZEAZ_CONFIG", "config/providers.example.yaml")
    monkeypatch.setenv("ZEAZ_CLIENT_KEYS", "test-client-key")
    with TestClient(app) as client:
        response = client.get(
            "/health/live",
            headers={"X-Request-ID": "trace-123"},
        )
    assert response.headers["x-request-id"] == "trace-123"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


def test_request_audit_excludes_credentials_and_body(monkeypatch, caplog):
    client_key = "test-client-key-never-log"
    prompt = "prompt-content-never-log"
    monkeypatch.setenv("ZEAZ_CONFIG", "config/providers.example.yaml")
    monkeypatch.setenv("ZEAZ_CLIENT_KEYS", client_key)
    caplog.set_level("INFO", logger="uvicorn.error")

    with TestClient(app) as client:
        response = client.post(
            "/v1/messages",
            content=json.dumps({"model": "zeaz-local", "messages": prompt, "max_tokens": 0}),
            headers={"x-api-key": client_key},
        )

    assert response.status_code == 400
    audit_record = caplog.records[-1].message
    event = json.loads(audit_record)
    assert event["status_code"] == 400
    assert event["path"] == "/v1/messages"
    assert client_key not in audit_record
    assert prompt not in audit_record


def test_prometheus_endpoint_exposes_request_metrics(monkeypatch):
    monkeypatch.setenv("ZEAZ_CONFIG", "config/providers.example.yaml")
    monkeypatch.setenv("ZEAZ_CLIENT_KEYS", "test-client-key")
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        response = client.get("/metrics")

    assert response.status_code == 200
    assert 'zeaz_http_requests_total{method="GET",path="/health/live",status="200"} 1.0' in response.text
    assert "test-client-key" not in response.text


def test_prometheus_endpoint_can_be_disabled(monkeypatch):
    monkeypatch.setenv("ZEAZ_CONFIG", "config/providers.example.yaml")
    monkeypatch.setenv("ZEAZ_CLIENT_KEYS", "test-client-key")
    monkeypatch.setenv("ZEAZ_METRICS_ENABLED", "false")
    with TestClient(app) as client:
        assert client.get("/metrics").status_code == 404


def test_rate_limit_backend_failure_returns_safe_503(monkeypatch):
    class FailingBackend:
        async def allow(self, _bucket):
            raise RateLimitBackendError("redis://user:secret@internal")

        async def close(self):
            return None

    monkeypatch.setenv("ZEAZ_CONFIG", "config/providers.example.yaml")
    monkeypatch.setenv("ZEAZ_CLIENT_KEYS", "test-client-key")
    with TestClient(app) as client:
        client.app.state.rate_limiter = FailingBackend()
        response = client.get("/health/live")

    assert response.status_code == 503
    assert response.json()["error"]["message"] == "Rate-limit service unavailable"
    assert "secret" not in response.text


def test_trusted_cloudflare_peer_uses_forwarded_ip_for_rate_limit(monkeypatch):
    monkeypatch.setenv("ZEAZ_CONFIG", "config/providers.example.yaml")
    monkeypatch.setenv("ZEAZ_RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setenv("ZEAZ_TRUSTED_PROXY_CIDRS", "192.0.2.0/24")
    with TestClient(app, client=("192.0.2.10", 50000)) as client:
        first = client.get("/health/live", headers={"CF-Connecting-IP": "203.0.113.1"})
        second = client.get("/health/live", headers={"CF-Connecting-IP": "203.0.113.2"})
    assert first.status_code == 200
    assert second.status_code == 200


def test_untrusted_peer_cannot_spoof_rate_limit_identity(monkeypatch):
    monkeypatch.setenv("ZEAZ_CONFIG", "config/providers.example.yaml")
    monkeypatch.setenv("ZEAZ_RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.delenv("ZEAZ_TRUSTED_PROXY_CIDRS", raising=False)
    with TestClient(app, client=("192.0.2.10", 50000)) as client:
        first = client.get("/health/live", headers={"CF-Connecting-IP": "203.0.113.1"})
        second = client.get("/health/live", headers={"CF-Connecting-IP": "203.0.113.2"})
    assert first.status_code == 200
    assert second.status_code == 429


def test_hashed_client_key_authentication(monkeypatch):
    key = "high-entropy-test-client-key"
    digest = hashlib.sha256(key.encode()).hexdigest()
    monkeypatch.setenv("ZEAZ_CONFIG", "config/providers.example.yaml")
    monkeypatch.delenv("ZEAZ_CLIENT_KEYS", raising=False)
    monkeypatch.setenv("ZEAZ_CLIENT_KEY_HASHES", f"sha256:{digest}")
    with TestClient(app) as client:
        assert client.get("/v1/models", headers={"x-api-key": key}).status_code == 200
        assert client.get("/v1/models", headers={"x-api-key": "wrong"}).status_code == 401


def test_concurrency_rejection_is_safe_and_does_not_release_unacquired_slot(monkeypatch):
    class RejectingLimiter:
        async def try_acquire(self):
            return False

        async def release(self):
            raise AssertionError("unacquired slot must not be released")

    monkeypatch.setenv("ZEAZ_CONFIG", "config/providers.example.yaml")
    monkeypatch.setenv("ZEAZ_CLIENT_KEYS", "test-client-key")
    with TestClient(app) as client:
        client.app.state.concurrency_limiter = RejectingLimiter()
        response = client.get("/health/live")

    assert response.status_code == 503
    assert response.headers["retry-after"] == "1"
    assert response.json()["error"]["message"] == "Request concurrency limit exceeded"


def test_concurrency_slot_is_released_after_response(monkeypatch):
    monkeypatch.setenv("ZEAZ_CONFIG", "config/providers.example.yaml")
    monkeypatch.setenv("ZEAZ_CLIENT_KEYS", "test-client-key")
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.app.state.concurrency_limiter.active == 0


def test_large_non_streaming_gateway_response_returns_bounded_error(monkeypatch):
    monkeypatch.setenv("ZEAZ_CONFIG", "config/providers.example.yaml")
    monkeypatch.setenv("ZEAZ_CLIENT_KEYS", "test-client-key")
    monkeypatch.setenv("ZEAZ_MAX_RESPONSE_BYTES", "1024")
    with TestClient(app) as client:
        response = client.get("/v1/models", headers={"x-api-key": "test-client-key"})

    assert response.status_code == 502
    assert len(response.content) <= 1024
    assert response.json()["error"]["type"] == "response_limit_error"
