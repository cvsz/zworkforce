# apps/ztrader/backend/tests/test_live.py

import os
# Pre-set required environment variables before imports
os.environ["ENCRYPTION_KEY"] = "00000000000000000000000000000000"
os.environ["JWT_SECRET"] = "00000000000000000000000000000000"

import pytest
from unittest.mock import AsyncMock, MagicMock
from ztrader.engine.live import LiveBroker, MT5GatewayClient
from ztrader.engine.risk import RiskEngine, StrategyIntent
from ztrader.models.db_models import ExchangeKey
from ztrader.core.security import encryptor

def test_mt5_gateway_client():
    client = MT5GatewayClient(login="12345", server="MT5-Broker-Live", password_encrypted="secret")
    receipt = client.execute_order(symbol="BTC/USD", side="buy", amount=0.5, price=65000.0)
    assert receipt["status"] == "filled"
    assert receipt["broker"] == "MetaTrader 5"
    assert "mt5-deal-" in receipt["id"]
    assert receipt["price"] == 65000.0

@pytest.mark.asyncio
async def test_live_broker_mt5_execution():
    # Construct exchange keys for MT5
    encrypted_key = encryptor.encrypt("12345")
    encrypted_secret = encryptor.encrypt("secret_pass")

    db_key = ExchangeKey(
        exchange="MT5",
        encrypted_key=encrypted_key,
        encrypted_secret=encrypted_secret,
        passphrase="MT5-Live-Server"
    )

    broker = LiveBroker(db_key)
    assert broker.exchange_name == "MT5"
    assert isinstance(broker.client, MT5GatewayClient)

    # Mock database session
    db_mock = AsyncMock()
    db_mock.add = MagicMock()

    risk = RiskEngine(allowed_symbols=("BTC/USDT",), max_order_notional=1000.0, kill_switch=False)
    intent = StrategyIntent(symbol="BTC/USDT", side="buy", notional=200.0, strategy_id="ma-crossover", request_id="00000000-0000-0000-0000-000000000001")

    order = await broker.execute(intent=intent, price=50000.0, risk=risk, db=db_mock)

    assert order.symbol == "BTC/USDT"
    assert order.side == "buy"
    assert order.execution_mode == "live"
    assert order.price == 50000.0
    assert order.base_amount == 200.0 / 50000.0
    db_mock.add.assert_called_once()
    db_mock.commit.assert_called_once()

def test_live_broker_initialization_crypto(monkeypatch):
    # Mock ccxt classes to prevent network calls
    mock_okx_class = MagicMock()
    mock_bybit_class = MagicMock()

    import ccxt
    monkeypatch.setattr(ccxt, "okx", mock_okx_class)
    monkeypatch.setattr(ccxt, "bybit", mock_bybit_class)

    enc_key = encryptor.encrypt("api-key-value")
    enc_sec = encryptor.encrypt("api-secret-value")

    # OKX key
    okx_db_key = ExchangeKey(
        exchange="okx",
        encrypted_key=enc_key,
        encrypted_secret=enc_sec,
        passphrase="my-passphrase"
    )

    broker_okx = LiveBroker(okx_db_key)
    assert broker_okx.exchange_name == "okx"
    mock_okx_class.assert_called_once_with({
        "apiKey": "api-key-value",
        "secret": "api-secret-value",
        "password": "my-passphrase",
        "enableRateLimit": True
    })

    # Bybit key
    bybit_db_key = ExchangeKey(
        exchange="bybit",
        encrypted_key=enc_key,
        encrypted_secret=enc_sec
    )

    broker_bybit = LiveBroker(bybit_db_key)
    assert broker_bybit.exchange_name == "bybit"
    mock_bybit_class.assert_called_once_with({
        "apiKey": "api-key-value",
        "secret": "api-secret-value",
        "enableRateLimit": True
    })
