from __future__ import annotations

from dataclasses import dataclass

from zkbtrader.models import PaperPortfolio
from zkbtrader.paper import PaperExecutionEngine
from zkbtrader.risk import RiskEngine, RiskLimits
from zkbtrader.strategy import Candle, Strategy


@dataclass(frozen=True)
class BacktestResult:
    strategy_id: str
    candles_seen: int
    orders_created: int
    ending_usdt: float
    ending_btc: float


class BacktestEngine:
    """Deterministic replay engine using the same risk and paper execution path."""

    def __init__(self, *, starting_usdt: float = 1000.0, starting_btc: float = 0.0) -> None:
        self.paper = PaperExecutionEngine(PaperPortfolio(usdt=starting_usdt, btc=starting_btc))
        self.risk = RiskEngine(limits=RiskLimits())

    def run(self, strategy: Strategy, candles: list[Candle]) -> BacktestResult:
        for idx in range(1, len(candles) + 1):
            window = candles[:idx]
            intent = strategy.generate_intent(window)
            if intent is None:
                continue
            try:
                self.paper.execute(intent, price=window[-1].close, risk=self.risk)
            except ValueError:
                continue

        return BacktestResult(
            strategy_id=strategy.id,
            candles_seen=len(candles),
            orders_created=len(self.paper.orders),
            ending_usdt=self.paper.portfolio.usdt,
            ending_btc=self.paper.portfolio.btc,
        )
