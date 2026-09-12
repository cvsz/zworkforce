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
from .narrative import attention_velocity


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def _known(*values: object) -> int:
    return sum(value is not None for value in values)


def narrative_stage(req: IntelligenceRequest) -> NarrativeStage:
    velocity = attention_velocity(req.social)
    if velocity.stage != NarrativeStage.DEAD:
        return velocity.stage

    social = req.social
    if social is None:
        return NarrativeStage.DEAD
    sentiment = social.sentiment_score or 0
    growth = [
        value
        for value in (
            social.mention_growth_5m,
            social.mention_growth_1h,
            social.mention_growth_24h,
        )
        if value is not None
    ]
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
    smart_delta = (w.new_smart_money_entries or 0) - (w.smart_money_exits or 0)

    if net > 0 and acc > dist and exchange_net >= 0 and smart_delta >= 0:
        return WhaleState.ACCUMULATING
    if net < 0 and dist > acc:
        return WhaleState.DISTRIBUTING
    return WhaleState.NEUTRAL


def risk_score(req: IntelligenceRequest) -> tuple[int, list[str]]:
    score = 15.0
    flags: list[str] = []
    sec = req.security
    market = req.market
    social = req.social
    whales = req.whales

    if sec:
        if sec.honeypot:
            score += 70
            flags.append("honeypot signal")
        if sec.mintable:
            score += 18
            flags.append("token supply is mintable")
        if sec.blacklistable:
            score += 12
            flags.append("blacklist authority detected")
        if sec.pausable:
            score += 8
            flags.append("trading/transfer pause authority detected")
        if sec.liquidity_locked is False:
            score += 18
            flags.append("liquidity is not verified locked/burned")
        if sec.lp_lock_pct is not None and sec.lp_lock_pct < 70:
            score += 12
            flags.append("LP lock percentage is weak")
        if sec.top10_holder_pct is not None and sec.top10_holder_pct > 50:
            score += min(22, (sec.top10_holder_pct - 50) * 0.6)
            flags.append("high top-10 holder concentration")
        if sec.insider_pct is not None and sec.insider_pct > 15:
            score += min(20, (sec.insider_pct - 15) * 0.8)
            flags.append("elevated insider-linked concentration")
        if (sec.sell_tax_pct or 0) > 10:
            score += 15
            flags.append("high sell tax")
        if sec.open_source is False:
            score += 12
            flags.append("contract source is not verified/open")
        if sec.owner_renounced is False:
            score += 8
            flags.append("owner privileges remain active")
        if sec.suspicious_deployer:
            score += 20
            flags.append("deployer history is suspicious")
        if (sec.deployer_previous_tokens or 0) >= 10:
            score += 8
            flags.append("deployer has unusually high prior token count")

    if market:
        cap = market.market_cap_usd or 0
        liquidity = market.liquidity_usd or 0
        if cap > 0:
            ratio = liquidity / cap
            if ratio < 0.03:
                score += 22
                flags.append("liquidity is thin relative to market cap")
            elif ratio < 0.08:
                score += 10
                flags.append("liquidity/market-cap ratio is weak")
        if market.volume_24h_usd and liquidity and market.volume_24h_usd / liquidity > 12:
            score += 10
            flags.append("volume/liquidity ratio is unusually high")
        if market.pair_age_minutes is not None and market.pair_age_minutes < 30:
            score += 10
            flags.append("pair is extremely new")

    if social:
        velocity = attention_velocity(social)
        if velocity.organic_score < 35:
            score += 16
            flags.append("social activity appears heavily coordinated/shilled")
        if (social.influencer_concentration or 0) > 0.75:
            score += 10
            flags.append("attention is concentrated among few influencers")

    if whales:
        if (whales.suspicious_flow_score or 0) > 0.65:
            score += 15
            flags.append("wallet flows show manipulation/coordination risk")
        if (whales.linked_wallet_score or 0) > 0.7:
            score += 12
            flags.append("linked-wallet concentration is high")

    return round(clamp(score)), flags


def opportunity_score(
    req: IntelligenceRequest,
    stage: NarrativeStage,
    whales: WhaleState,
    risk: int,
) -> int:
    score = 35.0
    score += {
        NarrativeStage.EARLY: 24,
        NarrativeStage.HEATING_UP: 17,
        NarrativeStage.CROWDED: 5,
        NarrativeStage.FADING: -14,
        NarrativeStage.DEAD: -20,
    }[stage]

    if whales == WhaleState.ACCUMULATING:
        score += 14
    elif whales == WhaleState.DISTRIBUTING:
        score -= 20

    market = req.market
    if market:
        if (market.buy_sell_ratio or 0) >= 1.5:
            score += 8
        if (market.holder_growth_pct or 0) >= 10:
            score += 8
        if (market.tx_growth_pct or 0) >= 15:
            score += 7
        if (market.price_change_5m_pct or 0) > 20 and (market.price_change_1h_pct or 0) > 50:
            score -= 8
        if market.market_cap_usd and market.liquidity_usd:
            ratio = market.liquidity_usd / market.market_cap_usd
            if ratio >= 0.15:
                score += 8
            elif ratio < 0.03:
                score -= 12

    if req.fundamentals_score is not None:
        score += (req.fundamentals_score - 50) * 0.15

    score -= risk * 0.38
    return round(clamp(score))


def confidence_score(req: IntelligenceRequest) -> int:
    market = req.market
    social = req.social
    whales = req.whales
    security = req.security

    possible = 26
    present = 0
    if market:
        present += _known(
            market.market_cap_usd,
            market.liquidity_usd,
            market.volume_24h_usd,
            market.buy_sell_ratio,
            market.holder_growth_pct,
            market.tx_growth_pct,
            market.price_change_5m_pct,
            market.price_change_1h_pct,
        )
    if social:
        present += _known(
            social.mention_growth_5m,
            social.mention_growth_1h,
            social.mention_growth_24h,
            social.sentiment_score,
            social.organic_score,
            social.unique_author_growth_pct,
            social.repeated_content_score,
            social.bot_score,
        )
    if whales:
        present += _known(
            whales.net_flow_usd,
            whales.accumulating_wallets,
            whales.distributing_wallets,
            whales.new_smart_money_entries,
            whales.smart_money_exits,
        )
    if security:
        present += _known(
            security.top10_holder_pct,
            security.insider_pct,
            security.liquidity_locked,
            security.honeypot,
            security.open_source,
        )

    confidence = 20 + (present / possible) * 75
    if req.source_freshness_minutes is not None:
        if req.source_freshness_minutes <= 15:
            confidence += 5
        elif req.source_freshness_minutes > 240:
            confidence -= 15
    return round(clamp(confidence))


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

    return IntelligenceResponse(
        token=req.token,
        narrative=stage,
        whales=whales,
        rug_risk=rug_label(risk),
        action=action,
        scores=Scores(opportunity=opportunity, risk=risk, confidence=confidence),
        reasons=[
            f"narrative stage={stage}",
            f"whale state={whales}",
            f"risk={risk}/100",
            f"opportunity={opportunity}/100",
            f"confidence={confidence}/100",
        ],
        red_flags=red_flags,
        invalidations=[
            "attention acceleration reverses while price/volume remain elevated",
            "whale state flips to DISTRIBUTING",
            "liquidity is removed or liquidity/market-cap ratio deteriorates materially",
            "new contract/holder/deployer concentration risk appears",
        ],
        watch_next=[
            "5m→1h→24h mention acceleration and unique-author growth",
            "holder and transaction growth versus price",
            "net whale flow and exchange inflows/outflows",
            "liquidity depth, LP changes, and realistic exit slippage",
            "security/permission changes and deployer-linked wallet activity",
        ],
    )
