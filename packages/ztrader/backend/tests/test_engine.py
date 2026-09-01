# apps/ztrader/backend/tests/test_engine.py

import os
# Pre-set required environment variables before importing config
os.environ["ENCRYPTION_KEY"] = "mock-encryption-key-must-be-32-chars-long"
os.environ["JWT_SECRET"] = "mock-jwt-secret-key"

import pytest
from ztrader.engine.risk import RiskEngine, StrategyIntent, RiskStatus
from ztrader.engine.paper import PaperExecutionEngine, PaperPortfolio
from ztrader.engine.strategy import Candle, MovingAverageCrossoverStrategy
from ztrader.engine.backtest import BacktestEngine

def test_risk_engine():
    risk = RiskEngine(
        allowed_symbols=("BTC/USDT",),
        max_order_notional=100.0,
        kill_switch=False
    )

    # 1. Test ALLOW
    intent = StrategyIntent("BTC/USDT", "buy", 50.0, "test-strat", "req-1")
    status, reason = risk.validate(intent)
    assert status == RiskStatus.ALLOW
    assert reason == "allowed"

    # 2. Test DENY: symbol not allowed
    intent_wrong_symbol = StrategyIntent("ETH/USDT", "buy", 50.0, "test-strat", "req-2")
    status, reason = risk.validate(intent_wrong_symbol)
    assert status == RiskStatus.DENY
    assert reason == "symbol_not_allowed"

    # 3. Test DENY: exceeding max order notional
    intent_large = StrategyIntent("BTC/USDT", "buy", 150.0, "test-strat", "req-3")
    status, reason = risk.validate(intent_large)
    assert status == RiskStatus.DENY
    assert reason == "max_order_notional_exceeded"

    # 4. Test DENY: kill switch active
    risk_killed = RiskEngine(
        allowed_symbols=("BTC/USDT",),
        max_order_notional=100.0,
        kill_switch=True
    )
    status, reason = risk_killed.validate(intent)
    assert status == RiskStatus.DENY
    assert reason == "global_kill_switch_active"

def test_paper_execution():
    portfolio = PaperPortfolio(usdt=1000.0, btc=0.0)
    paper = PaperExecutionEngine(portfolio=portfolio, fee_rate=0.001)
    risk = RiskEngine(allowed_symbols=("BTC/USDT",), max_order_notional=500.0, kill_switch=False)

    # 1. Test enter long (buy)
    intent_buy = StrategyIntent("BTC/USDT", "buy", 500.0, "test-strat", "req-1")
    order = paper.execute(intent_buy, price=50000.0, risk=risk)

    assert order.symbol == "BTC/USDT"
    assert order.side == "buy"
    assert order.price == 50000.0
    assert order.base_amount == 0.01
    assert order.fee == 0.5
    assert portfolio.usdt == 1000.0 - 500.5
    assert portfolio.btc == 0.01

    # 2. Test exit long (sell)
    intent_sell = StrategyIntent("BTC/USDT", "sell", 500.0, "test-strat", "req-2")
    order_sell = paper.execute(intent_sell, price=50000.0, risk=risk)

    assert order_sell.symbol == "BTC/USDT"
    assert order_sell.side == "sell"
    assert order_sell.base_amount == 0.01
    assert order_sell.fee == 0.5
    assert portfolio.usdt == (1000.0 - 500.5) + (500.0 - 0.5)
    assert portfolio.btc == 0.0

def test_backtest_engine():
    candles = [
        Candle("2026-06-06T00:00:00Z", 50000.0, 50100.0, 49900.0, 50000.0, 1.0),
        Candle("2026-06-06T00:01:00Z", 50000.0, 50200.0, 49800.0, 50100.0, 1.2),
        Candle("2026-06-06T00:02:00Z", 50100.0, 50300.0, 50000.0, 50200.0, 1.5),
        Candle("2026-06-06T00:03:00Z", 50200.0, 50400.0, 50100.0, 50300.0, 1.8),
        Candle("2026-06-06T00:04:00Z", 50300.0, 50500.0, 50200.0, 50400.0, 2.0),
        Candle("2026-06-06T00:05:00Z", 50400.0, 50600.0, 50300.0, 50500.0, 2.2),
    ]

    # Fast = 2, Slow = 4
    strategy = MovingAverageCrossoverStrategy(symbol="BTC/USDT", fast=2, slow=4, notional=100.0)
    engine = BacktestEngine(allowed_symbols=("BTC/USDT",), starting_usdt=1000.0)

    result = engine.run(strategy, candles)
    assert result.strategy_id == "ma-crossover-paper"
    assert result.candles_seen == 6
    assert result.orders_created > 0
    assert result.ending_usdt != 1000.0
