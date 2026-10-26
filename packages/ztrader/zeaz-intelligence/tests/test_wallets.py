from fastapi.testclient import TestClient
import pytest

from ztrader_intel import api

from ztrader_intel.models import SmartMoneyRequest, TokenRef, WalletTransfer, WhaleState
from ztrader_intel.wallets import analyze_wallet_flows


def test_smart_money_accumulation():
    result = analyze_wallet_flows(
        SmartMoneyRequest(
            token=TokenRef(symbol="T", chain="solana"),
            transfers=[
                WalletTransfer(
                    wallet="a",
                    direction="buy",
                    usd_value=10000,
                    is_known_smart_money=True,
                    is_new_wallet=True,
                ),
                WalletTransfer(wallet="b", direction="buy", usd_value=5000),
                WalletTransfer(wallet="c", direction="sell", usd_value=1000),
            ],
        )
    )
    assert result.state == WhaleState.ACCUMULATING
    assert result.smart_money_net_usd == 10000
    assert result.new_smart_money_entries == 1


@pytest.mark.parametrize("direction", ["unknown", "", "purchase", "sell-side"])
def test_unknown_wallet_direction_is_rejected(direction):
    payload = SmartMoneyRequest(
        token=TokenRef(symbol="T", chain="solana"),
        transfers=[WalletTransfer(wallet="x", direction=direction, usd_value=10)],
    )
    with pytest.raises(ValueError, match="unsupported wallet transfer direction"):
        analyze_wallet_flows(payload)


def test_negative_wallet_transfer_amount_is_rejected():
    payload = SmartMoneyRequest(
        token=TokenRef(symbol="T", chain="solana"),
        transfers=[WalletTransfer(wallet="x", direction="buy", usd_value=-1)],
    )
    with pytest.raises(ValueError, match="usd_value must be non-negative"):
        analyze_wallet_flows(payload)

@pytest.mark.parametrize(
    ("direction", "usd_value", "expected_detail"),
    [
        ("unknown", 10, "unsupported wallet transfer direction"),
        ("buy", -1, "usd_value must be non-negative"),
    ],
)
def test_wallets_api_returns_422_for_invalid_transfer(direction, usd_value, expected_detail):
    client = TestClient(api.app)
    response = client.post(
        "/v1/wallets/analyze",
        json={
            "token": {"symbol": "T", "chain": "solana"},
            "transfers": [{"wallet": "x", "direction": direction, "usd_value": usd_value}],
        },
    )

    assert response.status_code == 422
    assert expected_detail in response.json()["detail"]
