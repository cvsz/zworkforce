from ztrader_intel.models import (
    Action,
    IntelligenceResponse,
    NarrativeStage,
    RugRisk,
    Scores,
    TokenRef,
    TradePlanRequest,
    TradeVerdict,
    WhaleState,
)
from ztrader_intel.trade_plan import build_trade_plan


def test_high_risk_trade_plan_exits():
    intel = IntelligenceResponse(
        token=TokenRef(symbol="RISK", chain="bsc"),
        narrative=NarrativeStage.CROWDED,
        whales=WhaleState.DISTRIBUTING,
        rug_risk=RugRisk.HIGH,
        action=Action.AVOID,
        scores=Scores(opportunity=20, risk=85, confidence=70),
        reasons=[],
        red_flags=[],
        invalidations=[],
        watch_next=[],
    )
    result = build_trade_plan(
        TradePlanRequest(
            token=intel.token,
            current_price=1.0,
            support=0.9,
            resistance=1.2,
            intelligence=intel,
        )
    )
    assert result.verdict == TradeVerdict.EXIT
    assert result.max_position_usd >= 0
