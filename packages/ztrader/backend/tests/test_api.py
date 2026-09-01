# apps/ztrader/backend/tests/test_api.py

import os
# Pre-set required environment variables before importing config / main
os.environ["ENCRYPTION_KEY"] = "00000000000000000000000000000000"
os.environ["JWT_SECRET"] = "00000000000000000000000000000000"

import httpx
import pytest
from ztrader.main import app


@pytest.mark.asyncio
async def test_health_ready_endpoints():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Test /health
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["execution_mode"] == "paper"

        # Test /ready
        res = await client.get("/ready")
        assert res.status_code == 200
        assert res.json() == {"status": "ready"}

@pytest.mark.asyncio
async def test_backtest_endpoint():
    payload = {
        "strategy_name": "ma-crossover",
        "symbol": "BTC/USDT",
        "fast_period": 2,
        "slow_period": 4,
        "notional": 50.0,
        "candles": [
            {"timestamp": "2026-06-06T00:00Z", "open": 50000.0, "high": 50100.0, "low": 49900.0, "close": 50000.0, "volume": 1.0},
            {"timestamp": "2026-06-06T00:01Z", "open": 50000.0, "high": 50200.0, "low": 49800.0, "close": 50100.0, "volume": 1.2},
            {"timestamp": "2026-06-06T00:02Z", "open": 50100.0, "high": 50300.0, "low": 50000.0, "close": 50200.0, "volume": 1.5},
            {"timestamp": "2026-06-06T00:03Z", "open": 50200.0, "high": 50400.0, "low": 50100.0, "close": 50300.0, "volume": 1.8},
            {"timestamp": "2026-06-06T00:04Z", "open": 50300.0, "high": 50500.0, "low": 50200.0, "close": 50400.0, "volume": 2.0},
            {"timestamp": "2026-06-06T00:05Z", "open": 50400.0, "high": 50600.0, "low": 50300.0, "close": 50500.0, "volume": 2.2},
        ]
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/backtest/run", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["strategy_id"] == "ma-crossover-paper"
        assert data["candles_seen"] == 6
        assert data["orders_created"] > 0
