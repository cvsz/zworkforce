from ztrader_intel.discovery import discover
from ztrader_intel.models import (
    DiscoveryRequest,
    DiscoveryVerdict,
    IntelligenceRequest,
    MarketSnapshot,
    TokenRef,
)


def test_market_only_candidate_can_be_watch_but_not_early():
    result = discover(
        DiscoveryRequest(
            candidates=[
                IntelligenceRequest(
                    token=TokenRef(symbol="NEW", chain="base"),
                    market=MarketSnapshot(
                        market_cap_usd=200000,
                        liquidity_usd=50000,
                        volume_24h_usd=120000,
                        buy_sell_ratio=1.6,
                    ),
                )
            ]
        )
    )
    assert result.candidates
    assert result.candidates[0].verdict in {DiscoveryVerdict.WATCH, DiscoveryVerdict.SKIP}
    assert result.candidates[0].verdict != DiscoveryVerdict.EARLY


def test_market_cap_filter():
    result = discover(
        DiscoveryRequest(
            max_market_cap_usd=100000,
            candidates=[
                IntelligenceRequest(
                    token=TokenRef(symbol="BIG", chain="solana"),
                    market=MarketSnapshot(market_cap_usd=500000, liquidity_usd=50000),
                )
            ],
        )
    )
    assert result.filtered_count == 1
    assert result.candidates == []
