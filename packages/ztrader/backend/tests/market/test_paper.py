import pytest

from zkbtrader.models import IntentSide, PaperPortfolio, StrategyIntent
from zkbtrader.paper import PaperExecutionEngine
from zkbtrader.risk import RiskEngine, RiskLimits


def test_paper_enter_long_updates_virtual_balances() -> None:
    engine = PaperExecutionEngine(PaperPortfolio(usdt=1000, btc=0), fee_rate=0.001)
    risk = RiskEngine(limits=RiskLimits(max_order_notional=100))
    intent = StrategyIntent(
        symbol="BTC/USDT",
        side=IntentSide.ENTER_LONG,
        notional=100,
        strategy_id="test",
        reason="unit-test",
    )

    order = engine.execute(intent, price=50_000, risk=risk)

    assert order.base_amount == pytest.approx(0.002)
    assert order.fee == pytest.approx(0.1)
    assert engine.portfolio.usdt == pytest.approx(899.9)
    assert engine.portfolio.btc == pytest.approx(0.002)


def test_paper_engine_does_not_execute_when_risk_denies() -> None:
    engine = PaperExecutionEngine(PaperPortfolio(usdt=1000, btc=0))
    risk = RiskEngine(kill_switch=True)
    intent = StrategyIntent(
        symbol="BTC/USDT",
        side=IntentSide.ENTER_LONG,
        notional=10,
        strategy_id="test",
        reason="unit-test",
    )

    with pytest.raises(ValueError, match="risk_denied:global_kill_switch"):
        engine.execute(intent, price=50_000, risk=risk)

    assert engine.orders == []
    assert engine.portfolio.usdt == pytest.approx(1000)
