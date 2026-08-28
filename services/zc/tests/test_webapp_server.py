"""tests/test_webapp_server.py — webapp/backend/server.py

Uses FastAPI's TestClient (httpx-based, no real network/socket). The
Coder.generate() / anthropic streaming calls are monkeypatched so no real
API calls happen anywhere in this file, same convention as
tests/test_coder.py.
"""
import sys
import asyncio
from pathlib import Path

import pytest
import httpx
import fastapi.routing

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import webapp.backend.server as server  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_state(monkeypatch):
    """Each test gets an empty session store and a fresh rate-limit
    bucket, so tests can't leak state into each other via the
    process-local dicts server.py uses."""
    async def run_inline(call, *args, **kwargs):
        return call(*args, **kwargs)

    # This test host cannot wake event-loop callbacks from worker threads.
    # Route callables are deterministic local functions, so execute them inline.
    monkeypatch.setattr(fastapi.routing, "run_in_threadpool", run_inline)
    server._sessions.clear()
    server._rate_buckets.clear()
    yield
    server._sessions.clear()
    server._rate_buckets.clear()


@pytest.fixture
def client():
    class SyncASGIClient:
        """Synchronous facade over httpx's in-process ASGI transport."""

        def request(self, method, url, **kwargs):
            async def send():
                transport = httpx.ASGITransport(app=server.app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    return await client.request(method, url, **kwargs)

            return asyncio.run(send())

        def get(self, url, **kwargs):
            return self.request("GET", url, **kwargs)

        def post(self, url, **kwargs):
            return self.request("POST", url, **kwargs)

        def delete(self, url, **kwargs):
            return self.request("DELETE", url, **kwargs)

    yield SyncASGIClient()


def test_version_endpoint(client):
    resp = client.get("/api/version")
    assert resp.status_code == 200
    assert "version" in resp.json()


def test_chat_rejects_empty_prompt(client):
    resp = client.post("/api/chat", json={"prompt": "   "})
    assert resp.status_code == 400


def test_chat_rejects_out_of_range_temperature(client):
    resp = client.post("/api/chat", json={"prompt": "hi", "temperature": 5.0})
    assert resp.status_code == 422  # pydantic validation error


def test_chat_rejects_out_of_range_max_tokens(client):
    resp = client.post("/api/chat", json={"prompt": "hi", "max_tokens": 0})
    assert resp.status_code == 422


def test_chat_happy_path(client, monkeypatch):
    monkeypatch.setattr(server.Coder, "generate", lambda self, *a, **k: "mock reply")
    resp = client.post("/api/chat", json={"prompt": "hello", "api_key": "sk-ant-test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["response"] == "mock reply"
    assert "session_id" in data


def test_chat_rate_limit_returns_429(client, monkeypatch):
    monkeypatch.setattr(server.Coder, "generate", lambda self, *a, **k: "ok")
    monkeypatch.setattr(server, "_RATE_LIMIT", 2)
    for _ in range(2):
        resp = client.post("/api/chat", json={"prompt": "hi", "api_key": "sk-ant-test"})
        assert resp.status_code == 200
    resp = client.post("/api/chat", json={"prompt": "hi", "api_key": "sk-ant-test"})
    assert resp.status_code == 429


def test_sessions_list_empty_by_default(client):
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_sessions_list_reflects_chat_history(client, monkeypatch):
    monkeypatch.setattr(server.Coder, "generate", lambda self, *a, **k: "reply text")
    chat_resp = client.post("/api/chat", json={"prompt": "what is python", "api_key": "sk-ant-test"})
    sid = chat_resp.json()["session_id"]

    listing = client.get("/api/sessions").json()
    assert len(listing) == 1
    assert listing[0]["session_id"] == sid
    assert listing[0]["turns"] == 1
    assert "what is python" in listing[0]["preview"]


def test_sessions_get_and_delete(client, monkeypatch):
    monkeypatch.setattr(server.Coder, "generate", lambda self, *a, **k: "reply")
    sid = client.post("/api/chat", json={"prompt": "hi", "api_key": "sk-ant-test"}).json()["session_id"]

    got = client.get(f"/api/sessions/{sid}")
    assert got.status_code == 200
    assert len(got.json()["history"]) == 2

    deleted = client.delete(f"/api/sessions/{sid}")
    assert deleted.status_code == 200
    assert client.get(f"/api/sessions/{sid}").status_code == 404


def test_chat_stream_requires_api_key(client, monkeypatch):
    monkeypatch.setattr(server.Config, "get", lambda self, key, default=None: None)
    resp = client.post("/api/chat/stream", json={"prompt": "hi"})
    assert resp.status_code == 400


def test_chat_stream_yields_tokens_and_done(client, monkeypatch):
    class FakeDelta:
        def __init__(self, text):
            self.type = "text_delta"
            self.text = text

    class FakeEvent:
        def __init__(self, text):
            self.type = "content_block_delta"
            self.delta = FakeDelta(text)

    class FakeStreamCtx:
        def __init__(self, chunks):
            self.chunks = chunks

        def __enter__(self):
            return iter(FakeEvent(c) for c in self.chunks)

        def __exit__(self, *a):
            return False

    class FakeMessages:
        def stream(self, **kwargs):
            return FakeStreamCtx(["Hel", "lo", "!"])

    class FakeAnthropic:
        def __init__(self, api_key=None):
            self.messages = FakeMessages()

    import types
    fake_anthropic_module = types.SimpleNamespace(Anthropic=FakeAnthropic)
    monkeypatch.setitem(sys.modules, "anthropic", fake_anthropic_module)

    resp = client.post("/api/chat/stream", json={"prompt": "hi", "api_key": "sk-ant-test"})
    assert resp.status_code == 200
    body = resp.text
    assert '"type": "token"' in body or '"type":"token"' in body
    assert "done" in body
