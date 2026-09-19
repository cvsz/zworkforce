from __future__ import annotations

from pydantic import BaseModel, Field


class OrderBookLevel(BaseModel):
    price: float = Field(gt=0, lt=1)
    size: float = Field(gt=0)


class OrderBook(BaseModel):
    token_id: str = Field(min_length=1)
    bids: list[OrderBookLevel] = Field(default_factory=list)
    asks: list[OrderBookLevel] = Field(default_factory=list)


class MarketQuote(BaseModel):
    market_id: str = Field(min_length=1)
    token_id: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    best_bid: float | None = Field(default=None, gt=0, lt=1)
    best_ask: float | None = Field(default=None, gt=0, lt=1)
    available_bid: float = Field(default=0, ge=0)
    available_ask: float = Field(default=0, ge=0)
    timestamp: str | None = None


class ArbitrageRequest(BaseModel):
    market_id: str = Field(min_length=1)
    yes: MarketQuote
    no: MarketQuote
    capital_usd: float = Field(gt=0)
    fee_bps: float = Field(default=0, ge=0, le=500)
    slippage_bps: float = Field(default=0, ge=0, le=1000)
    latency_bps: float = Field(default=0, ge=0, le=1000)
    min_edge_bps: float = Field(default=25, ge=0, le=5000)


class ArbitrageOpportunity(BaseModel):
    market_id: str
    executable: bool
    strategy: str
    gross_edge_bps: float
    estimated_cost_bps: float
    net_edge_bps: float
    max_capital_usd: float
    estimated_profit_usd: float
    limiting_liquidity_usd: float
    reasons: list[str] = Field(default_factory=list)
