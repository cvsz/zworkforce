# apps/ztrader/backend/tests/test_tradingview.py

import os
# Pre-set environment variables before imports
os.environ["ENCRYPTION_KEY"] = "00000000000000000000000000000000"
os.environ["JWT_SECRET"] = "00000000000000000000000000000000"
os.environ["TRADINGVIEW_WEBHOOK_SECRET"] = "tradingview-secret-key-12345"

import pytest
import httpx
from ztrader.main import app


@pytest.mark.asyncio
async def test_tradingview_config():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/tradingview/config")
    assert res.status_code == 200
    data = res.json()
    assert "webhook_url" in data
    assert "instructions" in data

@pytest.mark.asyncio
async def test_tradingview_webhook_unauthenticated():
    payload = {
        "ticker": "BTCUSDT",
        "action": "BUY",
        "price": 65000.0
    }
    # Send request without header or wrong header
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/tradingview/webhook", json=payload, headers={"X-Webhook-Secret": "wrong-secret"})
    assert res.status_code == 403

@pytest.mark.asyncio
async def test_tradingview_webhook_invalid_action():
    payload = {
        "ticker": "BTCUSDT",
        "action": "INVALID_ACTION",
        "price": 65000.0
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/tradingview/webhook",
            json=payload,
            headers={"X-Webhook-Secret": "tradingview-secret-key-12345"}
        )
    assert res.status_code == 400
