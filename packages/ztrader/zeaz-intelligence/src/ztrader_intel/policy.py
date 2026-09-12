from __future__ import annotations

from .models import IntelligenceResponse


def execution_policy(intelligence: IntelligenceResponse) -> dict[str, object]:
    reasons: list[str] = []

    if intelligence.scores.risk >= 55:
        reasons.append("risk score must be below 55")
    if intelligence.scores.confidence < 60:
        reasons.append("confidence score must be at least 60")
    if intelligence.scores.opportunity < 65:
        reasons.append("opportunity score must be at least 65")
    if intelligence.rug_risk.value in {"HIGH", "EXTREME"}:
        reasons.append("rug risk must not be HIGH/EXTREME")
    if intelligence.whales.value == "DISTRIBUTING":
        reasons.append("whales are distributing")
    if intelligence.action.value != "WATCH":
        reasons.append("intelligence action is not WATCH")

    return {
        "allowed_for_paper_trade": not reasons,
        "allowed_for_live_execution": False,
        "live_execution_requires": [
            "successful paper/forward validation",
            "portfolio exposure check",
            "explicit human or configured policy approval",
            "exchange execution adapter kill switch enabled",
        ],
        "reasons": reasons or ["intelligence gates pass for paper-trade evaluation"],
    }
