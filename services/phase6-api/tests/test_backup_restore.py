from __future__ import annotations

import importlib.util
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
    monkeypatch.setenv("AI_PROVIDER_ENDPOINTS", "{}")
    monkeypatch.setenv("AI_PROVIDER_KEYS_JSON", "{}")
    spec = importlib.util.spec_from_file_location("phase6_api_backup_app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_backup_restore_requires_and_forwards_isolated_namespace(monkeypatch):
    module = load_app(monkeypatch)
    observed = {}

    async def fake_request(method, route, payload=None, params=None):
        observed.update(method=method, route=route, payload=payload, params=params)
        return {"restored": True, "isolated": True, "namespace": payload["namespace"]}

    module.agent_provider_request = fake_request
    client = TestClient(module.app)
    response = client.post(
        "/backup/restore",
        headers={"Authorization": "Bearer token"},
        json={"namespace": "readiness-run-1", "snapshot": {"jobs": {}}},
    )
    assert response.status_code == 200
    assert response.json()["isolated"] is True
    assert observed == {
        "method": "POST",
        "route": "restore",
        "payload": {"namespace": "readiness-run-1", "snapshot": {"jobs": {}}},
        "params": None,
    }


def test_backup_restore_rejects_primary_restore_shape(monkeypatch):
    module = load_app(monkeypatch)
    client = TestClient(module.app)
    response = client.post(
        "/backup/restore",
        headers={"Authorization": "Bearer token"},
        json={"jobs": {}},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "valid namespace is required"}


def test_backup_verify_forwards_object_and_namespace(monkeypatch):
    module = load_app(monkeypatch)
    observed = {}

    async def fake_request(method, route, payload=None, params=None):
        observed.update(method=method, route=route, payload=payload, params=params)
        return {"verified": True, "namespace": params["namespace"]}

    module.agent_provider_request = fake_request
    client = TestClient(module.app)
    response = client.get(
        "/backup/verify?object=backup-1&namespace=readiness-run-1",
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200
    assert observed == {
        "method": "GET",
        "route": "verify",
        "payload": None,
        "params": {"object": "backup-1", "namespace": "readiness-run-1"},
    }
