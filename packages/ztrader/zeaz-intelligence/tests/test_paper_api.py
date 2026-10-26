from fastapi.testclient import TestClient

from ztrader_intel import api
from ztrader_intel.paper_trading import PaperTradingStore


def test_paper_api_creates_account_and_submits_idempotent_order(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "paper_store", PaperTradingStore(str(tmp_path / "api-paper.db")))
    client = TestClient(api.app)

    account_response = client.post(
        "/v1/paper/accounts",
        json={"initial_cash_usd": 500},
        headers={"X-Tenant-ID": "tenant-a"},
    )
    assert account_response.status_code == 201
    account = account_response.json()
    account_id = account["account_id"]
    assert account["live_execution_enabled"] is False

    payload = {
        "account_id": account_id,
        "symbol": "TEST",
        "chain": "solana",
        "side": "buy",
        "quantity": 2,
        "reference_price": 10,
        "fee_bps": 10,
        "slippage_bps": 0,
        "idempotency_key": "api-order-key-0001",
    }
    first = client.post("/v1/paper/orders", json=payload, headers={"X-Tenant-ID": "tenant-a"})
    retry = client.post("/v1/paper/orders", json=payload, headers={"X-Tenant-ID": "tenant-a"})
    assert first.status_code == 201
    assert retry.status_code == 201
    assert first.json()["order_id"] == retry.json()["order_id"]

    account_after = client.get(f"/v1/paper/accounts/{account_id}", headers={"X-Tenant-ID": "tenant-a"})
    orders = client.get(f"/v1/paper/accounts/{account_id}/orders", headers={"X-Tenant-ID": "tenant-a"})
    assert account_after.status_code == 200
    assert account_after.json()["cash_usd"] == 479.98
    assert len(orders.json()) == 1


def test_paper_api_rejects_oversell(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "paper_store", PaperTradingStore(str(tmp_path / "api-paper.db")))
    client = TestClient(api.app)
    account = client.post("/v1/paper/accounts", json={"initial_cash_usd": 100}, headers={"X-Tenant-ID": "tenant-a"}).json()
    account_id = account["account_id"]

    common = {
        "account_id": account_id,
        "symbol": "TEST",
        "chain": "solana",
        "quantity": 1,
        "reference_price": 10,
        "fee_bps": 0,
        "slippage_bps": 0,
    }
    buy = client.post(
        "/v1/paper/orders",
        json={**common, "side": "buy", "idempotency_key": "api-buy-key-0001"},
        headers={"X-Tenant-ID": "tenant-a"},
    )
    sell = client.post(
        "/v1/paper/orders",
        json={**common, "side": "sell", "quantity": 2, "idempotency_key": "api-sell-key-0001"},
        headers={"X-Tenant-ID": "tenant-a"},
    )
    assert buy.status_code == 201
    assert sell.status_code == 422
    assert client.get(f"/v1/paper/accounts/{account_id}", headers={"X-Tenant-ID": "tenant-a"}).json()["positions"][0]["quantity"] == 1
