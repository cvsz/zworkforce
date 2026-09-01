"""Integrates TradingAgents' risk management agents into ztrader's RiskEngine.

TradingAgents provides 3 risk debaters (Aggressive, Conservative, Neutral)
that analyze trading decisions from different risk perspectives. This adapter
channels their output into ztrader's risk validation pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Optional

logger = logging.getLogger(__name__)


class RiskTier(StrEnum):
    """Risk assessment from TradingAgents' risk managers."""
    AGGRESSIVE = "aggressive"
    NEUTRAL = "neutral"
    CONSERVATIVE = "conservative"


@dataclass(frozen=True)
class RiskAssessment:
    """Output from TradingAgents' risk analysis pipeline."""
    tier: RiskTier
    score: float  # 0.0 (conservative) to 1.0 (aggressive)
    reasoning: str
    max_position_size_pct: float  # % of portfolio
    requires_approval: bool


class TradingAgentsRiskAdapter:
    """Wraps TradingAgents risk assessment into ztrader's risk system.

    Maps TradingAgents' 3-risk-manager debate output to ztrader's
    RiskEngine-compatible validation decisions.
    """

    @staticmethod
    def assess_risk(tier: RiskTier) -> RiskAssessment:
        """Generate a risk assessment based on the selected tier.

        Maps each risk tier to concrete position sizing and approval rules.
        """
        assessments = {
            RiskTier.CONSERVATIVE: RiskAssessment(
                tier=RiskTier.CONSERVATIVE,
                score=0.2,
                reasoning="Conservative: prioritizes capital preservation",
                max_position_size_pct=5.0,
                requires_approval=True,
            ),
            RiskTier.NEUTRAL: RiskAssessment(
                tier=RiskTier.NEUTRAL,
                score=0.5,
                reasoning="Neutral: balanced risk-reward approach",
                max_position_size_pct=15.0,
                requires_approval=False,
            ),
            RiskTier.AGGRESSIVE: RiskAssessment(
                tier=RiskTier.AGGRESSIVE,
                score=0.8,
                reasoning="Aggressive: higher risk for higher returns",
                max_position_size_pct=30.0,
                requires_approval=False,
            ),
        }
        return assessments[tier]

    @staticmethod
    def select_tier(
        signal_confidence: float,
        risk_score: float,
        portfolio_exposure: float,
    ) -> RiskTier:
        """Select the appropriate risk tier based on market conditions.

        Args:
            signal_confidence: TradingAgents signal confidence (0-1)
            risk_score: TradingAgents risk score (0-1, higher = riskier)
            portfolio_exposure: Current portfolio exposure (0-1)

        Returns:
            Appropriate RiskTier for the current conditions
        """
        if risk_score > 0.7 or portfolio_exposure > 0.8:
            return RiskTier.CONSERVATIVE
        if signal_confidence > 0.7 and risk_score < 0.3:
            return RiskTier.AGGRESSIVE
        return RiskTier.NEUTRAL