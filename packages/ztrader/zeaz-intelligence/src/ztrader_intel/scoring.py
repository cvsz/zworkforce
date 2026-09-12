from __future__ import annotations

from .models import (
    Action,
    IntelligenceRequest,
    IntelligenceResponse,
    NarrativeStage,
    RugRisk,
    Scores,
    WhaleState,
)


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def _known(*values: object) -> int:
    return sum(value is not None for value in values)


def narrative_stage(req: IntelligenceRequest) -> NarrativeStage:
    s = req.social
    if not s:
        return NarrativeStage.DEAD

    growth = [
        x for x in (s.mention_growth_5m, s.mention_growth_1h, s.mention_growth_24h) if x is not None
    ]
    sentiment = s.sentiment_score or 0
    organic = s.organic_score if s.organic_score is not None else 0.5

    if len(growth) >= 2 and growth[0] > growth[1] and growth[0] >= 40 and organic >= 0.65:
        return NarrativeStage.EARLY
    if growth and max(growth) >= 25 and sentiment > 0.15:
        return NarrativeStage.HEATING_UP
    if growth and max(growth) >= 75 and (s.influencer_concentration or 0) >= 0.55:
        return NarrativeStage.CROWDED
    if growth and growth[0] < 0 and sentiment <= 0:
        return NarrativeStage.FADING
    if growth and max(growth) > 0:
        return NarrativeStage.HEATING_UP
    return NarrativeStage.DEAD


def whale_state(req: IntelligenceRequest) -> WhaleState:
    w = req.whales
    if not w:
        return WhaleState.NEUTRAL

    net = w.net_flow_usd or 0
    acc = w.accumulating_wallets or 0
    dist = w.distributing_wallets or 0
    exchange_net = (w.exchange_outflow_usd or 0) - (w.exchange_inflow_usd or 0)

    if net > 0 and acc > dist and exchange_net >= 0:
        return WhaleState.ACCUMULATING
    if net < 0 and dist > acc:
        return WhaleState.DISTRIBUTING
    return WhaleState.NEUTRAL


def risk_score(req: IntelligenceRequest) -> tuple[int, list[str]]:
    r = 15.0
    flags: list[str] = []
    sec = req.security
    market = req.market
    social = req.social
    whales = req.whales

    if sec:
        if sec.honeypot:
            r += 70
            flags.append("honeypot signal")
        if sec.mintable:
            r += 18
            flags.append("token supply is mintable")
        if sec.blacklistable:
            r += 12
            flags.append("blacklist authority detected")
        if sec.pausable:
            r += 8
            flags.append("trading/transfer pause authority detected")
        if sec.liquidity_locked is False:
            r += 18
            flags.append("liquidity is not verified locked/burned")
        if sec.top10_holder_pct is not None and sec.top10_holder_pct > 50:
            r += min(22, (sec.top10_holder_pct - 50) * 0.6)
            flags.append("high top-10 holder concentration")
        if sec.insider_pct is not None and sec.insider_pct > 15:
            r += min(20, (sec.insider_pct - 15) * 0.8)
            flags.append("elevated insider-linked concentration")
        if (sec.sell_tax_pct or 0) > 10:
            r += 15
            flags.append("high sell tax")
        if sec.open_source is False:
            r += 12
            flags.append("contract source is not verified/open")

    if market:
        cap = market.market_cap_usd or 0
        liq = market.liquidity_usd or 0
        if cap > 0:
            liq_ratio = liq / cap
            if liq_ratio < 0.03:
                r += 22
                flags.append("liquidity is thin relative to market cap")
            elif liq_ratio < 0.08:
                r += 10
                flags.append("liquidity/market-cap ratio is weak")
        if market.volume_24h_usd and liq and market.volume_24h_usd / liq > 12:
            r += 10
            flags.append("volume/liquidity ratio is unusually high")

    if social:
        if social.organic_score is not None and social.organic_score < 0.35:
            r += 16
            flags.append("social activity appears heavily coordinated/shilled")
        if (social.influencer_concentration or 0) > 0.75:
            r += 10
            flags.append("attention is concentrated among few influencers")

    if whales and (whales.suspicious_flow_score or 0) > 0.65:
        r += 15
        flags.append("wallet flows show manipulation/coordination risk")

    return int(round(clamp(r))), flags


def opportunity_score(req: IntelligenceRequest, stage: NarrativeStage, whales: WhaleState, risk: int) -> int:
    score = 35.0

    stage_bonus = {
        NarrativeStage.EARLY: 24,
        NarrativeStage.HEATING_UP: 17,
        NarrativeStage.CROWDED: 5,
        NarrativeStage.FADING: -14,
        NarrativeStage.DEAD: -20,
    }
    score += stage_bonus[stage]

    if whales == WhaleState.ACCUMULATING:
        score += 14
    elif whales == WhaleState.DISTRIBUTING:
        score -= 20

    m = req.market
    if m:
        if (m.buy_sell_ratio or 0) >= 1.5:
            score += 8
        if (m.holder_growth_pct or 0) >= 10:
            score += 8
        if (m.tx_growth_pct or 0) >= 15:
            score += 7
        if m.market_cap_usd and m.liquidity_usd:
            ratio = m.liquidity_usd / m.market_cap_usd
            if ratio >= 0.15:
                score += 8
            elif ratio < 0.03:
                score -= 12

    if req.fundamentals_score is not None:
        score += (req.fundamentals_score - 50) * 0.15

    score -= risk * 0.38
    return int(round(clamp(score)))


def confidence_score(req: IntelligenceRequest) -> int:
    m = req.market
    s = req.social
    w = req.whales
    sec = req.security

    possible = 18
    present = 0
    if m:
        present += _known(
            m.market_cap_usd,
            m.liquidity_usd,
            m.volume_24h_usd,
            m.buy_sell_ratio,
            m.holder_growth_pct,
            m.tx_growth_pct,
        )
    if s:
        present += _known(
            s.mention_growth_5m,
            s.mention_growth_1h,
            s.mention_growth_24h,
            s.sentiment_score,
            s.organic_score,
        )
    if w:
        present += _known(
            w.net_flow_usd,
            w.accumulating_wallets,
            w.distributing_wallets,
        )
    if sec:
        present += _known(
            sec.top10_holder_pct,
            sec.insider_pct,
            sec.liquidity_locked,
            sec.honeypot,
        )

    confidence = 20 + (present / possible) * 75
    if req.source_freshness_minutes is not None:
        if req.source_freshness_minutes <= 15:
            confidence += 5
        elif req.source_freshness_minutes > 240:
            confidence -= 15

    return int(round(clamp(confidence)))


def rug_label(score: int) -> RugRisk:
    if score >= 85:
        return RugRisk.EXTREME
    if score >= 65:
        return RugRisk.HIGH
    if score >= 40:
        return RugRisk.MEDIUM
    return RugRisk.LOW


def action_label(opportunity: int, risk: int, confidence: int) -> Action:
    if risk >= 75:
        return Action.AVOID
    if confidence < 45:
        return Action.RESEARCH_MORE
    if opportunity >= 65 and risk < 55:
        return Action.WATCH
    return Action.WAIT


def analyze(req: IntelligenceRequest) -> IntelligenceResponse:
    stage = narrative_stage(req)
    whales = whale_state(req)
    risk, red_flags = risk_score(req)
    opportunity = opportunity_score(req, stage, whales, risk)
    confidence = confidence_score(req)
    action = action_label(opportunity, risk, confidence)

    reasons = [
        f"narrative stage={stage}",
        f"whale state={whales}",
        f"risk={risk}/100",
        f"opportunity={opportunity}/100",
        f"confidence={confidence}/100",
    ]

    invalidations = [
        "attention acceleration reverses while price/volume remain elevated",
        "whale state flips to DISTRIBUTING",
        "liquidity is removed or liquidity/market-cap ratio deteriorates materially",
        "new contract/holder concentration risk appears",
    ]
    watch_next = [
        "5m→1h→24h mention acceleration and unique-author growth",
        "holder and transaction growth versus price",
        "net whale flow and exchange inflows/outflows",
        "liquidity depth, LP changes, and realistic exit slippage",
        "security/permission changes and deployer-linked wallet activity",
    ]

    return IntelligenceResponse(
        token=req.token,
        narrative=stage,
        whales=whales,
        rug_risk=rug_label(risk),
        action=action,
        scores=Scores(opportunity=opportunity, risk=risk, confidence=confidence),
        reasons=reasons,
        red_flags=red_flags,
        invalidations=invalidations,
        watch_next=watch_next,
    )
