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


def test_invalid_support_geometry_blocks_entry_and_returns_ordered_zone():
    intel = IntelligenceResponse(
        token=TokenRef(symbol="EDGE", chain="bsc"),
        narrative=NarrativeStage.EARLY,
        whales=WhaleState.ACCUMULATING,
        rug_risk=RugRisk.LOW,
        action=Action.WATCH,
        scores=Scores(opportunity=90, risk=10, confidence=95),
        reasons=[],
        red_flags=[],
        invalidations=[],
        watch_next=[],
    )
    result = build_trade_plan(
        TradePlanRequest(
            token=intel.token,
            current_price=1.0,
            support=1.1,
            resistance=1.3,
            intelligence=intel,
        )
    )

    assert result.verdict == TradeVerdict.WAIT
    assert result.entry_zone[0] <= result.entry_zone[1]
    assert any("entry is blocked" in reason for reason in result.reasons)
