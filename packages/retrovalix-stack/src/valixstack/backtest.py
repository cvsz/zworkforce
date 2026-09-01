from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .broker import PaperBroker, RiskRejected
from .core import RiskLimits, Side, Tick
from .strategy import ProbabilityEdgeStrategy


@dataclass(frozen=True)
class BacktestResult:
    pnl: float
    fills: int
    ending_cash: float
    winner: Side
    max_exposure: float


def load_ticks(path: str | Path) -> list[Tick]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return [Tick(**{k: int(v) if k == "timestamp" else float(v) for k, v in row.items()}) for row in rows]


def run_backtest(ticks: list[Tick], starting_cash: float = 1_000.0, limits: RiskLimits | None = None) -> BacktestResult:
    if not ticks:
        raise ValueError("backtest requires at least one tick")
    limits = limits or RiskLimits()
    broker = PaperBroker(starting_cash, limits)
    strategy = ProbabilityEdgeStrategy(limits.min_edge)
    max_exposure = 0.0
    for tick in ticks:
        signal = strategy.signal(tick)
        if signal is None:
            continue
        size = min(limits.max_order_usd, max(1.0, signal.edge * 100.0))
        try:
            broker.buy(signal.side, signal.market_price, size)
            max_exposure = max(max_exposure, broker.position.gross_exposure)
        except RiskRejected:
            continue
    winner = Side.UP if ticks[-1].spot >= ticks[-1].reference else Side.DOWN
    pnl = broker.settle(winner)
    return BacktestResult(pnl, len(broker.fills), broker.cash, winner, max_exposure)

