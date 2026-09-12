from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class NarrativeStage(StrEnum):
    EARLY = "EARLY"
    HEATING_UP = "HEATING_UP"
    CROWDED = "CROWDED"
    FADING = "FADING"
    DEAD = "DEAD"


class WhaleState(StrEnum):
    ACCUMULATING = "ACCUMULATING"
    NEUTRAL = "NEUTRAL"
    DISTRIBUTING = "DISTRIBUTING"


class RugRisk(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class Action(StrEnum):
    WATCH = "WATCH"
    WAIT = "WAIT"
    RESEARCH_MORE = "RESEARCH_MORE"
    AVOID = "AVOID"


class TokenRef(BaseModel):
    symbol: str
    chain: str
    address: str | None = None
    goplus_chain_id: str | None = None


class MarketSnapshot(BaseModel):
    price_usd: float | None = None
    market_cap_usd: float | None = None
    fdv_usd: float | None = None
    liquidity_usd: float | None = None
    volume_24h_usd: float | None = None
    buy_sell_ratio: float | None = None
    holder_growth_pct: float | None = None
    tx_growth_pct: float | None = None


class SocialSnapshot(BaseModel):
    mention_growth_5m: float | None = None
    mention_growth_1h: float | None = None
    mention_growth_24h: float | None = None
    mention_growth_7d: float | None = None
    sentiment_score: float | None = Field(default=None, ge=-1, le=1)
    organic_score: float | None = Field(default=None, ge=0, le=1)
    influencer_concentration: float | None = Field(default=None, ge=0, le=1)
    excerpts: list[str] = Field(default_factory=list)


class WhaleSnapshot(BaseModel):
    net_flow_usd: float | None = None
    accumulating_wallets: int | None = None
    distributing_wallets: int | None = None
    exchange_inflow_usd: float | None = None
    exchange_outflow_usd: float | None = None
    suspicious_flow_score: float | None = Field(default=None, ge=0, le=1)


class SecuritySnapshot(BaseModel):
    top10_holder_pct: float | None = Field(default=None, ge=0, le=100)
    insider_pct: float | None = Field(default=None, ge=0, le=100)
    liquidity_locked: bool | None = None
    honeypot: bool | None = None
    mintable: bool | None = None
    blacklistable: bool | None = None
    pausable: bool | None = None
    sell_tax_pct: float | None = Field(default=None, ge=0)
    buy_tax_pct: float | None = Field(default=None, ge=0)
    open_source: bool | None = None


class IntelligenceRequest(BaseModel):
    token: TokenRef
    market: MarketSnapshot | None = None
    social: SocialSnapshot | None = None
    whales: WhaleSnapshot | None = None
    security: SecuritySnapshot | None = None
    fundamentals_score: float | None = Field(default=None, ge=0, le=100)
    source_freshness_minutes: float | None = Field(default=None, ge=0)
    use_grok_summary: bool = False


class Scores(BaseModel):
    opportunity: int = Field(ge=0, le=100)
    risk: int = Field(ge=0, le=100)
    confidence: int = Field(ge=0, le=100)


class IntelligenceResponse(BaseModel):
    token: TokenRef
    narrative: NarrativeStage
    whales: WhaleState
    rug_risk: RugRisk
    action: Action
    scores: Scores
    reasons: list[str]
    red_flags: list[str]
    invalidations: list[str]
    watch_next: list[str]
    grok_summary: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
