from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class SignalAction(str, Enum):
    ENTER_LONG = "enter_long"
    ENTER_SHORT = "enter_short"
    EXIT = "exit"
    HOLD = "hold"


class RegimeMode(str, Enum):
    TREND = "trend"
    MEAN_REVERSION = "mean_reversion"
    HIGH_VOLATILITY = "high_volatility"


class StrategyKind(str, Enum):
    SCALP = "scalp"
    SWING = "swing"
    POSITION = "position"


class Position(BaseModel):
    """Immutable audit-friendly portfolio position record.

    PositionManager is the only component that should create or remove these records.
    Keeping the model frozen makes accidental out-of-band mutation impossible and
    preserves the trace_id/open_time data needed to reconstruct an order lifecycle.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    strategy_id: str
    symbol: str
    side: Literal["LONG", "SHORT"]
    size: float
    entry_price: float
    leverage: int
    margin_used: float
    open_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    regime_at_open: str
    trace_id: str

    @property
    def notional_value(self) -> float:
        return self.size * self.entry_price

    @property
    def strategy_kind(self) -> StrategyKind | None:
        try:
            return StrategyKind(self.strategy_id)
        except ValueError:
            return None


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    timeframe: str
    ohlcv: list[list[float]]
    ticker: dict[str, Any]
    orderbook: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def with_bounded_ohlcv(self, max_candles: int) -> "MarketSnapshot":
        """Return a copy retaining only the latest candles for memory safety."""
        bounded = self.ohlcv[-max_candles:] if max_candles > 0 else []
        return MarketSnapshot(
            symbol=self.symbol,
            timeframe=self.timeframe,
            ohlcv=bounded,
            ticker=self.ticker,
            orderbook=self.orderbook,
            timestamp=self.timestamp,
        )


@dataclass
class TradeSignal:
    symbol: str
    strategy: StrategyKind
    action: SignalAction
    confidence: float
    size_usdt: float
    regime: RegimeMode
    trace_id: str = field(default_factory=lambda: uuid4().hex)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PositionIntent:
    signal: TradeSignal
    side: Side
    amount: float
    notional_usdt: float
    leverage: int
    reduce_only: bool = False


@dataclass
class OpenPosition:
    symbol: str
    strategy: StrategyKind
    notional_usdt: float
    side: Side
    entry_price: float
    amount: float
    trace_id: str
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
