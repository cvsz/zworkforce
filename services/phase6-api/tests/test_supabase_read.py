from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
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


class FakeAsyncClient:
    response: httpx.Response | None = None
    last: FakeAsyncClient | None = None

    def __init__(self, timeout: float | None = None) -> None:
        self.timeout = timeout
        self.url: str | None = None
        self.params: dict[str, str] | None = None
        self.headers: dict[str, str] | None = None
        type(self).last = self

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def get(
        self,
        url: str,
        *,
        params: dict[str, str],
        headers: dict[str, str],
        follow_redirects: bool,
    ) -> httpx.Response:
        self.url = url
        self.params = params
        self.headers = headers
        assert follow_redirects is False
        assert type(self).response is not None
        return type(self).response


def load_app(monkeypatch, *, supabase_url: str = "https://project.supabase.co", supabase_key: str = "anon-key", table: str = "readiness"):
    for collector in list(REGISTRY._collector_to_names):
        REGISTRY.unregister(collector)
    monkeypatch.setenv("PHASE6_API_TOKEN", "token")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("AI_PROVIDER_ENDPOINTS", "{}")
    monkeypatch.setenv("AI_PROVIDER_KEYS_JSON", "{}")
    monkeypatch.setenv("SUPABASE_URL", supabase_url)
    monkeypatch.setenv("SUPABASE_ANON_KEY", supabase_key)
    monkeypatch.setenv("SUPABASE_TABLE", table)
    spec = importlib.util.spec_from_file_location("phase6_api_app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    module.r = FakeRedis()
    return module


def test_supabase_read_requires_service_token(monkeypatch):
    module = load_app(monkeypatch)
    client = TestClient(module.app)

    response = client.get("/supabase/read")

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_supabase_read_returns_rows_and_uses_read_only_headers(monkeypatch):
    module = load_app(monkeypatch)
    client = TestClient(module.app)
    request = httpx.Request("GET", "https://project.supabase.co/rest/v1/readiness?select=*&limit=2")
    FakeAsyncClient.response = httpx.Response(200, json=[{"id": 1, "name": "alpha"}], request=request)
    monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)

    response = client.get("/supabase/read?limit=2", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "verified"
    assert body["source"] == "supabase"
    assert body["table"] == "readiness"
    assert body["limit"] == 2
    assert body["rows"] == [{"id": 1, "name": "alpha"}]
    assert FakeAsyncClient.last is not None
    assert FakeAsyncClient.last.url == "https://project.supabase.co/rest/v1/readiness"
    assert FakeAsyncClient.last.params == {"select": "*", "limit": "2"}
    assert FakeAsyncClient.last.headers == {
        "apikey": "anon-key",
        "Authorization": "Bearer anon-key",
        "Accept": "application/json",
    }


def test_supabase_read_rejects_missing_config(monkeypatch):
    module = load_app(monkeypatch, supabase_url="", supabase_key="", table="")
    client = TestClient(module.app)

    response = client.get("/supabase/read", headers={"Authorization": "Bearer token"})

    assert response.status_code == 503
    assert response.json() == {"detail": "supabase read access not configured"}


def test_supabase_read_rejects_invalid_base_url(monkeypatch):
    module = load_app(monkeypatch, supabase_url="ftp://project.supabase.co", supabase_key="anon-key", table="readiness")
    client = TestClient(module.app)

    response = client.get("/supabase/read", headers={"Authorization": "Bearer token"})

    assert response.status_code == 400
    assert response.json() == {"detail": "supabase base url is invalid"}


def test_supabase_read_rejects_invalid_table_name(monkeypatch):
    module = load_app(monkeypatch, supabase_url="https://project.supabase.co", supabase_key="anon-key", table="readiness-1")
    client = TestClient(module.app)

    response = client.get("/supabase/read", headers={"Authorization": "Bearer token"})

    assert response.status_code == 400
    assert response.json() == {"detail": "supabase table name is invalid"}


def test_supabase_read_rejects_upstream_forbidden(monkeypatch):
    module = load_app(monkeypatch)
    client = TestClient(module.app)
    request = httpx.Request("GET", "https://project.supabase.co/rest/v1/readiness?select=*&limit=1")
    FakeAsyncClient.response = httpx.Response(403, content=b"{}", request=request)
    monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)

    response = client.get("/supabase/read?limit=1", headers={"Authorization": "Bearer token"})

    assert response.status_code == 502
    assert response.json() == {"detail": "supabase rejected the read request"}


def test_supabase_read_rejects_non_array_payload(monkeypatch):
    module = load_app(monkeypatch)
    client = TestClient(module.app)
    request = httpx.Request("GET", "https://project.supabase.co/rest/v1/readiness?select=*&limit=1")
    FakeAsyncClient.response = httpx.Response(200, json={"rows": []}, request=request)
    monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)

    response = client.get("/supabase/read?limit=1", headers={"Authorization": "Bearer token"})

    assert response.status_code == 502
    assert response.json() == {"detail": "supabase returned an unexpected payload"}


def test_supabase_read_rows_rejects_out_of_range_limit(monkeypatch):
    module = load_app(monkeypatch)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(module.supabase_read_rows(0))

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "limit must be between 1 and 100"
