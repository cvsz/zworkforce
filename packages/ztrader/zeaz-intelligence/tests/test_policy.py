from ztrader_intel.models import (
    Action,
    IntelligenceResponse,
    NarrativeStage,
    RugRisk,
    Scores,
    TokenRef,
    WhaleState,
)
from ztrader_intel.policy import execution_policy


def make_response(risk: int = 30, confidence: int = 75, opportunity: int = 80):
    return IntelligenceResponse(
        token=TokenRef(symbol="T", chain="solana"),
        narrative=NarrativeStage.EARLY,
        whales=WhaleState.ACCUMULATING,
        rug_risk=RugRisk.LOW,
        action=Action.WATCH,
        scores=Scores(opportunity=opportunity, risk=risk, confidence=confidence),
        reasons=[],
        red_flags=[],
        invalidations=[],
        watch_next=[],
    )


def test_policy_allows_paper_but_never_live():
    result = execution_policy(make_response())
    assert result["allowed_for_paper_trade"] is True
    assert result["allowed_for_live_execution"] is False


def test_policy_blocks_high_risk():
    result = execution_policy(make_response(risk=80))
    assert result["allowed_for_paper_trade"] is False
