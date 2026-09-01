"""TradingAgents-powered strategy for ztrader.

Integrates TradingAgents' multi-agent LLM pipeline as a ztrader Strategy,
generating trade intents from LLM-powered analysis of market, news, sentiment,
fundamentals, and risk assessment.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ztrader.engine.risk import StrategyIntent
from ztrader.engine.strategy import Candle, Strategy
from ztrader.core.logging_utils import sanitize_log_value
from ztrader.tradingagents_integration.adapter import TradingAgentsStrategy as TAAdapter

logger = logging.getLogger(__name__)

SIGNAL_TO_SIDE = {
    "buy": "buy",
    "sell": "sell",
    "hold": None,
}


class TradingAgentsLLMStrategy(Strategy):
    """Strategy that delegates analysis to TradingAgents' multi-agent LLM pipeline.

    Uses the full TradingAgents graph: Research Manager, multiple Analysts,
    Bull/Bear Researchers, Trader, Portfolio Manager, and Risk Managers.

    Args:
        symbol: Trading pair (e.g., "BTC/USDT" or "AAPL")
        notional: Order size in quote currency
        llm_provider: LLM provider (openai, anthropic, google, etc.)
        config_overrides: Additional TradingAgents config overrides
    """

    def __init__(
        self,
        symbol: str = "BTC/USDT",
        notional: float = 25.0,
        llm_provider: str = "openai",
        config_overrides: Optional[dict[str, Any]] = None,
    ) -> None:
        self.id = f"tradingagents-{llm_provider}-paper"
        self.symbol = symbol
        self.notional = notional
        self._ta = TAAdapter(
            llm_provider=llm_provider,
            config_overrides=config_overrides,
            debug=False,
        )
        logger.info(
            "TradingAgentsLLMStrategy initialized: symbol=%s provider=%s",
            sanitize_log_value(symbol),
            sanitize_log_value(llm_provider),
        )

    def generate_intent(self, candles: list[Candle]) -> Optional[StrategyIntent]:
        """Run TradingAgents analysis and generate a trade intent.

        Uses the last candle's timestamp as the analysis date. Falls back
        to 'hold' when the LLM analysis is unavailable.
        """
        if not candles:
            return None

        # Use the latest candle date for analysis context
        date = candles[-1].timestamp[:10] if len(candles[-1].timestamp) >= 10 else None

        # Map symbol to TradingAgents ticker format
        ticker = self.symbol.replace("/USD", "").replace("/USDT", "")

        try:
            signal = self._ta.analyze(ticker, date)
        except Exception as error:
            logger.error(
                "TradingAgents analysis failed",
                extra={"error_type": type(error).__name__},
            )
            return None

        side = SIGNAL_TO_SIDE.get(signal.signal)
        if side is None:
            logger.debug(
                "TradingAgents hold signal for %s (confidence=%.2f)",
                sanitize_log_value(self.symbol),
                signal.confidence,
            )
            return None

        logger.info(
            "TradingAgents signal: %s %s (confidence=%.2f, risk=%.2f)",
            sanitize_log_value(self.symbol),
            sanitize_log_value(side),
            signal.confidence,
            signal.risk_score,
        )

        return StrategyIntent(
            symbol=self.symbol,
            side=side,
            notional=self.notional,
            strategy_id=self.id,
            request_id="",
        )

    def reflect_on_trade(self, trade_return: float) -> None:
        """Feed trade outcome back to TradingAgents' reflection system.

        Call this after a trade closes to improve future analysis.
        """
        self._ta.reflect_and_learn(trade_return)
