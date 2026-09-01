"""Adapter between TradingAgents framework and ztrader platform.

Integrates TradingAgents' multi-agent LLM trading pipeline into ztrader's
strategy and analysis system. Provides:
- Multi-agent analysis (Research Manager, Analysts, Trader, Portfolio Manager)
- LLM-powered signal generation from multiple providers
- LangGraph-based trading workflow with reflection/memory
- Risk management via TradingAgents' risk agents
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from ztrader.core.logging_utils import sanitize_log_value

try:
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    TRADINGAGENTS_AVAILABLE = True
except ImportError:
    DEFAULT_CONFIG = {}
    TradingAgentsGraph = None
    TRADINGAGENTS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class TradingAgentsSignal:
    """Structured output from TradingAgents analysis."""
    symbol: str
    signal: str  # buy, sell, hold
    confidence: float  # 0.0 to 1.0
    reasoning: str
    analysis_date: str
    risk_score: float  # 0.0 (low risk) to 1.0 (high risk)
    agents_used: list[str] = field(default_factory=list)
    supporting_data: dict[str, Any] = field(default_factory=dict)


class TradingAgentsStrategy:
    """Wraps TradingAgents as a ztrader-compatible strategy.

    Usage:
        strategy = TradingAgentsStrategy(llm_provider="openai")
        signal = strategy.analyze("NVDA", "2024-05-10")
    """

    def __init__(
        self,
        llm_provider: str = "openai",
        config_overrides: Optional[dict[str, Any]] = None,
        debug: bool = False,
    ):
        config = DEFAULT_CONFIG.copy()
        config["llm_provider"] = llm_provider
        if config_overrides:
            config.update(config_overrides)

        if TradingAgentsGraph is not None:
            self._graph = TradingAgentsGraph(debug=debug, config=config)
        else:
            self._graph = None
            logger.warning("TradingAgents package is not installed; running in fallback mode.")
        self._debug = debug
        logger.info(
            "TradingAgentsStrategy initialized with provider=%s",
            sanitize_log_value(llm_provider),
        )

    def analyze(
        self,
        symbol: str,
        date: str | None = None,
    ) -> TradingAgentsSignal:
        """Run TradingAgents' multi-agent pipeline for a symbol.

        Args:
            symbol: Ticker symbol (e.g., "NVDA", "BTC-USD")
            date: Analysis date in YYYY-MM-DD format (defaults to today)

        Returns:
            TradingAgentsSignal with the aggregated decision
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        logger.info(
            "Running TradingAgents analysis for %s on %s",
            sanitize_log_value(symbol),
            sanitize_log_value(date),
        )

        try:
            if self._graph is None:
                return TradingAgentsSignal(
                    symbol=symbol,
                    signal="hold",
                    confidence=0.5,
                    reasoning="TradingAgents engine is running in fallback mode.",
                    analysis_date=date,
                    risk_score=0.0,
                )
            raw_state, decision = self._graph.propagate(symbol, date)

            signal = self._extract_signal(symbol, date, raw_state, decision)

            if self._debug:
                logger.debug(
                    "TradingAgents result: symbol=%s signal=%s confidence=%.2f",
                    sanitize_log_value(symbol),
                    sanitize_log_value(signal.signal),
                    signal.confidence,
                )

            return signal
        except Exception as error:
            logger.error(
                "TradingAgents analysis failed for symbol=%s",
                sanitize_log_value(symbol),
                extra={"error_type": type(error).__name__},
            )
            return TradingAgentsSignal(
                symbol=symbol,
                signal="hold",
                confidence=0.0,
                reasoning="Analysis failed",
                analysis_date=date,
                risk_score=1.0,
            )

    def reflect_and_learn(self, position_returns: float) -> None:
        """Feed trade outcomes back into TradingAgents' reflection system.

        Args:
            position_returns: Actual return from the position (e.g., 0.05 for 5%)
        """
        try:
            if self._graph is not None:
                self._graph.reflect_and_remember(position_returns)
            logger.info(
                "TradingAgents reflection complete (returns=%.4f)",
                position_returns,
            )
        except Exception as error:
            logger.warning(
                "TradingAgents reflection failed",
                extra={"error_type": type(error).__name__},
            )

    def _extract_signal(
        self,
        symbol: str,
        date: str,
        raw_state: dict[str, Any],
        decision: dict[str, Any],
    ) -> TradingAgentsSignal:
        """Parse TradingAgents' raw output into a structured signal."""
        action = decision.get("action", "hold")
        confidence = float(decision.get("confidence", 0.5))
        reasoning = decision.get("reasoning", "No reasoning provided")
        risk_score = float(decision.get("risk_score", 0.5))

        agents_used = list(raw_state.get("agents_executed", []))
        supporting = {
            "market_analyst": raw_state.get("market_analysis"),
            "news_analyst": raw_state.get("news_analysis"),
            "sentiment_analyst": raw_state.get("sentiment_analysis"),
            "fundamentals_analyst": raw_state.get("fundamentals_analysis"),
            "bull_case": raw_state.get("bull_research"),
            "bear_case": raw_state.get("bear_research"),
        }

        return TradingAgentsSignal(
            symbol=symbol,
            signal=action,
            confidence=confidence,
            reasoning=reasoning,
            analysis_date=date,
            risk_score=risk_score,
            agents_used=agents_used,
            supporting_data={k: v for k, v in supporting.items() if v},
        )
