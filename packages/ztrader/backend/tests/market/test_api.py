from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from zkbtrader.adapters.kucoin import InvalidMarketDataResponse, MarketDataUnavailable


def _client_with_sqlite(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "zkbtrader-test.db"

    import os

    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path}"
    os.environ["EXECUTION_MODE"] = "paper"
    os.environ["LIVE_TRADING_ENABLED"] = "false"

    from zkbtrader import db

    db.get_engine.cache_clear()
    db.get_session_factory.cache_clear()

    from zkbtrader.api import app

    return TestClient(app)


def _sample_backtest_payload() -> dict[str, object]:
    return {
        "symbol": "BTC/USDT",
        "candles": [
            {"timestamp": "t1", "open": 1, "high": 1, "low": 1, "close": 10, "volume": 1},
            {"timestamp": "t2", "open": 1, "high": 1, "low": 1, "close": 11, "volume": 1},
            {"timestamp": "t3", "open": 1, "high": 1, "low": 1, "close": 12, "volume": 1},
            {"timestamp": "t4", "open": 1, "high": 1, "low": 1, "close": 13, "volume": 1},
            {"timestamp": "t5", "open": 1, "high": 1, "low": 1, "close": 14, "volume": 1},
        ],
    }


def test_live_trading_remains_disabled(tmp_path: Path) -> None:
    with _client_with_sqlite(tmp_path) as client:
        response = client.get("/api/v1/safety/live-trading-disabled")

    assert response.status_code == 200
    payload = response.json()
    assert payload["safe"] is True
    assert payload["execution_mode"] == "paper"
    assert payload["live_trading_enabled"] is False


def test_demo_order_persists_and_is_listed(tmp_path: Path) -> None:
    with _client_with_sqlite(tmp_path) as client:
        create_response = client.post("/api/v1/paper/demo-order")
        list_response = client.get("/api/v1/paper/orders")

    assert create_response.status_code == 200
    assert list_response.status_code == 200
    orders = list_response.json()
    assert orders["limit"] == 50
    assert orders["offset"] == 0
    assert orders["count"] == 1
    assert orders["items"][0]["symbol"] == "BTC/USDT"


def test_audit_metadata_round_trip_for_enable_paper(tmp_path: Path) -> None:
    with _client_with_sqlite(tmp_path) as client:
        strategy_id = "strategy-123"
        create_response = client.post(f"/api/v1/strategies/{strategy_id}/enable-paper")
        list_response = client.get("/api/v1/audit/events")

    assert create_response.status_code == 200
    assert list_response.status_code == 200

    events = list_response.json()["items"]
    target = next(event for event in events if event["event_type"] == "strategy.enable_paper")
    assert target["request_id"] == strategy_id
    assert target["metadata"] == {"strategy_id": strategy_id}


def test_demo_order_creates_audit_event_with_metadata(tmp_path: Path) -> None:
    with _client_with_sqlite(tmp_path) as client:
        create_response = client.post("/api/v1/paper/demo-order")
        assert create_response.status_code == 200
        events_response = client.get("/api/v1/audit/events")

    assert events_response.status_code == 200
    events = events_response.json()["items"]
    target = next(event for event in events if event["event_type"] == "paper.order.created")
    assert target["metadata"] == {"symbol": "BTC/USDT", "notional": 25.0}


def test_lifespan_initializes_db_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "zkbtrader-lifespan.db"

    import os

    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path}"
    os.environ["EXECUTION_MODE"] = "paper"
    os.environ["LIVE_TRADING_ENABLED"] = "false"

    from zkbtrader import db

    db.get_engine.cache_clear()
    db.get_session_factory.cache_clear()

    from zkbtrader.api import app

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200

    table_names = set(inspect(db.get_engine()).get_table_names())
    assert "audit_events" in table_names
    assert "paper_orders" in table_names
    assert "backtest_runs" in table_names


def test_backtest_run_is_persisted_and_listed(tmp_path: Path) -> None:
    with _client_with_sqlite(tmp_path) as client:
        run_response = client.post("/api/v1/backtest/run", json=_sample_backtest_payload())
        list_response = client.get("/api/v1/backtests")

    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["strategy_id"] == "ma-crossover-paper"
    assert run_payload["candles_seen"] == 5
    assert run_payload["symbol"] == "BTC/USDT"
    assert isinstance(run_payload["run_id"], str)
    assert isinstance(run_payload["created_at"], str)

    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["limit"] == 50
    assert list_payload["offset"] == 0
    runs = list_payload["items"]
    assert any(item["run_id"] == run_payload["run_id"] for item in runs)


def test_backtest_detail_returns_one_run(tmp_path: Path) -> None:
    with _client_with_sqlite(tmp_path) as client:
        run_response = client.post("/api/v1/backtest/run", json=_sample_backtest_payload())
        run_id = run_response.json()["run_id"]
        detail_response = client.get(f"/api/v1/backtests/{run_id}")

    assert run_response.status_code == 200
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["run_id"] == run_id
    assert detail["strategy_id"] == "ma-crossover-paper"


def test_market_api_maps_unavailable_to_safe_503(tmp_path: Path, monkeypatch) -> None:
    class _UnavailableAdapter:
        def get_ticker(self, symbol: str) -> None:
            raise MarketDataUnavailable("transport details should not leak")

    from zkbtrader import api as api_module

    monkeypatch.setattr(api_module, "_market_adapter", lambda: _UnavailableAdapter())

    with _client_with_sqlite(tmp_path) as client:
        response = client.get("/api/v1/markets/BTC-USDT/ticker")

    assert response.status_code == 503
    assert response.json() == {"detail": "market data service unavailable"}


def test_market_api_maps_invalid_payload_to_safe_502(tmp_path: Path, monkeypatch) -> None:
    class _InvalidPayloadAdapter:
        def list_symbols(self) -> list[str]:
            raise InvalidMarketDataResponse("upstream payload body should not leak")

    from zkbtrader import api as api_module

    monkeypatch.setattr(api_module, "_market_adapter", lambda: _InvalidPayloadAdapter())

    with _client_with_sqlite(tmp_path) as client:
        response = client.get("/api/v1/markets")

    assert response.status_code == 502
    assert response.json() == {"detail": "market data upstream returned an invalid response"}


def test_market_api_server_time_maps_unavailable_to_safe_503(tmp_path: Path, monkeypatch) -> None:
    class _UnavailableAdapter:
        def get_server_time(self) -> None:
            raise MarketDataUnavailable("raw upstream detail should not leak")

    from zkbtrader import api as api_module

    monkeypatch.setattr(api_module, "_market_adapter", lambda: _UnavailableAdapter())

    with _client_with_sqlite(tmp_path) as client:
        response = client.get("/api/v1/markets/server-time")

    assert response.status_code == 503
    assert response.json() == {"detail": "market data service unavailable"}


def test_market_api_invalid_candles_params_return_400(tmp_path: Path) -> None:
    with _client_with_sqlite(tmp_path) as client:
        invalid_limit = client.get("/api/v1/markets/BTC-USDT/candles?timeframe=1hour&limit=0")
        invalid_timeframe = client.get(
            "/api/v1/markets/BTC-USDT/candles?timeframe=not-a-frame&limit=10"
        )

    assert invalid_limit.status_code == 400
    assert invalid_limit.json() == {"detail": "invalid market request parameter"}
    assert invalid_timeframe.status_code == 400
    assert invalid_timeframe.json() == {"detail": "invalid market request parameter"}


def test_market_api_invalid_orderbook_depth_returns_400(tmp_path: Path) -> None:
    with _client_with_sqlite(tmp_path) as client:
        response = client.get("/api/v1/markets/BTC-USDT/orderbook?depth=0")

    assert response.status_code == 400
    assert response.json() == {"detail": "invalid market request parameter"}


def test_dashboard_renders(tmp_path: Path) -> None:
    with _client_with_sqlite(tmp_path) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "ZKBTrader" in response.text
    assert "Execution Mode" in response.text


def test_paper_orders_pagination_and_filters(tmp_path: Path) -> None:
    with _client_with_sqlite(tmp_path) as client:
        first = client.post("/api/v1/paper/demo-order")
        second = client.post("/api/v1/paper/demo-order")
        response = client.get(
            "/api/v1/paper/orders?limit=1&offset=1&symbol=BTC-USDT&strategy_id=demo&side=enter_long"
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["limit"] == 1
    assert payload["offset"] == 1
    assert payload["count"] == 1
    assert payload["items"][0]["symbol"] == "BTC/USDT"
    assert payload["items"][0]["strategy_id"] == "demo"
    assert payload["items"][0]["side"] == "enter_long"


def test_paper_orders_invalid_side_filter_returns_400(tmp_path: Path) -> None:
    with _client_with_sqlite(tmp_path) as client:
        response = client.get("/api/v1/paper/orders?side=not-a-side")

    assert response.status_code == 400
    assert response.json() == {"detail": "invalid paper order filter"}


def test_audit_events_pagination_and_filters(tmp_path: Path) -> None:
    with _client_with_sqlite(tmp_path) as client:
        first = client.post("/api/v1/strategies/strategy-1/enable-paper")
        second = client.post("/api/v1/strategies/strategy-2/disable")
        response = client.get(
            "/api/v1/audit/events?limit=1&offset=0&event_type=strategy.enable_paper"
            "&request_id=strategy-1&actor=system"
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["limit"] == 1
    assert payload["offset"] == 0
    assert payload["count"] == 1
    assert payload["items"][0]["event_type"] == "strategy.enable_paper"
    assert payload["items"][0]["request_id"] == "strategy-1"
    assert payload["items"][0]["actor"] == "system"


def test_backtests_pagination_and_filters(tmp_path: Path) -> None:
    second_payload = _sample_backtest_payload()
    second_payload["symbol"] = "ETH-USDT"

    with _client_with_sqlite(tmp_path) as client:
        first = client.post("/api/v1/backtest/run", json=_sample_backtest_payload())
        second = client.post("/api/v1/backtest/run", json=second_payload)
        response = client.get("/api/v1/backtests?limit=5&offset=0&symbol=BTC-USDT")

    assert first.status_code == 200
    assert second.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["limit"] == 5
    assert payload["offset"] == 0
    assert payload["count"] >= 1
    assert all(item["symbol"] == "BTC/USDT" for item in payload["items"])
