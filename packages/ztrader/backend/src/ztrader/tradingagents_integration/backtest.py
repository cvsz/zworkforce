"""TradingAgents backtest integration for ztrader.

Extends ztrader's BacktestEngine to support TradingAgents-powered strategies
with reflection/learning from backtest results.
"""

from __future__ import annotations

import logging
from typing import Any

from ztrader.engine.backtest import BacktestEngine, BacktestResult
from ztrader.engine.strategy import Strategy
from ztrader.strategies.tradingagents_strategy import TradingAgentsLLMStrategy

logger = logging.getLogger(__name__)


class TradingAgentsBacktestEngine(BacktestEngine):
    """Extended backtest engine that feeds results back to TradingAgents.

    After each backtest run, completed trades are reflected back into
    TradingAgents' memory system for continuous improvement.
    """

    def __init__(
        self,
        allowed_symbols: tuple[str, ...],
        starting_usdt: float = 1000.0,
        starting_btc: float = 0.0,
        enable_reflection: bool = True,
    ) -> None:
        super().__init__(allowed_symbols, starting_usdt, starting_btc)
        self.enable_reflection = enable_reflection

    def run_with_reflection(
        self,
        strategy: TradingAgentsLLMStrategy,
        candles: list[Any],
        initial_balance: float = 1000.0,
    ) -> tuple[BacktestResult, list[float]]:
        """Run backtest and collect trade returns for reflection.

        Args:
            strategy: TradingAgents-powered strategy
            candles: OHLCV candle data
            initial_balance: Starting balance for return calculation

        Returns:
            Tuple of (BacktestResult, list of trade returns)
        """
        result = self.run(strategy, candles)
        trade_returns = []

        if self.enable_reflection and result.orders_created > 0:
            pnl = result.ending_usdt + result.ending_btc * candles[-1].close
            total_return = (pnl - initial_balance) / initial_balance
            avg_return = total_return / max(result.orders_created, 1)

            trade_returns.append(total_return)
            strategy.reflect_on_trade(total_return)

            logger.info(
                "TradingAgents backtest reflection: total_return=%.4f "
                "orders=%d avg_return=%.4f",
                total_return,
                result.orders_created,
                avg_return,
            )

        return result, trade_returns