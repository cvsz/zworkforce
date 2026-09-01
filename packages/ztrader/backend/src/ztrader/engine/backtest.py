# apps/ztrader/backend/src/ztrader/engine/backtest.py

import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import numpy as np

from ztrader.engine.paper import PaperExecutionEngine, PaperPortfolio
from ztrader.engine.risk import RiskEngine
from ztrader.engine.strategy import Candle, Strategy

@dataclass(frozen=True)
class BacktestResult:
    strategy_id: str
    candles_seen: int
    orders_created: int
    starting_usdt: float
    ending_usdt: float
    ending_btc: float
    total_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    win_rate_pct: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    gross_profit: float
    gross_loss: float
    equity_curve: List[float] = field(default_factory=list)

class BacktestEngine:
    """Deterministic replay engine using identical risk and paper execution paths."""

    def __init__(self, allowed_symbols: tuple[str, ...], starting_usdt: float = 10000.0, starting_btc: float = 0.0) -> None:
        self.starting_usdt = starting_usdt
        self.starting_btc = starting_btc
        self.paper = PaperExecutionEngine(PaperPortfolio(usdt=starting_usdt, btc=starting_btc))
        # Backtest uses a local risk engine with kill switch = False for simulation
        self.risk = RiskEngine(
            allowed_symbols=allowed_symbols,
            max_order_notional=1000000.0, # Large limit for backtesting
            kill_switch=False
        )

    def run(self, strategy: Strategy, candles: List[Candle]) -> BacktestResult:
        orders = []
        equity_curve: List[float] = []
        trade_returns: List[float] = []
        winning_trades = 0
        losing_trades = 0
        gross_profit = 0.0
        gross_loss = 0.0

        prev_portfolio_val = self.starting_usdt

        for idx in range(1, len(candles) + 1):
            window = candles[:idx]
            current_candle = window[-1]
            intent = strategy.generate_intent(window)

            current_val = self.paper.portfolio.usdt + (self.paper.portfolio.btc * current_candle.close)
            equity_curve.append(current_val)

            if intent is not None:
                try:
                    import uuid
                    intent_with_id = intent
                    if not intent.request_id:
                        intent_with_id = intent.__class__(
                            symbol=intent.symbol,
                            side=intent.side,
                            notional=intent.notional,
                            strategy_id=intent.strategy_id,
                            request_id=str(uuid.uuid4())
                        )
                    order = self.paper.execute(intent_with_id, price=current_candle.close, risk=self.risk)
                    orders.append(order)

                    # Calculate return delta from previous position state
                    new_val = self.paper.portfolio.usdt + (self.paper.portfolio.btc * current_candle.close)
                    pnl = new_val - prev_portfolio_val
                    if pnl > 0:
                        winning_trades += 1
                        gross_profit += pnl
                        trade_returns.append(pnl / prev_portfolio_val if prev_portfolio_val > 0 else 0)
                    elif pnl < 0:
                        losing_trades += 1
                        gross_loss += abs(pnl)
                        trade_returns.append(pnl / prev_portfolio_val if prev_portfolio_val > 0 else 0)

                    prev_portfolio_val = new_val
                except ValueError:
                    pass

        ending_val = self.paper.portfolio.usdt + (self.paper.portfolio.btc * (candles[-1].close if candles else 0.0))
        total_return_pct = ((ending_val - self.starting_usdt) / self.starting_usdt) * 100.0 if self.starting_usdt > 0 else 0.0

        # Calculate Max Drawdown
        max_drawdown_pct = 0.0
        if equity_curve:
            peak = equity_curve[0]
            for val in equity_curve:
                if val > peak:
                    peak = val
                dd = (peak - val) / peak if peak > 0 else 0.0
                if dd > max_drawdown_pct:
                    max_drawdown_pct = dd
        max_drawdown_pct *= 100.0

        # Calculate Sharpe & Sortino
        daily_returns = np.diff(equity_curve) / np.maximum(equity_curve[:-1], 1e-9) if len(equity_curve) > 1 else np.array([])
        mean_ret = float(np.mean(daily_returns)) if len(daily_returns) > 0 else 0.0
        std_ret = float(np.std(daily_returns)) if len(daily_returns) > 0 else 0.0

        sharpe_ratio = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 1e-8 else 0.0

        downside_returns = daily_returns[daily_returns < 0]
        downside_std = float(np.std(downside_returns)) if len(downside_returns) > 0 else 0.0
        sortino_ratio = (mean_ret / downside_std * math.sqrt(252)) if downside_std > 1e-8 else 0.0

        total_trades = winning_trades + losing_trades
        win_rate_pct = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)

        return BacktestResult(
            strategy_id=strategy.id,
            candles_seen=len(candles),
            orders_created=len(orders),
            starting_usdt=self.starting_usdt,
            ending_usdt=self.paper.portfolio.usdt,
            ending_btc=self.paper.portfolio.btc,
            total_return_pct=round(total_return_pct, 2),
            sharpe_ratio=round(sharpe_ratio, 2),
            sortino_ratio=round(sortino_ratio, 2),
            max_drawdown_pct=round(max_drawdown_pct, 2),
            win_rate_pct=round(win_rate_pct, 2),
            profit_factor=round(profit_factor, 2),
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            gross_profit=round(gross_profit, 2),
            gross_loss=round(gross_loss, 2),
            equity_curve=equity_curve,
        )

