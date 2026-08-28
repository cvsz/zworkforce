"""Authentication and production configuration regression tests."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

import app.core.config as config_module
from app.api.v1.routes import router
from app.core.auth import create_short_lived_token
from app.core.config import Config


@pytest.fixture
def secure_config(tmp_path, monkeypatch) -> Config:
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
    return config


@pytest.mark.asyncio
async def test_upload_endpoint_requires_bearer_token(secure_config: Config) -> None:
    app = FastAPI()
    app.include_router(router)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/wire/upload/init", json={})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_viewer_cannot_create_upload(secure_config: Config) -> None:
    app = FastAPI()
    app.include_router(router)
    token = create_short_lived_token("tenant-a", "viewer")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/wire/upload/init",
            json={"file_id": "file-1", "file_name": "x", "total_size": 4},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403


def test_production_config_requires_jwt_secret(tmp_path) -> None:
    config = Config(
        environment="production",
        auth_required=True,
        jwt_secret=None,
        upload_temp_dir=tmp_path,
    )
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        config.validate()
