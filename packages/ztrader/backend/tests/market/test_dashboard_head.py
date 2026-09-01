from __future__ import annotations

from fastapi.testclient import TestClient

from zkbtrader.api import app


def test_dashboard_head_returns_200() -> None:
    with TestClient(app) as client:
        response = client.head("/")

    assert response.status_code == 200
    assert response.text == ""
