# apps/ztrader/backend/tests/test_admin.py

import os
# Pre-set required environment variables before importing config / main
os.environ["ENCRYPTION_KEY"] = "00000000000000000000000000000000"
os.environ["JWT_SECRET"] = "00000000000000000000000000000000"
os.environ["ADMIN_API_TOKEN"] = "test-admin-token"

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest
import pytest_asyncio

from ztrader.main import app
from ztrader.core.database import get_db_session
from ztrader.models.db_models import User, RentalContract
from ztrader.core.config import settings

mock_db = AsyncMock()
ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token"}

def utc_now():
    return datetime.now(timezone.utc)

async def override_get_db_session():
    yield mock_db

app.dependency_overrides[get_db_session] = override_get_db_session
settings.ADMIN_API_TOKEN = "test-admin-token"

@pytest.fixture(autouse=True)
def reset_mock_db():
    mock_db.reset_mock(return_value=True, side_effect=True)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.rollback = AsyncMock()
    yield
    mock_db.reset_mock(return_value=True, side_effect=True)

@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

@pytest.mark.asyncio
async def test_admin_get_users(client):
    # Setup mock user data
    mock_user_1 = User(
        id=uuid.uuid4(),
        email="test-admin@zeaz.dev",
        name="Test Admin",
        role="admin",
        created_at=utc_now()
    )
    mock_user_2 = User(
        id=uuid.uuid4(),
        email="test-user@zeaz.dev",
        name="Test User",
        role="user",
        created_at=utc_now()
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_user_1, mock_user_2]
    mock_db.execute.return_value = mock_result

    res = await client.get("/api/v1/admin/users", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    assert data[0]["email"] == "test-admin@zeaz.dev"
    assert data[0]["role"] == "admin"
    assert data[1]["email"] == "test-user@zeaz.dev"
    assert data[1]["role"] == "user"

@pytest.mark.asyncio
async def test_admin_update_user_role(client):
    user_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        email="test-user@zeaz.dev",
        name="Test User",
        role="user",
        created_at=utc_now()
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_user
    mock_db.execute.return_value = mock_result

    res = await client.put(f"/api/v1/admin/users/{user_id}/role", json={"role": "operator"}, headers=ADMIN_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "operator"
    assert mock_db.commit.called

@pytest.mark.asyncio
async def test_admin_get_contracts(client):
    user_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        email="test-user@zeaz.dev",
        name="Test User",
        role="user",
        created_at=utc_now()
    )

    mock_contract = RentalContract(
        id=uuid.uuid4(),
        user_id=user_id,
        start_date=utc_now(),
        end_date=utc_now(),
        is_active=True
    )

    # We execute twice in the endpoint (once for contracts, and once per contract for user)
    mock_result_contracts = MagicMock()
    mock_result_contracts.scalars.return_value.all.return_value = [mock_contract]

    mock_result_user = MagicMock()
    mock_result_user.scalars.return_value.first.return_value = mock_user

    # Setup mock side effect for DB execution
    async def mock_execute(stmt):
        stmt_str = str(stmt)
        if "rental_contracts" in stmt_str:
            return mock_result_contracts
        elif "users" in stmt_str:
            return mock_result_user
        return MagicMock()

    mock_db.execute.side_effect = mock_execute

    res = await client.get("/api/v1/admin/contracts", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["user_email"] == "test-user@zeaz.dev"
    assert data[0]["is_active"] is True

@pytest.mark.asyncio
async def test_admin_create_contract(client):
    user_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        email="test-user@zeaz.dev",
        name="Test User",
        role="user",
        created_at=utc_now()
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_user
    mock_db.execute.side_effect = None
    mock_db.execute.return_value = mock_result

    payload = {
        "user_id": str(user_id),
        "end_date": "2026-12-31T23:59:59Z",
        "is_active": True
    }

    res = await client.post("/api/v1/admin/contracts", json=payload, headers=ADMIN_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["user_email"] == "test-user@zeaz.dev"
    assert data["is_active"] is True
    assert mock_db.add.called
    assert mock_db.commit.called

@pytest.mark.asyncio
async def test_admin_toggle_contract(client):
    contract_id = uuid.uuid4()
    user_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        email="test-user@zeaz.dev",
        role="user",
        created_at=utc_now()
    )
    mock_contract = RentalContract(
        id=contract_id,
        user_id=user_id,
        start_date=utc_now(),
        end_date=utc_now(),
        is_active=True
    )

    mock_result_contract = MagicMock()
    mock_result_contract.scalars.return_value.first.return_value = mock_contract
    mock_result_user = MagicMock()
    mock_result_user.scalars.return_value.first.return_value = mock_user

    async def mock_execute_toggle(stmt):
        stmt_str = str(stmt)
        if "rental_contracts" in stmt_str:
            return mock_result_contract
        elif "users" in stmt_str:
            return mock_result_user
        return MagicMock()

    mock_db.execute.side_effect = mock_execute_toggle

    res = await client.put(f"/api/v1/admin/contracts/{contract_id}/toggle", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["is_active"] is False # toggled from True to False
    assert mock_db.commit.called

@pytest.mark.asyncio
async def test_admin_risk_config_endpoints(client):
    # Test GET config
    res = await client.get("/api/v1/admin/risk/config", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "kill_switch_active" in data
    assert "max_order_notional" in data
    assert "allowed_symbols" in data

    # Test PUT config
    payload = {
        "kill_switch_active": True,
        "max_order_notional": 250.0,
        "allowed_symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    }
    res = await client.put("/api/v1/admin/risk/config", json=payload, headers=ADMIN_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["kill_switch_active"] is True
    assert data["max_order_notional"] == 250.0
    assert "SOL/USDT" in data["allowed_symbols"]

    # Restore settings to original values
    settings.GLOBAL_KILL_SWITCH = False
    settings.RISK_MAX_ORDER_NOTIONAL = 100.0
    settings.RISK_ALLOWED_SYMBOLS = ("BTC/USDT", "ETH/USDT")

@pytest.mark.asyncio
async def test_admin_system_health(client):
    res = await client.get("/api/v1/admin/system/health", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["db_connected"] is True
    assert data["redis_connected"] is True
    assert any(
        broker_name == "binance.com"
        for broker_name in data["broker_latency_ms"]
    )

@pytest.mark.asyncio
async def test_admin_requires_bearer_token(client):
    res = await client.get("/api/v1/admin/system/health")
    assert res.status_code == 403

@pytest.mark.asyncio
async def test_kill_switch_requires_admin_token(client):
    res = await client.post("/api/v1/risk/kill-switch", json={"active": True})
    assert res.status_code == 403

    res = await client.post(
        "/api/v1/risk/kill-switch",
        json={"active": True},
        headers=ADMIN_HEADERS,
    )
    assert res.status_code == 200
    assert res.json()["kill_switch_active"] is True
    settings.GLOBAL_KILL_SWITCH = False
