"""Persistent chat session API and SSE contract tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

import app.core.config as config_module
from app.api.v1.chat_routes import router
from app.core.auth import create_short_lived_token
from app.core.config import Config
from app.services.ai_service import AIService
from app.services.chat_session_store import AtomicChatSessionStore
from app.services.chat_sessions import ChatSessionService, get_chat_session_service
from app.services.resource_store import ResourceNotFoundError


class FakeCoder:
    """Deterministic streaming provider used by API tests."""

    def __init__(self, **options: Any) -> None:
        self.model = str(options.get("model") or "test-model")

    async def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        file_content: str | None = None,
        history: list[dict[str, str]] | None = None,
    ):
        del system, file_content
        yield type(
            "Chunk",
            (),
            {
                "text": f"answer:{prompt}:",
                "model": self.model,
                "input_tokens": len(history or []),
                "output_tokens": None,
            },
        )()
        yield type(
            "Chunk",
            (),
            {
                "text": "done",
                "model": self.model,
                "input_tokens": None,
                "output_tokens": 2,
            },
        )()


@pytest.fixture
def chat_app(tmp_path, monkeypatch) -> tuple[FastAPI, AtomicChatSessionStore]:
    config = Config(
        environment="test",
        redis_enabled=False,
        nats_enabled=False,
        protobuf_enabled=False,
        upload_temp_dir=tmp_path,
        storage_backend="local",
        jwt_secret="a-test-secret-with-sufficient-entropy",
        auth_required=True,
        rate_limit_enabled=False,
    )
    monkeypatch.setattr(config_module, "_config", config)
    store = AtomicChatSessionStore(tmp_path / "chat")
    service = ChatSessionService(store, AIService(FakeCoder))

    async def fake_chat_service() -> ChatSessionService:
        return service

    application = FastAPI()

    @application.exception_handler(ResourceNotFoundError)
    async def not_found(_request, _exc) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "Not found."}},
        )

    application.include_router(router)
    application.dependency_overrides[get_chat_session_service] = fake_chat_service
    return application, store


def auth_header(subject: str = "tenant-a", role: str = "developer") -> dict[str, str]:
    token = create_short_lived_token(subject, role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_chat_session_streams_and_persists_exchange(
    chat_app: tuple[FastAPI, AtomicChatSessionStore],
) -> None:
    app, _store = chat_app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/v1/chat/sessions",
            json={},
            headers=auth_header(),
        )
        session_id = created.json()["data"]["id"]
        response = await client.post(
            f"/v1/chat/sessions/{session_id}/responses",
            json={"prompt": "Review this", "model": "zc-default"},
            headers=auth_header(),
        )
        loaded = await client.get(
            f"/v1/chat/sessions/{session_id}",
            headers=auth_header(),
        )

    assert created.status_code == 201
    assert created.headers["location"].endswith(session_id)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: response.started" in response.text
    assert response.text.count("event: response.output_text.delta") == 2
    assert "event: response.completed" in response.text
    session = loaded.json()["data"]
    assert session["title"] == "Review this"
    assert [message["role"] for message in session["messages"]] == [
        "user",
        "assistant",
    ]
    assert session["messages"][1]["content"] == "answer:Review this:done"
    assert session["messages"][1]["usage"]["output_tokens"] == 2


@pytest.mark.asyncio
async def test_chat_sessions_are_tenant_isolated(
    chat_app: tuple[FastAPI, AtomicChatSessionStore],
) -> None:
    app, _store = chat_app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/v1/chat/sessions",
            json={"title": "Private"},
            headers=auth_header("tenant-a"),
        )
        session_id = created.json()["data"]["id"]
        cross_tenant = await client.get(
            f"/v1/chat/sessions/{session_id}",
            headers=auth_header("tenant-b"),
        )
        tenant_b_list = await client.get(
            "/v1/chat/sessions",
            headers=auth_header("tenant-b"),
        )

    assert cross_tenant.status_code == 404
    assert tenant_b_list.json()["data"] == []


@pytest.mark.asyncio
async def test_chat_session_survives_service_restart(
    chat_app: tuple[FastAPI, AtomicChatSessionStore],
) -> None:
    app, store = chat_app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/v1/chat/sessions",
            json={"title": "Durable"},
            headers=auth_header(),
        )
    session_id = created.json()["data"]["id"]

    restarted = ChatSessionService(
        AtomicChatSessionStore(store.root),
        AIService(FakeCoder),
    )
    session = await restarted.get("tenant-a", session_id)

    assert session.title == "Durable"
    session_file = next(store.root.rglob(f"{session_id}.json"))
    assert session_file.stat().st_mode & 0o777 == 0o600
    assert session_file.parent.stat().st_mode & 0o777 == 0o700


@pytest.mark.asyncio
async def test_viewer_can_read_but_cannot_mutate_chat(
    chat_app: tuple[FastAPI, AtomicChatSessionStore],
) -> None:
    app, _store = chat_app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        listed = await client.get(
            "/v1/chat/sessions",
            headers=auth_header(role="viewer"),
        )
        created = await client.post(
            "/v1/chat/sessions",
            json={},
            headers=auth_header(role="viewer"),
        )

    assert listed.status_code == 200
    assert created.status_code == 403


@pytest.mark.asyncio
async def test_chat_session_identifier_cannot_escape_storage_root(
    chat_app: tuple[FastAPI, AtomicChatSessionStore],
) -> None:
    app, store = chat_app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/chat/sessions/..%2F..%2Fsecret",
            headers=auth_header(),
        )

    assert response.status_code == 404
    assert not (store.root.parent / "secret.json").exists()


@pytest.mark.asyncio
async def test_chat_listing_skips_corrupt_records_without_leaking_tenants(
    chat_app: tuple[FastAPI, AtomicChatSessionStore],
) -> None:
    _app, store = chat_app
    tenant_directory = store._tenant_dir("tenant-a")
    corrupt = tenant_directory / ("chat_" + "f" * 32 + ".json")
    corrupt.write_text("{not-json", encoding="utf-8")
    service = ChatSessionService(store, AIService(FakeCoder))

    sessions, total = await service.list("tenant-a", limit=50, offset=0)

    assert sessions == []
    assert total == 0


@pytest.mark.asyncio
async def test_chat_store_rejects_symlink_records(
    chat_app: tuple[FastAPI, AtomicChatSessionStore],
    tmp_path: Path,
) -> None:
    _app, store = chat_app
    outside = tmp_path / "outside.json"
    outside.write_text('{"secret":"must-not-be-read"}', encoding="utf-8")
    session_id = "chat_" + "e" * 32
    link = store._tenant_dir("tenant-a") / f"{session_id}.json"
    link.symlink_to(outside)
    service = ChatSessionService(store, AIService(FakeCoder))

    with pytest.raises(ResourceNotFoundError):
        await service.get("tenant-a", session_id)

    sessions, total = await service.list("tenant-a", limit=50, offset=0)
    assert sessions == []
    assert total == 0
