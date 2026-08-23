from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=str(tmp_path / "test.db"),
        line_channel_access_token=None,
        line_channel_secret="line-secret",
        facebook_app_secret="facebook-secret",
        tiktok_webhook_secret="tiktok-secret",
        shopee_webhook_secret="shopee-secret",
    )


@pytest.fixture()
def app(settings: Settings):
    return create_app(settings)


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def services(app):
    return app.state.services


@pytest.fixture()
def catalog(services):
    return services.catalog


@pytest.fixture()
def conversations(services):
    return services.conversations


@pytest.fixture()
def orders(services):
    return services.orders


@pytest.fixture()
def integrations(services):
    return services.integrations


@pytest.fixture()
def notifications(services):
    return services.notifications
