"""Tests for TradingAgents integration with ztrader."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from ztrader.strategies.tradingagents_strategy import TradingAgentsLLMStrategy
from ztrader.tradingagents_integration.adapter import TradingAgentsSignal, TradingAgentsStrategy
from ztrader.tradingagents_integration.data_providers import (
    get_available_data_sources,
    get_enabled_data_sources,
)
from ztrader.tradingagents_integration.model_catalog import (
    get_all_providers,
    get_configured_providers,
)
from ztrader.tradingagents_integration.risk_adapter import (
    RiskTier,
    TradingAgentsRiskAdapter,
)


class TestTradingAgentsStrategy:
    """Test the TradingAgentsStrategy adapter."""

    def test_signal_creation(self):
        """Verify TradingAgentsSignal dataclass works correctly."""
        signal = TradingAgentsSignal(
            symbol="NVDA",
            signal="buy",
            confidence=0.85,
            reasoning="Strong earnings growth",
            analysis_date="2024-05-10",
            risk_score=0.3,
            agents_used=["market_analyst", "news_analyst", "trader"],
            supporting_data={"market_analysis": "Bullish trend"},
        )

        assert signal.symbol == "NVDA"
        assert signal.signal == "buy"
        assert signal.confidence == 0.85
        assert signal.risk_score == 0.3
        assert len(signal.agents_used) == 3

    def test_signal_fallback_hold(self):
        """Verify TradingAgentsSignal defaults to safe hold values."""
        signal = TradingAgentsSignal(
            symbol="INVALID",
            signal="hold",
            confidence=0.0,
            reasoning="Analysis failed",
            analysis_date="2024-05-10",
            risk_score=1.0,
        )

        assert signal.signal == "hold"
        assert signal.confidence == 0.0
        assert signal.risk_score == 1.0


class TestTradingAgentsLLMStrategy:
    """Test the ztrader Strategy subclass."""

    def test_hold_signal_returns_none(self):
        """Verify hold signals return None (no intent)."""
        with patch.object(TradingAgentsStrategy, "analyze") as mock_analyze, \
             patch.object(TradingAgentsStrategy, "__init__", return_value=None):
            mock_analyze.return_value = TradingAgentsSignal(
                symbol="BTC-USD",
                signal="hold",
                confidence=0.5,
                reasoning="Neutral",
                analysis_date="2024-05-10",
                risk_score=0.5,
            )

            strategy = TradingAgentsLLMStrategy.__new__(TradingAgentsLLMStrategy)
            strategy._ta = TradingAgentsStrategy.__new__(TradingAgentsStrategy)
            strategy.symbol = "BTC/USDT"
            strategy.notional = 25.0
            strategy.id = "tradingagents-openai-paper"

            intent = strategy.generate_intent([])
            assert intent is None


class TestDataProviders:
    """Test the data provider integration."""

    def test_available_sources(self):
        """Verify all data sources are listed."""
        sources = get_available_data_sources()
        assert "alpha_vantage" in sources
        assert "fred" in sources
        assert "polymarket" in sources
        assert len(sources) >= 5

    def test_enabled_sources(self):
        """Verify enabled sources are correctly detected."""
        with patch.dict("os.environ", {"FRED_API_KEY": "test-key"}, clear=False):
            enabled = get_enabled_data_sources()
            assert "fred" in enabled


class TestModelCatalog:
    """Test the model catalog integration."""

    def test_all_providers_listed(self):
        """Verify all providers are in the catalog."""
        providers = get_all_providers()
        keys = [p.key for p in providers]
        assert "openai" in keys
        assert "anthropic" in keys
        assert "google" in keys
        assert len(providers) >= 10

    def test_configured_providers(self):
        """Verify configured provider detection."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
            configured = get_configured_providers()
            keys = [p.key for p in configured]
            assert "openai" in keys


class TestRiskAdapter:
    """Test the TradingAgents risk adapter."""

    def test_select_conservative_high_risk(self):
        """Verify high risk selects conservative tier."""
        tier = TradingAgentsRiskAdapter.select_tier(
            signal_confidence=0.8,
            risk_score=0.8,
            portfolio_exposure=0.5,
        )
        assert tier == RiskTier.CONSERVATIVE

    def test_select_aggressive_high_confidence(self):
        """Verify high confidence + low risk selects aggressive."""
        tier = TradingAgentsRiskAdapter.select_tier(
            signal_confidence=0.8,
            risk_score=0.2,
            portfolio_exposure=0.3,
        )
        assert tier == RiskTier.AGGRESSIVE

    def test_select_neutral_default(self):
        """Verify moderate conditions select neutral."""
        tier = TradingAgentsRiskAdapter.select_tier(
            signal_confidence=0.5,
            risk_score=0.5,
            portfolio_exposure=0.5,
        )
        assert tier == RiskTier.NEUTRAL