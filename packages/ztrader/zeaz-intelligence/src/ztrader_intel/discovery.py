from __future__ import annotations

from .models import (
    DiscoveryCandidate,
    DiscoveryRequest,
    DiscoveryResponse,
    DiscoveryVerdict,
)
from .scoring import analyze


def discover(payload: DiscoveryRequest) -> DiscoveryResponse:
    ranked: list[tuple[float, DiscoveryCandidate]] = []
    filtered = 0

    for request in payload.candidates:
        market = request.market
        if market and market.market_cap_usd and market.market_cap_usd > payload.max_market_cap_usd:
            filtered += 1
            continue
        if market and (market.liquidity_usd or 0) < payload.min_liquidity_usd:
            filtered += 1
            continue

        intelligence = analyze(request)
        market_quality = 0.0
        if market:
            if (market.buy_sell_ratio or 0) >= 1.3:
                market_quality += 8
            if market.market_cap_usd and market.liquidity_usd:
                ratio = market.liquidity_usd / market.market_cap_usd
                if ratio >= 0.1:
                    market_quality += 10
            if market.volume_24h_usd and market.liquidity_usd:
                volume_ratio = market.volume_24h_usd / market.liquidity_usd
                if 0.25 <= volume_ratio <= 8:
                    market_quality += 8

        score = (
            intelligence.scores.opportunity * 0.55
            + intelligence.scores.confidence * 0.25
            - intelligence.scores.risk * 0.35
            + market_quality
        )

        if intelligence.scores.risk >= 75 or intelligence.action.value == "AVOID":
            verdict = DiscoveryVerdict.SKIP
        elif intelligence.narrative.value == "EARLY" and intelligence.scores.opportunity >= 60:
            verdict = DiscoveryVerdict.EARLY
        elif intelligence.scores.opportunity >= 50 or market_quality >= 18:
            verdict = DiscoveryVerdict.WATCH
        else:
            verdict = DiscoveryVerdict.SKIP

        ranked.append(
            (
                score,
                DiscoveryCandidate(
                    rank=0,
                    token=request.token,
                    verdict=verdict,
                    score=round(score, 2),
                    intelligence=intelligence,
                ),
            )
        )

    ranked.sort(key=lambda item: item[0], reverse=True)
    candidates: list[DiscoveryCandidate] = []
    for index, (_, candidate) in enumerate(ranked[: payload.limit], start=1):
        candidate.rank = index
        candidates.append(candidate)

    return DiscoveryResponse(candidates=candidates, filtered_count=filtered)
