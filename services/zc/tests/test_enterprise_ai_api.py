"""Enterprise AI API migration contract tests."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI

import app.core.config as config_module
from app.api.v1.ai_routes import router
from app.core.auth import create_short_lived_token
from app.core.config import Config
from app.services.ai_service import AIService, get_ai_service


class FakeCoder:
    """Deterministic provider adapter used to keep API tests offline."""

    model = "test-model"

    def __init__(self, **options: Any) -> None:
        self.options = options
        self.model = options.get("model") or self.model

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        file_content: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        return f"generated:{prompt}:{system or ''}:{len(history or [])}"


@pytest.fixture
def ai_app(tmp_path, monkeypatch) -> FastAPI:
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

    async def fake_ai_service() -> AIService:
        return AIService(FakeCoder)

    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_ai_service] = fake_ai_service
    return application


def auth_header(role: str = "developer") -> dict[str, str]:
    token = create_short_lived_token("tenant-a", role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_ai_response_requires_bearer_token(ai_app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=ai_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/ai/responses", json={"prompt": "hello"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_viewer_cannot_create_ai_response(ai_app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=ai_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/ai/responses",
            json={"prompt": "hello"},
            headers=auth_header("viewer"),
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_ai_response_uses_service_layer(ai_app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=ai_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/ai/responses",
            json={
                "prompt": "review this",
                "model": "test-model-v2",
                "agent": "code_reviewer",
                "history": [{"role": "user", "content": "context"}],
            },
            headers=auth_header(),
        )

    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["object"] == "ai.response"
    assert payload["model"] == "test-model-v2"
    assert payload["output_text"].startswith("generated:review this:")
    assert payload["output_text"].endswith(":1")
    assert payload["id"].startswith("air_")


@pytest.mark.asyncio
async def test_unknown_agent_has_stable_error_shape(ai_app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=ai_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/ai/responses",
            json={"prompt": "hello", "agent": "root"},
            headers=auth_header(),
        )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "unknown_capability",
            "message": "Unknown agent: root",
        }
    }


@pytest.mark.asyncio
async def test_capabilities_are_discoverable(ai_app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=ai_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/ai/capabilities",
            headers=auth_header(),
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "code_reviewer" in data["agents"]
    assert "precise" in data["personalities"]
    assert "security" in data["skills"]


@pytest.mark.asyncio
async def test_model_discovery_is_authorized_and_sanitized(ai_app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=ai_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unauthorized = await client.get("/v1/ai/models")
        response = await client.get("/v1/ai/models", headers=auth_header())

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.json() == {"data": []}


@pytest.mark.asyncio
async def test_request_schema_rejects_unknown_fields(ai_app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=ai_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/ai/responses",
            json={"prompt": "hello", "api_key": "must-not-be-client-controlled"},
            headers=auth_header(),
        )

    assert response.status_code == 422
