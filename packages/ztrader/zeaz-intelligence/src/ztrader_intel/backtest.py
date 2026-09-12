from __future__ import annotations

from statistics import mean, median

from .models import BacktestRequest, BacktestResponse


def _max_drawdown(returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    drawdown = 0.0
    for value in returns:
        equity *= 1 + value / 100
        peak = max(peak, equity)
        drawdown = min(drawdown, (equity - peak) / peak * 100)
    return abs(drawdown)


def evaluate_signals(payload: BacktestRequest) -> BacktestResponse:
    triggered = [
        point.forward_return_pct
        for point in payload.points
        if point.opportunity_score >= payload.min_opportunity
        and point.risk_score <= payload.max_risk
        and point.confidence_score >= payload.min_confidence
    ]

    if not triggered:
        return BacktestResponse(
            total_points=len(payload.points),
            triggered_signals=0,
            win_rate_pct=0,
            average_return_pct=0,
            median_return_pct=0,
            max_drawdown_pct=0,
            precision_positive=0,
        )

    wins = sum(value > 0 for value in triggered)
    precision = wins / len(triggered)

    return BacktestResponse(
        total_points=len(payload.points),
        triggered_signals=len(triggered),
        win_rate_pct=round(precision * 100, 2),
        average_return_pct=round(mean(triggered), 4),
        median_return_pct=round(median(triggered), 4),
        max_drawdown_pct=round(_max_drawdown(triggered), 4),
        precision_positive=round(precision, 4),
    )
