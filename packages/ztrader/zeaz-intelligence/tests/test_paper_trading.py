from __future__ import annotations

import pytest

from ztrader_intel.paper_trading import (
    PaperAccountCreate,
    PaperOrderRequest,
    PaperTradingError,
    PaperTradingStore,
)


def _order(account_id: str, *, side: str = "buy", quantity: float = 2, key: str = "order-key-0001",
           price: float = 10.0, fee_bps: float = 10, slippage_bps: float = 0) -> PaperOrderRequest:
    return PaperOrderRequest(
        account_id=account_id,
        symbol="TEST",
        chain="solana",
        side=side,
        quantity=quantity,
        reference_price=price,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        idempotency_key=key,
    )


def test_paper_account_starts_with_configured_cash(tmp_path):
    store = PaperTradingStore(str(tmp_path / "paper.db"))
    account = store.create_account(PaperAccountCreate(initial_cash_usd=1_000))

    assert account.cash_usd == 1_000
    assert account.equity_usd == 1_000
    assert account.positions == []
    assert account.execution_mode == "paper"
    assert account.live_execution_enabled is False


def test_buy_applies_slippage_fee_and_updates_position(tmp_path):
    store = PaperTradingStore(str(tmp_path / "paper.db"))
    account = store.create_account(PaperAccountCreate(initial_cash_usd=1_000))

    order = store.submit_order(_order(account.account_id, price=10, quantity=2, fee_bps=100,
                                      slippage_bps=100))
    updated = store.get_account(account.account_id)

    assert order.fill_price == pytest.approx(10.1)
    assert order.notional_usd == pytest.approx(20.2)
    assert order.fee_usd == pytest.approx(0.202)
    assert updated.cash_usd == pytest.approx(979.598)
    assert updated.positions[0].quantity == pytest.approx(2)
    assert updated.positions[0].average_cost_usd == pytest.approx(10.201)
    assert updated.total_fees_usd == pytest.approx(0.202)


def test_buy_rejects_insufficient_cash_without_mutating_ledger(tmp_path):
    store = PaperTradingStore(str(tmp_path / "paper.db"))
    account = store.create_account(PaperAccountCreate(initial_cash_usd=10))

    with pytest.raises(PaperTradingError, match="insufficient paper cash"):
        store.submit_order(_order(account.account_id, quantity=2, price=10, fee_bps=100))

    updated = store.get_account(account.account_id)
    assert updated.cash_usd == 10
    assert updated.positions == []
    assert store.list_orders(account.account_id) == []


def test_sell_rejects_overselling(tmp_path):
    store = PaperTradingStore(str(tmp_path / "paper.db"))
    account = store.create_account(PaperAccountCreate(initial_cash_usd=100))
    store.submit_order(_order(account.account_id, quantity=2, key="buy-order-0001"))

    with pytest.raises(PaperTradingError, match="insufficient position"):
        store.submit_order(_order(account.account_id, side="sell", quantity=3, key="sell-order-0001"))

    assert store.get_account(account.account_id).positions[0].quantity == pytest.approx(2)
    assert len(store.list_orders(account.account_id)) == 1


def test_sell_updates_realized_pnl_and_cash(tmp_path):
    store = PaperTradingStore(str(tmp_path / "paper.db"))
    account = store.create_account(PaperAccountCreate(initial_cash_usd=1_000))
    store.submit_order(_order(account.account_id, quantity=2, key="buy-order-0001", price=10,
                              fee_bps=0))
    sell = store.submit_order(_order(account.account_id, side="sell", quantity=1,
                                     key="sell-order-0001", price=12, fee_bps=100))
    updated = store.get_account(account.account_id)

    assert sell.fill_price == pytest.approx(12)
    assert updated.realized_pnl_usd == pytest.approx(1.88)
    assert updated.cash_usd == pytest.approx(991.88)
    assert updated.positions[0].quantity == pytest.approx(1)


def test_idempotent_retry_returns_original_order_without_double_fill(tmp_path):
    store = PaperTradingStore(str(tmp_path / "paper.db"))
    account = store.create_account(PaperAccountCreate(initial_cash_usd=1_000))
    request = _order(account.account_id)

    first = store.submit_order(request)
    retry = store.submit_order(request)
    updated = store.get_account(account.account_id)

    assert retry.order_id == first.order_id
    assert updated.cash_usd == pytest.approx(979.98)
    assert len(store.list_orders(account.account_id)) == 1


def test_reusing_idempotency_key_with_different_payload_is_rejected(tmp_path):
    store = PaperTradingStore(str(tmp_path / "paper.db"))
    account = store.create_account(PaperAccountCreate(initial_cash_usd=1_000))
    store.submit_order(_order(account.account_id, key="same-order-key"))

    with pytest.raises(PaperTradingError, match="different order"):
        store.submit_order(_order(account.account_id, key="same-order-key", quantity=3))


def test_ledger_survives_store_restart(tmp_path):
    db_path = str(tmp_path / "paper.db")
    store = PaperTradingStore(db_path)
    account = store.create_account(PaperAccountCreate(initial_cash_usd=250))
    store.submit_order(_order(account.account_id, quantity=2, price=5))

    restarted = PaperTradingStore(db_path)
    persisted = restarted.get_account(account.account_id)

    assert persisted.cash_usd == pytest.approx(239.99)
    assert persisted.positions[0].quantity == pytest.approx(2)
    assert len(restarted.list_orders(account.account_id)) == 1


def test_unknown_account_is_rejected(tmp_path):
    store = PaperTradingStore(str(tmp_path / "paper.db"))

    with pytest.raises(PaperTradingError, match="account not found"):
        store.submit_order(_order("missing-account"))
