from __future__ import annotations

import asyncio

import numpy as np
from ztrader.binance_perp_bot.models import (
    MarketSnapshot,
    RegimeMode,
    SignalAction,
    StrategyKind,
    TradeSignal,
)
from ztrader.binance_perp_bot.risk.position_manager import PositionManager
from ztrader.binance_perp_bot.strategies import (
    BaseStrategy,
    PositionStrategy,
    ScalpStrategy,
    SwingStrategy,
)


class Allocation:
    scalp = 0.20
    swing = 0.30
    position = 0.50


def candles(count: int = 250) -> list[list[float]]:
    return [
        [i * 60_000, 100 + i * 0.1, 101 + i * 0.1, 99 + i * 0.1, 100 + i * 0.1, 10]
        for i in range(count)
    ]


def snapshot(symbol: str = "BTC/USDT:USDT") -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        timeframe="1m",
        ohlcv=candles(),
        ticker={"last": 125.0},
        orderbook={},
    )


def test_concrete_strategies_implement_base_contract() -> None:
    for strategy in (ScalpStrategy(), SwingStrategy(), PositionStrategy()):
        assert isinstance(strategy, BaseStrategy)
        assert strategy.calculate_size(snapshot(), 1_000, 100) > 0
        assert 0 <= strategy.get_regime_suitability(RegimeMode.TREND) <= 1


def test_position_manager_rejects_high_correlation() -> None:
    async def scenario() -> None:
        manager = PositionManager(Allocation(), max_correlation=0.65)
        await manager.update_equity(1_000)
        returns = np.linspace(-0.01, 0.01, 30)
        await manager.set_return_history("BTC/USDT:USDT", returns)
        await manager.set_return_history("ETH/USDT:USDT", returns)
        signal = TradeSignal(
            "BTC/USDT:USDT",
            StrategyKind.SCALP,
            SignalAction.ENTER_LONG,
            0.9,
            100,
            RegimeMode.TREND,
        )
        first = await manager.reserve(signal, 100, 3)
        assert first is not None
        await manager.commit_open(first, 100)
        correlated = TradeSignal(
            "ETH/USDT:USDT",
            StrategyKind.SCALP,
            SignalAction.ENTER_LONG,
            0.9,
            100,
            RegimeMode.TREND,
        )
        assert await manager.reserve(correlated, 100, 3) is None

    asyncio.run(scenario())


def test_position_manager_rejects_scalp_against_position_conflict() -> None:
    async def scenario() -> None:
        manager = PositionManager(Allocation(), max_correlation=0.65)
        await manager.update_equity(1_000)
        position_signal = TradeSignal(
            "BTC/USDT:USDT",
            StrategyKind.POSITION,
            SignalAction.ENTER_LONG,
            0.9,
            100,
            RegimeMode.TREND,
        )
        position_intent = await manager.reserve(position_signal, 100, 3)
        assert position_intent is not None
        await manager.commit_open(position_intent, 100)

        scalp_signal = TradeSignal(
            "BTC/USDT:USDT",
            StrategyKind.SCALP,
            SignalAction.ENTER_SHORT,
            0.9,
            100,
            RegimeMode.MEAN_REVERSION,
        )
        assert await manager.reserve(scalp_signal, 100, 3) is None
        assert scalp_signal.metadata["risk_rejection_reason"] == "conflict"
        assert scalp_signal.metadata["conflicting_strategy"] == "position"

    asyncio.run(scenario())


def test_position_manager_enforces_capacity_and_reports_snapshot() -> None:
    async def scenario() -> None:
        manager = PositionManager(
            Allocation(), max_correlation=0.65, max_positions=1, max_margin_ratio=0.80
        )
        await manager.update_equity(1_000)
        first_signal = TradeSignal(
            "BTC/USDT:USDT",
            StrategyKind.SCALP,
            SignalAction.ENTER_LONG,
            0.9,
            100,
            RegimeMode.TREND,
        )
        first = await manager.reserve(first_signal, 100, 3)
        assert first is not None
        await manager.commit_open(first, 100)

        second_signal = TradeSignal(
            "SOL/USDT:USDT",
            StrategyKind.SCALP,
            SignalAction.ENTER_LONG,
            0.9,
            100,
            RegimeMode.TREND,
        )
        assert await manager.reserve(second_signal, 100, 3) is None
        assert second_signal.metadata["risk_rejection_reason"] == "max_positions"

        portfolio = await manager.snapshot()
        assert portfolio.equity_usdt == 1_000
        assert portfolio.used_margin_usdt == 100
        assert len(portfolio.open_positions) == 1
        assert 0 < portfolio.margin_ratio < 1

    asyncio.run(scenario())


def test_market_snapshot_bounds_ohlcv_without_mutating_original() -> None:
    source = snapshot()
    bounded = source.with_bounded_ohlcv(25)
    assert len(source.ohlcv) == 250
    assert len(bounded.ohlcv) == 25
    assert bounded.ohlcv[0] == source.ohlcv[-25]


def test_xgboost_gate_uses_cold_start_when_model_missing(tmp_path) -> None:
    from ztrader.binance_perp_bot.ml.gate import XGBoostTradeGate

    gate = XGBoostTradeGate(str(tmp_path / "missing.json"), threshold=0.10)
    signal = TradeSignal(
        "BTC/USDT:USDT",
        StrategyKind.SCALP,
        SignalAction.ENTER_LONG,
        0.9,
        100,
        RegimeMode.TREND,
    )
    assert gate.allow(snapshot(), signal)
    assert signal.metadata["ml_gate_mode"] == "calibrated_cold_start"
    assert 0 <= signal.metadata["xgb_trade_probability"] <= 1


def test_crypto_service_imports_without_encryption_key(monkeypatch) -> None:
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

    from ztrader.core import crypto_service

    try:
        crypto_service.encrypt_data("secret")
    except RuntimeError as exc:
        assert str(exc) == "ENCRYPTION_KEY not set"
    else:
        raise AssertionError("encrypt_data should require ENCRYPTION_KEY at call time")


def test_crypto_service_round_trip(monkeypatch) -> None:
    import base64

    from ztrader.core import crypto_service

    monkeypatch.setenv("ENCRYPTION_KEY", base64.b64encode(b"1" * 32).decode())

    ciphertext, iv = crypto_service.encrypt_data("secret")

    assert ciphertext != "secret"
    assert crypto_service.decrypt_data(ciphertext, iv) == "secret"
