from zkbtrader.models import IntentSide, RiskDecisionStatus, StrategyIntent
from zkbtrader.risk import RiskEngine, RiskLimits


def test_kill_switch_denies_intent() -> None:
    risk = RiskEngine(kill_switch=True)
    intent = StrategyIntent(
        symbol="BTC/USDT",
        side=IntentSide.ENTER_LONG,
        notional=10,
        strategy_id="test",
        reason="unit-test",
    )

    decision = risk.validate_intent(intent)

    assert decision.status == RiskDecisionStatus.DENY
    assert decision.reason_code == "global_kill_switch"


def test_max_notional_denies_intent() -> None:
    risk = RiskEngine(limits=RiskLimits(max_order_notional=10))
    intent = StrategyIntent(
        symbol="BTC/USDT",
        side=IntentSide.ENTER_LONG,
        notional=11,
        strategy_id="test",
        reason="unit-test",
    )

    decision = risk.validate_intent(intent)

    assert decision.status == RiskDecisionStatus.DENY
    assert decision.reason_code == "max_order_notional_exceeded"


def test_allowed_intent() -> None:
    risk = RiskEngine(limits=RiskLimits(max_order_notional=10))
    intent = StrategyIntent(
        symbol="BTC/USDT",
        side=IntentSide.ENTER_LONG,
        notional=10,
        strategy_id="test",
        reason="unit-test",
    )

    decision = risk.validate_intent(intent)

    assert decision.status == RiskDecisionStatus.ALLOW
    assert decision.reason_code == "allowed"
