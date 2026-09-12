from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class DiscoveryVerdict(StrEnum):
    EARLY = "EARLY"
    WATCH = "WATCH"
    SKIP = "SKIP"


class TradeVerdict(StrEnum):
    ENTER = "ENTER"
    WAIT = "WAIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    EXIT = "EXIT"


class RiskProfile(StrEnum):
    CONSERVATIVE = "Conservative"
    MODERATE = "Moderate"
    AGGRESSIVE = "Aggressive"


class Horizon(StrEnum):
    SHORT = "Short"
    MEDIUM = "Medium"
    LONG = "Long"


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
    price_change_5m_pct: float | None = None
    price_change_1h_pct: float | None = None
    price_change_24h_pct: float | None = None
    pair_age_minutes: float | None = Field(default=None, ge=0)
    unique_makers_24h: int | None = Field(default=None, ge=0)


class SocialSnapshot(BaseModel):
    mention_growth_5m: float | None = None
    mention_growth_1h: float | None = None
    mention_growth_24h: float | None = None
    mention_growth_7d: float | None = None
    sentiment_score: float | None = Field(default=None, ge=-1, le=1)
    organic_score: float | None = Field(default=None, ge=0, le=1)
    influencer_concentration: float | None = Field(default=None, ge=0, le=1)
    unique_author_growth_pct: float | None = None
    repeated_content_score: float | None = Field(default=None, ge=0, le=1)
    bot_score: float | None = Field(default=None, ge=0, le=1)
    excerpts: list[str] = Field(default_factory=list)


class WhaleSnapshot(BaseModel):
    net_flow_usd: float | None = None
    accumulating_wallets: int | None = None
    distributing_wallets: int | None = None
    exchange_inflow_usd: float | None = None
    exchange_outflow_usd: float | None = None
    suspicious_flow_score: float | None = Field(default=None, ge=0, le=1)
    new_smart_money_entries: int | None = Field(default=None, ge=0)
    smart_money_exits: int | None = Field(default=None, ge=0)
    linked_wallet_score: float | None = Field(default=None, ge=0, le=1)


class SecuritySnapshot(BaseModel):
    top10_holder_pct: float | None = Field(default=None, ge=0, le=100)
    insider_pct: float | None = Field(default=None, ge=0, le=100)
    liquidity_locked: bool | None = None
    lp_lock_pct: float | None = Field(default=None, ge=0, le=100)
    honeypot: bool | None = None
    mintable: bool | None = None
    blacklistable: bool | None = None
    pausable: bool | None = None
    sell_tax_pct: float | None = Field(default=None, ge=0)
    buy_tax_pct: float | None = Field(default=None, ge=0)
    open_source: bool | None = None
    owner_renounced: bool | None = None
    suspicious_deployer: bool | None = None
    deployer_previous_tokens: int | None = Field(default=None, ge=0)


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


class AttentionVelocity(BaseModel):
    acceleration_score: float = Field(ge=-100, le=100)
    organic_score: float = Field(ge=0, le=100)
    stage: NarrativeStage
    reasons: list[str]


class DiscoveryRequest(BaseModel):
    candidates: list[IntelligenceRequest] = Field(min_length=1, max_length=200)
    max_market_cap_usd: float = Field(default=1_000_000, gt=0)
    min_liquidity_usd: float = Field(default=10_000, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class DiscoveryCandidate(BaseModel):
    rank: int
    token: TokenRef
    verdict: DiscoveryVerdict
    score: float
    intelligence: IntelligenceResponse


class DiscoveryResponse(BaseModel):
    candidates: list[DiscoveryCandidate]
    filtered_count: int


class LiveDiscoveryRequest(BaseModel):
    max_market_cap_usd: float = Field(default=1_000_000, gt=0)
    min_liquidity_usd: float = Field(default=10_000, ge=0)
    chains: list[str] = Field(default_factory=lambda: ["solana", "base", "bsc"])
    limit: int = Field(default=20, ge=1, le=50)


class WalletTransfer(BaseModel):
    wallet: str
    direction: str
    usd_value: float
    counterparty_type: str = "unknown"
    is_new_wallet: bool = False
    is_known_smart_money: bool = False
    linked_cluster: str | None = None


class SmartMoneyRequest(BaseModel):
    token: TokenRef
    transfers: list[WalletTransfer] = Field(min_length=1, max_length=5000)


class SmartMoneyResponse(BaseModel):
    state: WhaleState
    net_flow_usd: float
    smart_money_net_usd: float
    accumulation_wallets: int
    distribution_wallets: int
    new_smart_money_entries: int
    manipulation_risk: float = Field(ge=0, le=100)
    clusters: dict[str, float]


class TradePlanRequest(BaseModel):
    token: TokenRef
    current_price: float = Field(gt=0)
    support: float | None = Field(default=None, gt=0)
    resistance: float | None = Field(default=None, gt=0)
    atr_pct: float = Field(default=6.0, gt=0, le=100)
    account_equity_usd: float = Field(default=10_000, gt=0)
    risk_per_trade_pct: float = Field(default=1.0, gt=0, le=5)
    intelligence: IntelligenceResponse | None = None


class TradePlanResponse(BaseModel):
    verdict: TradeVerdict
    entry_zone: tuple[float, float]
    dca_levels: list[float]
    take_profit_levels: list[float]
    stop_loss: float
    max_position_usd: float
    risk_reward_estimate: float
    reasons: list[str]


class PortfolioCandidate(BaseModel):
    token: TokenRef
    intelligence: IntelligenceResponse
    category: str = "high-risk"


class PortfolioRequest(BaseModel):
    capital_usd: float = Field(gt=0)
    risk: RiskProfile
    horizon: Horizon
    candidates: list[PortfolioCandidate] = Field(min_length=1, max_length=100)


class PortfolioAllocation(BaseModel):
    token: TokenRef
    weight_pct: float
    amount_usd: float
    category: str
    max_loss_budget_usd: float


class PortfolioResponse(BaseModel):
    allocations: list[PortfolioAllocation]
    reserve_pct: float
    rebalance_trigger_pct: float
    notes: list[str]


class BacktestPoint(BaseModel):
    timestamp: str
    opportunity_score: int = Field(ge=0, le=100)
    risk_score: int = Field(ge=0, le=100)
    confidence_score: int = Field(ge=0, le=100)
    forward_return_pct: float


class BacktestRequest(BaseModel):
    points: list[BacktestPoint] = Field(min_length=2, max_length=100_000)
    min_opportunity: int = Field(default=65, ge=0, le=100)
    max_risk: int = Field(default=55, ge=0, le=100)
    min_confidence: int = Field(default=50, ge=0, le=100)


class BacktestResponse(BaseModel):
    total_points: int
    triggered_signals: int
    win_rate_pct: float
    average_return_pct: float
    median_return_pct: float
    max_drawdown_pct: float
    precision_positive: float


class AlertRule(BaseModel):
    min_opportunity: int = Field(default=70, ge=0, le=100)
    max_risk: int = Field(default=50, ge=0, le=100)
    min_confidence: int = Field(default=55, ge=0, le=100)
    narratives: list[NarrativeStage] = Field(
        default_factory=lambda: [NarrativeStage.EARLY, NarrativeStage.HEATING_UP]
    )
    whale_states: list[WhaleState] = Field(
        default_factory=lambda: [WhaleState.ACCUMULATING, WhaleState.NEUTRAL]
    )


class AlertEvaluation(BaseModel):
    matched: bool
    reasons: list[str]


class AlertRequest(BaseModel):
    intelligence: IntelligenceResponse
    rule: AlertRule = Field(default_factory=AlertRule)


class WatchlistEntry(BaseModel):
    token: TokenRef
    note: str = ""


class OnchainEvidenceLookup(BaseModel):
    trace_id: str = Field(min_length=1, max_length=128)
    token: TokenRef


class AdvisoryScoresV11(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity: int = Field(ge=0, le=100)
    risk: int = Field(ge=0, le=100)
    confidence: int = Field(ge=0, le=100)


class ProposedPaperTradeV11(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["paper"]
    side: Literal["buy", "sell"]
    order_type: Literal["limit"]
    entry_low: float | None = Field(default=None, gt=0)
    entry_high: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit_levels: list[float] = Field(default_factory=list)
    max_position_usd: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_entry_band(self) -> ProposedPaperTradeV11:
        if (
            self.entry_low is not None
            and self.entry_high is not None
            and self.entry_low > self.entry_high
        ):
            raise ValueError("entry_low must be <= entry_high")
        return self


class AdvisoryIntentV11(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1.1"]
    tenant_id: str = Field(min_length=1, max_length=128)
    account_ref: str = Field(min_length=1, max_length=256)
    portfolio_ref: str | None = Field(default=None, max_length=256)
    signal_id: str = Field(min_length=1, max_length=128)
    trace_id: str | None = Field(default=None, max_length=128)
    symbol: str = Field(min_length=1, max_length=64)
    chain: str = Field(min_length=1, max_length=64)
    address: str = Field(min_length=1, max_length=256)
    scores: AdvisoryScoresV11
    narrative: Literal["EARLY", "HEATING_UP", "CROWDED", "FADING", "DEAD"]
    whales: Literal["ACCUMULATING", "NEUTRAL", "DISTRIBUTING"]
    rug_risk: Literal["LOW", "MEDIUM", "HIGH", "EXTREME"]
    action: Literal["WATCH", "WAIT", "RESEARCH_MORE", "AVOID"]
    evidence_timestamp: datetime
    invalidations: list[str] = Field(default_factory=list)
    proposed_trade: ProposedPaperTradeV11
    evidence: dict[str, Any] = Field(default_factory=dict)


class AdvisoryIntentSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: AdvisoryIntentV11
