from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient


def _dashboard_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "zkbtrader-dashboard.db"
    raw_database_url = f"sqlite+pysqlite:///{db_path}"

    os.environ["DATABASE_URL"] = raw_database_url
    os.environ["EXECUTION_MODE"] = "paper"
    os.environ["LIVE_TRADING_ENABLED"] = "false"

    from zkbtrader import db

    db.get_engine.cache_clear()
    db.get_session_factory.cache_clear()

    from zkbtrader.api import app

    return TestClient(app)


def test_dashboard_returns_200(tmp_path: Path) -> None:
    with _dashboard_client(tmp_path) as client:
        response = client.get("/")

    assert response.status_code == 200


def test_dashboard_includes_required_sections(tmp_path: Path) -> None:
    with _dashboard_client(tmp_path) as client:
        response = client.get("/")

    body = response.text
    assert "ZKBTrader" in body
    assert "PAPER MODE" in body
    assert "LIVE TRADING DISABLED" in body
    assert "Paper Orders" in body
    assert "Audit Events" in body
    assert "Backtests" in body


def test_dashboard_renders_after_demo_order(tmp_path: Path) -> None:
    with _dashboard_client(tmp_path) as client:
        create_order = client.post("/api/v1/paper/demo-order")
        dashboard = client.get("/")

    assert create_order.status_code == 200
    assert dashboard.status_code == 200
    assert "Paper Orders" in dashboard.text
    assert "BTC/USDT" in dashboard.text


def test_dashboard_does_not_expose_sensitive_env_values(tmp_path: Path) -> None:
    raw_database_url = f"sqlite+pysqlite:///{tmp_path / 'zkbtrader-sensitive.db'}"
    os.environ["DATABASE_URL"] = raw_database_url
    os.environ["EXECUTION_MODE"] = "paper"
    os.environ["LIVE_TRADING_ENABLED"] = "false"

    from zkbtrader import db

    db.get_engine.cache_clear()
    db.get_session_factory.cache_clear()

    from zkbtrader.api import app

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    body = response.text
    assert "KUCOIN_API_SECRET" not in body
    assert "KUCOIN_API_PASSPHRASE" not in body
    assert raw_database_url not in body
