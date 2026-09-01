from __future__ import annotations

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from ztrader.abt.api import tradingview_endpoints as endpoints
from fastapi import HTTPException


class DummyTradingViewAlertTable:
    def __init__(self) -> None:
        self.created_data = None
        self.find_many_kwargs = None

    async def create(self, data):
        self.created_data = data
        return SimpleNamespace(id=123)

    async def find_many(self, **kwargs):
        self.find_many_kwargs = kwargs
        return [
            SimpleNamespace(
                id=123,
                ticker="BTCUSDT",
                exchange="binance",
                action="BUY",
                price=100.0,
                strategy="TRADINGVIEW_ALERT",
                interval="1m",
                message="test",
                receivedAt=datetime(2026, 5, 6, 14, 0, 0),
            )
        ]


class DummyPrisma:
    def __init__(self) -> None:
        self.connected = False
        self.tradingviewalert = DummyTradingViewAlertTable()

    def is_connected(self):
        return self.connected

    async def connect(self):
        self.connected = True


@pytest.fixture()
def dummy_prisma(monkeypatch):
    client = DummyPrisma()
    monkeypatch.setattr(endpoints, "prisma", client)
    return client


def test_tradingview_webhook_uses_schema_fields_and_json_payload(dummy_prisma):
    alert = endpoints.TradingViewAlert(
        ticker="BTCUSDT", action="buy", price=100.0, interval="1m", volume=12.5
    )

    result = asyncio.run(endpoints.tradingview_webhook(alert, webhook_secret="secret"))

    assert result["status"] == "success"
    data = dummy_prisma.tradingviewalert.created_data
    assert data["action"] == "BUY"
    assert "receivedAt" in data
    assert "rawPayload" in data
    assert "received_at" not in data
    assert "raw_payload" not in data
    assert json.loads(data["rawPayload"])["ticker"] == "BTCUSDT"


def test_tradingview_webhook_preserves_client_errors(dummy_prisma):
    alert = endpoints.TradingViewAlert(ticker="BTCUSDT", action="WAIT")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(endpoints.tradingview_webhook(alert, webhook_secret="secret"))

    assert exc_info.value.status_code == 400


def test_list_tradingview_alerts_orders_by_schema_field(dummy_prisma):
    result = asyncio.run(endpoints.list_tradingview_alerts(limit=10, ticker="BTCUSDT"))

    assert result["count"] == 1
    assert result["alerts"][0]["received_at"] == "2026-05-06T14:00:00"
    assert dummy_prisma.tradingviewalert.find_many_kwargs["order"] == {
        "receivedAt": "desc"
    }
