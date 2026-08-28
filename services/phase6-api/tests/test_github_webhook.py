import asyncio
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path

from fastapi import HTTPException
import pytest
from prometheus_client import REGISTRY


ROOT = Path(__file__).resolve().parents[3]
APP_PATH = ROOT / "services" / "phase6-api" / "app.py"


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def ping(self) -> bool:
        return True

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value

    async def get(self, key: str) -> str | None:
        return self.values.get(key)


class FakeRequest:
    def __init__(self, body: bytes, headers: dict[str, str]) -> None:
        self._body = body
        self.headers = headers

    async def body(self) -> bytes:
        return self._body


def load_app(monkeypatch, secret: str = "test-secret"):
    for collector in list(REGISTRY._collector_to_names):
        REGISTRY.unregister(collector)
    monkeypatch.setenv("PHASE6_API_TOKEN", "token")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("AI_PROVIDER_ENDPOINTS", "{}")
    monkeypatch.setenv("AI_PROVIDER_KEYS_JSON", "{}")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", secret)
    spec = importlib.util.spec_from_file_location("phase6_api_app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    module.r = FakeRedis()
    return module


def sign(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def call_webhook(module, body: bytes, headers: dict[str, str]):
    request = FakeRequest(body, headers)
    return asyncio.run(module.github_webhook(request))


def test_github_webhook_verifies_signature_and_records_delivery(monkeypatch):
    module = load_app(monkeypatch)
    body = json.dumps({
        "action": "opened",
        "repository": {"full_name": "cvsz/z-platform"},
    }).encode("utf-8")

    payload = call_webhook(
        module,
        body,
        {
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": "delivery-123",
            "X-Hub-Signature-256": sign("test-secret", body),
        },
    )

    assert payload["status"] == "verified"
    assert payload["delivery"] == "delivery-123"
    assert payload["event"] == "issues"
    assert payload["repository"] == "cvsz/z-platform"
    assert module.r.values["github:webhook:delivery-123"]


def test_github_webhook_rejects_missing_secret(monkeypatch):
    module = load_app(monkeypatch, secret="")

    with pytest.raises(HTTPException) as excinfo:
        call_webhook(
            module,
            b"{}",
            {"X-Hub-Signature-256": "sha256=deadbeef"},
        )

    assert excinfo.value.status_code == 503
    assert excinfo.value.detail == "github webhook secret not configured"


def test_github_webhook_rejects_invalid_signature(monkeypatch):
    module = load_app(monkeypatch)

    with pytest.raises(HTTPException) as excinfo:
        call_webhook(
            module,
            b"{}",
            {"X-Hub-Signature-256": "sha256=deadbeef"},
        )

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "invalid signature"


def test_github_webhook_rejects_invalid_json(monkeypatch):
    module = load_app(monkeypatch)
    body = b"{not-json"

    with pytest.raises(HTTPException) as excinfo:
        call_webhook(
            module,
            body,
            {"X-Hub-Signature-256": sign("test-secret", body)},
        )

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "invalid github payload"
