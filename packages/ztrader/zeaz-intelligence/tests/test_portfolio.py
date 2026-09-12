from ztrader_intel.models import (
    Action,
    Horizon,
    IntelligenceResponse,
    NarrativeStage,
    PortfolioCandidate,
    PortfolioRequest,
    RiskProfile,
    RugRisk,
    Scores,
    TokenRef,
    WhaleState,
)
from ztrader_intel.portfolio import build_portfolio


def intelligence(symbol: str, opportunity: int, risk: int):
    return IntelligenceResponse(
        token=TokenRef(symbol=symbol, chain="solana"),
        narrative=NarrativeStage.EARLY,
        whales=WhaleState.ACCUMULATING,
        rug_risk=RugRisk.LOW,
        action=Action.WATCH,
        scores=Scores(opportunity=opportunity, risk=risk, confidence=75),
        reasons=[],
        red_flags=[],
        invalidations=[],
        watch_next=[],
    )


def test_conservative_portfolio_keeps_reserve():
    a = intelligence("A", 80, 30)
    b = intelligence("B", 70, 40)
    result = build_portfolio(
        PortfolioRequest(
            capital_usd=10000,
            risk=RiskProfile.CONSERVATIVE,
            horizon=Horizon.MEDIUM,
            candidates=[
                PortfolioCandidate(token=a.token, intelligence=a),
                PortfolioCandidate(token=b.token, intelligence=b),
            ],
        )
    )
    assert result.reserve_pct == 35
    assert sum(item.weight_pct for item in result.allocations) <= 65.01
