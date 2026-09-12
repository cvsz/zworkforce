from ztrader_intel.backtest import evaluate_signals
from ztrader_intel.models import BacktestPoint, BacktestRequest


def test_backtest_selects_only_gated_signals():
    result = evaluate_signals(
        BacktestRequest(
            points=[
                BacktestPoint(
                    timestamp="1",
                    opportunity_score=80,
                    risk_score=30,
                    confidence_score=70,
                    forward_return_pct=12,
                ),
                BacktestPoint(
                    timestamp="2",
                    opportunity_score=40,
                    risk_score=30,
                    confidence_score=70,
                    forward_return_pct=-5,
                ),
                BacktestPoint(
                    timestamp="3",
                    opportunity_score=75,
                    risk_score=40,
                    confidence_score=65,
                    forward_return_pct=-2,
                ),
            ]
        )
    )
    assert result.triggered_signals == 2
    assert result.win_rate_pct == 50
