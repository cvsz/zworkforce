from ztrader_intel.models import (
    Action,
    IntelligenceRequest,
    MarketSnapshot,
    RugRisk,
    SecuritySnapshot,
    SocialSnapshot,
    TokenRef,
    WhaleSnapshot,
)
from ztrader_intel.scoring import analyze


def test_early_accumulation_setup_is_watch_not_buy():
    req = IntelligenceRequest(
        token=TokenRef(symbol="TEST", chain="solana"),
        market=MarketSnapshot(
            market_cap_usd=500_000,
            liquidity_usd=100_000,
            volume_24h_usd=140_000,
            buy_sell_ratio=1.9,
            holder_growth_pct=14,
            tx_growth_pct=25,
        ),
        social=SocialSnapshot(
            mention_growth_5m=60,
            mention_growth_1h=35,
            mention_growth_24h=12,
            sentiment_score=0.6,
            organic_score=0.82,
            influencer_concentration=0.25,
        ),
        whales=WhaleSnapshot(
            net_flow_usd=90_000,
            accumulating_wallets=5,
            distributing_wallets=1,
            exchange_inflow_usd=10_000,
            exchange_outflow_usd=25_000,
        ),
        security=SecuritySnapshot(
            top10_holder_pct=22,
            insider_pct=4,
            liquidity_locked=True,
            honeypot=False,
            mintable=False,
            open_source=True,
        ),
        fundamentals_score=55,
        source_freshness_minutes=8,
    )

    result = analyze(req)

    assert result.narrative.value == "EARLY"
    assert result.whales.value == "ACCUMULATING"
    assert result.action == Action.WATCH
    assert result.scores.opportunity >= 60
    assert result.scores.risk < 55


def test_honeypot_forces_extreme_risk_and_avoid():
    req = IntelligenceRequest(
        token=TokenRef(symbol="BAD", chain="bsc"),
        security=SecuritySnapshot(honeypot=True, mintable=True, liquidity_locked=False),
    )

    result = analyze(req)

    assert result.rug_risk == RugRisk.EXTREME
    assert result.action == Action.AVOID
    assert result.scores.risk >= 85
