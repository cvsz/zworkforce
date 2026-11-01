import json

from fastapi.testclient import TestClient

from ztrader_intel import api
from ztrader_intel.paper_trading import PaperTradingStore

SERVICE_TOKEN = "service-test-token-for-paper-api-32-characters"
TENANT_TOKENS = {
    "tenant-a": "tenant-a-paper-token-test-value-32-characters",
    "tenant-b": "tenant-b-paper-token-test-value-32-characters",
}


def _configure_auth(monkeypatch):
    monkeypatch.setenv("ZTRADER_INTEL_SERVICE_TOKEN", SERVICE_TOKEN)
    monkeypatch.setenv("ZTRADER_PAPER_TENANT_TOKENS", json.dumps(TENANT_TOKENS))


def _headers(tenant_id: str = "tenant-a") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {SERVICE_TOKEN}",
        "X-Tenant-ID": tenant_id,
        "X-Paper-Tenant-Token": TENANT_TOKENS[tenant_id],
    }


def _client(tmp_path, monkeypatch, name: str = "paper.db") -> TestClient:
    monkeypatch.setattr(api, "paper_store", PaperTradingStore(str(tmp_path / name)))
    return TestClient(api.app)


def test_paper_api_creates_account_and_submits_idempotent_order(tmp_path, monkeypatch):
    _configure_auth(monkeypatch)
    client = _client(tmp_path, monkeypatch, "api-paper.db")
    headers = _headers()

    account_response = client.post(
        "/v1/paper/accounts",
        json={"initial_cash_usd": 500},
        headers=headers,
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
    first = client.post("/v1/paper/orders", json=payload, headers=headers)
    retry = client.post("/v1/paper/orders", json=payload, headers=headers)
    assert first.status_code == 201
    assert retry.status_code == 201
    assert first.json()["order_id"] == retry.json()["order_id"]

    account_after = client.get(f"/v1/paper/accounts/{account_id}", headers=headers)
    orders = client.get(f"/v1/paper/accounts/{account_id}/orders", headers=headers)
    assert account_after.status_code == 200
    assert account_after.json()["cash_usd"] == 479.98
    assert len(orders.json()) == 1


def test_paper_api_rejects_oversell(tmp_path, monkeypatch):
    _configure_auth(monkeypatch)
    client = _client(tmp_path, monkeypatch, "oversell-paper.db")
    headers = _headers()
    account = client.post(
        "/v1/paper/accounts",
        json={"initial_cash_usd": 100},
        headers=headers,
    ).json()
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
        headers=headers,
    )
    sell = client.post(
        "/v1/paper/orders",
        json={**common, "side": "sell", "quantity": 2, "idempotency_key": "api-sell-key-0001"},
        headers=headers,
    )
    assert buy.status_code == 201
    assert sell.status_code == 422
    account_after = client.get(f"/v1/paper/accounts/{account_id}", headers=headers)
    assert account_after.json()["positions"][0]["quantity"] == 1


def test_paper_api_denies_cross_tenant_account_and_order_access(tmp_path, monkeypatch):
    _configure_auth(monkeypatch)
    client = _client(tmp_path, monkeypatch, "tenant-paper.db")
    account_response = client.post(
        "/v1/paper/accounts",
        json={"initial_cash_usd": 100},
        headers=_headers("tenant-a"),
    )
    assert account_response.status_code == 201
    account_id = account_response.json()["account_id"]

    tenant_b_headers = _headers("tenant-b")
    assert client.get(
        f"/v1/paper/accounts/{account_id}",
        headers=tenant_b_headers,
    ).status_code == 404
    assert client.get(
        f"/v1/paper/accounts/{account_id}/orders",
        headers=tenant_b_headers,
    ).status_code == 404

    cross_tenant_order = {
        "account_id": account_id,
        "symbol": "TEST",
        "chain": "solana",
        "side": "buy",
        "quantity": 1,
        "reference_price": 10,
        "idempotency_key": "cross-tenant-order-0001",
    }
    assert client.post(
        "/v1/paper/orders",
        json=cross_tenant_order,
        headers=tenant_b_headers,
    ).status_code == 404


def test_paper_api_rejects_tenant_token_for_another_tenant(tmp_path, monkeypatch):
    _configure_auth(monkeypatch)
    client = _client(tmp_path, monkeypatch, "tenant-token-mismatch.db")
    headers = _headers("tenant-a")
    headers["X-Tenant-ID"] = "tenant-b"

    response = client.post(
        "/v1/paper/accounts",
        json={"initial_cash_usd": 100},
        headers=headers,
    )
    assert response.status_code == 401


def test_paper_api_requires_service_authentication(tmp_path, monkeypatch):
    _configure_auth(monkeypatch)
    client = _client(tmp_path, monkeypatch, "service-auth.db")
    headers = {
        "X-Tenant-ID": "tenant-a",
        "X-Paper-Tenant-Token": TENANT_TOKENS["tenant-a"],
    }
    response = client.post(
        "/v1/paper/accounts",
        json={"initial_cash_usd": 100},
        headers=headers,
    )
    assert response.status_code == 401


def test_paper_api_requires_tenant_bound_token(tmp_path, monkeypatch):
    _configure_auth(monkeypatch)
    client = _client(tmp_path, monkeypatch, "tenant-auth.db")
    headers = {
        "Authorization": f"Bearer {SERVICE_TOKEN}",
        "X-Tenant-ID": "tenant-a",
    }
    response = client.post(
        "/v1/paper/accounts",
        json={"initial_cash_usd": 100},
        headers=headers,
    )
    assert response.status_code == 401


def test_paper_api_fails_closed_without_tenant_token_configuration(tmp_path, monkeypatch):
    _configure_auth(monkeypatch)
    monkeypatch.delenv("ZTRADER_PAPER_TENANT_TOKENS", raising=False)
    client = _client(tmp_path, monkeypatch, "tenant-config-missing.db")
    response = client.post(
        "/v1/paper/accounts",
        json={"initial_cash_usd": 100},
        headers=_headers(),
    )
    assert response.status_code == 503


def test_paper_api_rejects_reused_tenant_tokens_in_configuration(tmp_path, monkeypatch):
    _configure_auth(monkeypatch)
    monkeypatch.setenv(
        "ZTRADER_PAPER_TENANT_TOKENS",
        json.dumps({
            "tenant-a": TENANT_TOKENS["tenant-a"],
            "tenant-b": TENANT_TOKENS["tenant-a"],
        }),
    )
    client = _client(tmp_path, monkeypatch, "tenant-config-duplicate.db")
    response = client.post(
        "/v1/paper/accounts",
        json={"initial_cash_usd": 100},
        headers=_headers(),
    )
    assert response.status_code == 503


def test_paper_api_requires_tenant_header(tmp_path, monkeypatch):
    _configure_auth(monkeypatch)
    client = _client(tmp_path, monkeypatch, "header-paper.db")
    response = client.post(
        "/v1/paper/accounts",
        json={"initial_cash_usd": 100},
        headers={
            "Authorization": f"Bearer {SERVICE_TOKEN}",
            "X-Paper-Tenant-Token": TENANT_TOKENS["tenant-a"],
        },
    )
    assert response.status_code == 422

def test_wallets_api_returns_422_for_invalid_transfer_data():
    client = TestClient(api.app)
    token = {"symbol": "T", "chain": "solana"}
    invalid_transfers = [
        ({"wallet": "x", "direction": "unknown", "usd_value": 10},
         "unsupported wallet transfer direction"),
        ({"wallet": "x", "direction": "buy", "usd_value": -1},
         "usd_value must be non-negative"),
    ]

    for transfer, expected_detail in invalid_transfers:
        response = client.post(
            "/v1/wallets/analyze",
            json={"token": token, "transfers": [transfer]},
        )
        assert response.status_code == 422
        assert expected_detail in response.json()["detail"]
