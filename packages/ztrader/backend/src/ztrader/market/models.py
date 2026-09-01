from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class ExecutionMode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


class IntentSide(StrEnum):
    ENTER_LONG = "enter_long"
    EXIT_LONG = "exit_long"


class RiskDecisionStatus(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class StrategyIntent:
    symbol: str
    side: IntentSide
    notional: float
    strategy_id: str
    reason: str
    request_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class RiskDecision:
    status: RiskDecisionStatus
    reason_code: str
    request_id: str
    details: dict[str, str | float | int | bool] = field(default_factory=dict)


@dataclass(frozen=True)
class PaperOrder:
    id: str
    symbol: str
    side: IntentSide
    notional: float
    price: float
    base_amount: float
    fee: float
    strategy_id: str
    request_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class PaperPortfolio:
    usdt: float = 1000.0
    btc: float = 0.0

    @property
    def total_usdt_at_last_price(self) -> float:
        return self.usdt
