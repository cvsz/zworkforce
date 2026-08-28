from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient
from prometheus_client import REGISTRY


ROOT = Path(__file__).resolve().parents[3]
APP_PATH = ROOT / "services" / "phase6-api" / "app.py"


def load_app(monkeypatch):
    for collector in list(REGISTRY._collector_to_names):
        REGISTRY.unregister(collector)
    monkeypatch.setenv("PHASE6_API_TOKEN", "token")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("Z_PLATFORM_RELEASE_SHA", "a" * 40)
    monkeypatch.setenv(
        "AI_PROVIDER_ENDPOINTS",
        json.dumps({
            "primary": {"baseUrl": "https://primary.example/v1", "model": "model-a"},
            "secondary": {"baseUrl": "https://secondary.example/v1", "model": "model-b"},
        }),
    )
    monkeypatch.setenv("AI_PROVIDER_KEYS_JSON", json.dumps({"primary": "primary-secret-key", "secondary": "secondary-secret-key"}))
    spec = importlib.util.spec_from_file_location("phase6_external_ai_app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_liveness_exposes_the_immutable_release_identity(monkeypatch):
    module = load_app(monkeypatch)
    response = TestClient(module.app).get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive", "service": "phase6-api", "release_sha": "a" * 40}


def test_upload_is_bounded_and_processed_by_an_external_provider(monkeypatch):
    module = load_app(monkeypatch)
    observed = {}

    async def fake_call(prompt, skip_primary=False):
        observed.update(prompt=prompt, skip_primary=skip_primary)
        return {"provider": "primary", "upstreamStatus": 200, "requestId": "upload-request-1", "failures": [], "failover": False}

    module.call_any_provider = fake_call
    response = TestClient(module.app).post(
        "/ai/upload",
        headers={"Authorization": "Bearer token"},
        files={"file": ("evidence.txt", b"external upload evidence", "text/plain")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "verified"
    assert payload["provider"] == "primary"
    assert payload["upstreamStatus"] == 200
    assert payload["requestId"] == "upload-request-1"
    assert payload["size"] == len(b"external upload evidence")
    assert len(payload["sha256"]) == 64
    assert "Filename: evidence.txt" in observed["prompt"]


def test_upload_rejects_content_over_the_runtime_bound(monkeypatch):
    module = load_app(monkeypatch)
    module.MAX_AI_UPLOAD_BYTES = 4
    response = TestClient(module.app).post(
        "/ai/upload",
        headers={"Authorization": "Bearer token"},
        files={"file": ("large.bin", b"12345", "application/octet-stream")},
    )
    assert response.status_code == 413


def test_failover_uses_the_secondary_external_provider(monkeypatch):
    module = load_app(monkeypatch)

    async def fake_provider(name, prompt):
        assert prompt
        return {"provider": name, "upstreamStatus": 200, "response": {"id": "request-1"}}

    module.call_provider = fake_provider
    response = TestClient(module.app).post(
        "/ai/failover",
        headers={"Authorization": "Bearer token"},
        json={"prompt": "verify failover", "forcePrimaryFailure": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "verified"
    assert payload["selected"] == "secondary"
    assert payload["failover"] is True


def test_multi_provider_verification_calls_every_provider(monkeypatch):
    module = load_app(monkeypatch)
    called = []

    async def fake_provider(name, prompt):
        called.append(name)
        return {"provider": name, "upstreamStatus": 200, "requestId": f"request-{name}", "response": {}}

    module.call_provider = fake_provider
    response = TestClient(module.app).post(
        "/ai/providers/verify",
        headers={"Authorization": "Bearer token"},
        json={"prompt": "verify all providers"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "verified"
    assert called == ["primary", "secondary"]


def test_stream_forwards_upstream_chunks_and_closes_connections(monkeypatch):
    module = load_app(monkeypatch)

    class FakeResponse:
        async def aiter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"verified"}}]}'
            yield "data: [DONE]"

    class FakeContext:
        closed = False

        async def __aexit__(self, *_args):
            self.closed = True

    class FakeClient:
        closed = False

        async def aclose(self):
            self.closed = True

    context = FakeContext()
    client = FakeClient()

    async def fake_open(prompt):
        assert prompt
        return "primary", [], "stream-request-1", client, context, FakeResponse()

    module.open_provider_stream = fake_open
    response = TestClient(module.app).get("/ai/stream", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert "event: upstream" in response.text
    assert '"status": "verified"' in response.text
    assert '"provider": "primary"' in response.text
    assert '"requestId": "stream-request-1"' in response.text
    assert context.closed is True
    assert client.closed is True
