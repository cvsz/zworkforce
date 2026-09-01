# apps/ztrader/backend/src/ztrader/engine/strategy.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from ztrader.engine.risk import StrategyIntent

@dataclass(frozen=True)
class Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float

class Strategy(ABC):
    """Strategies emit intents only; they never execute orders directly."""
    id: str
    symbol: str

    @abstractmethod
    def generate_intent(self, candles: List[Candle]) -> Optional[StrategyIntent]:
        pass

class MovingAverageCrossoverStrategy(Strategy):
    def __init__(
        self,
        symbol: str = "BTC/USDT",
        fast: int = 3,
        slow: int = 5,
        notional: float = 25.0,
    ) -> None:
        if fast <= 0 or slow <= 0 or fast >= slow:
            raise ValueError("fast must be positive and lower than slow")
        self.id = "ma-crossover-paper"
        self.symbol = symbol
        self.fast = fast
        self.slow = slow
        self.notional = notional

    def generate_intent(self, candles: List[Candle]) -> Optional[StrategyIntent]:
        if len(candles) < self.slow:
            return None
        closes = [c.close for c in candles]
        fast_avg = sum(closes[-self.fast :]) / self.fast
        slow_avg = sum(closes[-self.slow :]) / self.slow
        if fast_avg > slow_avg:
            return StrategyIntent(
                symbol=self.symbol,
                side="buy",
                notional=self.notional,
                strategy_id=self.id,
                request_id="", # Assigned by caller or default
            )
        if fast_avg < slow_avg:
            return StrategyIntent(
                symbol=self.symbol,
                side="sell",
                notional=self.notional,
                strategy_id=self.id,
                request_id="", # Assigned by caller or default
            )
        return None


class ScalpStrategy(Strategy):
    """Short-term scalping strategy using price momentum."""

    def __init__(self, symbol: str = "BTC/USDT", notional: float = 25.0) -> None:
        self.id = "scalp-paper"
        self.symbol = symbol
        self.notional = notional

    def generate_intent(self, candles: List[Candle]) -> Optional[StrategyIntent]:
        if len(candles) < 3:
            return None
        closes = [c.close for c in candles[-3:]]
        # Buy if last two candles are bullish, sell if bearish
        if closes[-1] > closes[-2] > closes[-3]:
            return StrategyIntent(
                symbol=self.symbol,
                side="buy",
                notional=self.notional,
                strategy_id=self.id,
                request_id="",
            )
        if closes[-1] < closes[-2] < closes[-3]:
            return StrategyIntent(
                symbol=self.symbol,
                side="sell",
                notional=self.notional,
                strategy_id=self.id,
                request_id="",
            )
        return None


class SwingStrategy(Strategy):
    """Swing trading strategy based on support/resistance breakouts."""

    def __init__(self, symbol: str = "BTC/USDT", notional: float = 25.0, lookback: int = 10) -> None:
        self.id = "swing-paper"
        self.symbol = symbol
        self.notional = notional
        self.lookback = lookback

    def generate_intent(self, candles: List[Candle]) -> Optional[StrategyIntent]:
        if len(candles) < self.lookback + 1:
            return None
        window = candles[-(self.lookback + 1):-1]
        current = candles[-1]
        resistance = max(c.high for c in window)
        support = min(c.low for c in window)
        if current.close > resistance:
            return StrategyIntent(
                symbol=self.symbol,
                side="buy",
                notional=self.notional,
                strategy_id=self.id,
                request_id="",
            )
        if current.close < support:
            return StrategyIntent(
                symbol=self.symbol,
                side="sell",
                notional=self.notional,
                strategy_id=self.id,
                request_id="",
            )
        return None


class PositionStrategy(Strategy):
    """Long-term position/trend-following strategy using a simple moving average."""

    def __init__(self, symbol: str = "BTC/USDT", notional: float = 25.0, period: int = 20) -> None:
        self.id = "position-paper"
        self.symbol = symbol
        self.notional = notional
        self.period = period

    def generate_intent(self, candles: List[Candle]) -> Optional[StrategyIntent]:
        if len(candles) < self.period + 1:
            return None
        closes = [c.close for c in candles]
        sma = sum(closes[-self.period:]) / self.period
        current_close = closes[-1]
        prev_close = closes[-2]
        # Buy when price crosses above SMA, sell when it crosses below
        if prev_close <= sma < current_close:
            return StrategyIntent(
                symbol=self.symbol,
                side="buy",
                notional=self.notional,
                strategy_id=self.id,
                request_id="",
            )
        if prev_close >= sma > current_close:
            return StrategyIntent(
                symbol=self.symbol,
                side="sell",
                notional=self.notional,
                strategy_id=self.id,
                request_id="",
            )
        return None
