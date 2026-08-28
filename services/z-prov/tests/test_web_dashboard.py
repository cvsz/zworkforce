import hashlib
import json
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from zeaz_web.dashboard import DashboardSettings, create_app
from zeaz_web.views import StateReader


def settings() -> DashboardSettings:
    return DashboardSettings(
        gateway_url="https://gateway.test",
        control_url="https://control.test",
        enterprise_url="https://enterprise.test",
        gateway_key=SecretStr("server-only-dashboard-key"),
    )


def transport(request: httpx.Request) -> httpx.Response:
    if request.url.host == "gateway.test" and request.url.path == "/health/ready":
        return httpx.Response(200, json={"status": "ready"})
    if request.url.host == "control.test":
        return httpx.Response(200, json={"status": "ready"})
    if request.url.host == "enterprise.test":
        return httpx.Response(200, json={"status": "ready"})
    if request.url.path == "/v1/models":
        assert request.headers["authorization"] == "Bearer server-only-dashboard-key"
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [{"id": "zeaz-claude", "owned_by": "anthropic"}],
            },
        )
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_dashboard_aggregates_health_and_models_without_exposing_key(monkeypatch) -> None:
    app = create_app(settings())
    original = httpx.AsyncClient

    class MockClient:
        def __init__(self, *args, **kwargs):
            self._client = original(transport=httpx.MockTransport(transport), trust_env=False)

        async def __aenter__(self):
            return self._client

        async def __aexit__(self, *args):
            await self._client.aclose()

    monkeypatch.setattr("zeaz_web.dashboard.httpx.AsyncClient", MockClient)
    with TestClient(app) as client:
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        value = response.json()
        assert [item["name"] for item in value["services"]] == ["gateway", "control", "enterprise"]
        assert value["models"] == [{"id": "zeaz-claude", "owned_by": "anthropic", "route": "zeaz-claude"}]
        assert value["routes"] == [
            {
                "name": "anthropic",
                "provider": "anthropic",
                "status": "healthy",
                "model_count": 1,
            }
        ]
        assert "server-only-dashboard-key" not in response.text


def test_dashboard_static_shell_is_accessible_and_does_not_use_browser_storage() -> None:
    with TestClient(create_app(settings())) as client:
        assert client.get("/").status_code == 200
        assert client.get("/chat").status_code == 200
        script = client.get("/assets/app.js").text
        chat_script = client.get("/assets/chat.js").text
        assert "localStorage" not in script
        assert "sessionStorage" not in script
        assert "localStorage" not in chat_script
        assert "sessionStorage" not in chat_script
        assert "server-only-dashboard-key" not in client.get("/").text


def test_state_reader_redacts_sensitive_audit_fields_and_exposes_views(tmp_path) -> None:
    database = tmp_path / "sessions.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE sessions (session_id TEXT PRIMARY KEY, revision INTEGER, document TEXT)"
        )
        document = {
            "id": "session-1",
            "status": "active",
            "execution_mode": "plan",
            "turns": [],
        }
        connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?)",
            ("session-1", 2, json.dumps(document)),
        )
    audit = tmp_path / "audit.jsonl"
    event = {
        "event": {
            "session_id": "session-1",
            "sequence": 0,
            "event_type": "plan.created",
            "actor": "user",
            "details": {"api_key": "do-not-show", "note": "ok"},
            "created_at": "2026-01-01T00:00:00Z",
        }
    }
    audit.write_text(json.dumps(event) + "\n")
    snapshot = StateReader(session_db_path=database, audit_log_path=audit).snapshot()
    assert snapshot.sessions[0].execution_mode == "plan"
    assert snapshot.plans[0].details == {"api_key": "[REDACTED]", "note": "ok"}
    assert "do-not-show" not in snapshot.model_dump_json()


def test_sessions_static_and_state_endpoint_are_read_only() -> None:
    with TestClient(create_app(settings())) as client:
        assert client.get("/sessions").status_code == 200
        value = client.get("/api/state").json()
        assert value["sessions"] == []
        assert "localStorage" not in client.get("/assets/sessions.js").text
        assert "sessionStorage" not in client.get("/assets/sessions.js").text


def test_admin_surface_requires_dedicated_hash_only_credential() -> None:
    admin_key = "admin-only-test-key"
    values = settings().model_dump()
    values["admin_key_hashes"] = frozenset(
        {hashlib.sha256(admin_key.encode()).digest()}
    )
    configured = DashboardSettings(**values)
    with TestClient(create_app(configured)) as client:
        assert client.get("/admin").status_code == 200
        assert client.get("/api/admin/state").status_code == 404
        assert client.get(
            "/api/admin/state", headers={"x-zeaz-admin-key": "wrong"}
        ).status_code == 404
        response = client.get(
            "/api/admin/state", headers={"x-zeaz-admin-key": admin_key}
        )
        assert response.status_code == 200
        assert "admin-only-test-key" not in response.text
        assert "localStorage" not in client.get("/assets/admin.js").text
        assert "sessionStorage" not in client.get("/assets/admin.js").text


def test_web_pages_have_keyboard_and_responsive_contracts() -> None:
    with TestClient(create_app(settings())) as client:
        for path in ("/", "/chat", "/sessions", "/admin"):
            document = client.get(path).text
            assert 'name="viewport"' in document
            assert 'class="shell"' in document
        assert 'class="skip-link"' in client.get("/").text
        assert 'class="skip-link"' in client.get("/chat").text
        css = client.get("/assets/styles.css").text + client.get("/assets/chat.css").text
        assert "@media(max-width:720px)" in css
        assert ":focus-visible" in css


def test_dashboard_rejects_credentials_in_urls_and_unbounded_settings() -> None:
    with pytest.raises(ValidationError):
        DashboardSettings(gateway_url="https://user:pass@example.test")
    with pytest.raises(ValidationError):
        DashboardSettings(request_timeout_seconds=31)


@pytest.mark.parametrize(
    ("protocol", "path"),
    (
        ("anthropic", "/v1/messages"),
        ("chat", "/v1/chat/completions"),
        ("responses", "/v1/responses"),
    ),
)
def test_chat_proxy_keeps_key_server_side_and_selects_protocol(
    monkeypatch, protocol: str, path: str
) -> None:
    seen: list[httpx.Request] = []

    def chat_transport(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b'data: {"ok":true}\\n\\nevent: done\\ndata: [DONE]\\n\\n',
        )

    original = httpx.AsyncClient

    class MockClient:
        def __init__(self, *args, **kwargs):
            self._client = original(
                transport=httpx.MockTransport(chat_transport), trust_env=False
            )

        async def __aenter__(self):
            return self._client

        async def __aexit__(self, *args):
            await self._client.aclose()

    monkeypatch.setattr("zeaz_web.dashboard.httpx.AsyncClient", MockClient)
    with TestClient(create_app(settings())) as client:
        response = client.post(
            f"/api/chat/{protocol}",
            json={"model": "zeaz-claude", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert response.status_code == 200
    assert seen[0].url.path == path
    assert seen[0].headers["authorization"] == "Bearer server-only-dashboard-key"
    assert "server-only-dashboard-key" not in response.text
    assert json.loads(seen[0].content)["stream"] is True
