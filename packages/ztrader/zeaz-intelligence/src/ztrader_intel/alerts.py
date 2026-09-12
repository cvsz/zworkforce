from __future__ import annotations

from .models import AlertEvaluation, AlertRule, IntelligenceResponse


def evaluate_alert(intelligence: IntelligenceResponse, rule: AlertRule) -> AlertEvaluation:
    reasons: list[str] = []

    if intelligence.scores.opportunity < rule.min_opportunity:
        reasons.append("opportunity below threshold")
    if intelligence.scores.risk > rule.max_risk:
        reasons.append("risk above threshold")
    if intelligence.scores.confidence < rule.min_confidence:
        reasons.append("confidence below threshold")
    if intelligence.narrative not in rule.narratives:
        reasons.append("narrative stage not allowed")
    if intelligence.whales not in rule.whale_states:
        reasons.append("whale state not allowed")

    return AlertEvaluation(matched=not reasons, reasons=reasons or ["all alert gates passed"])
