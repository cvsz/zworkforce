from ztrader_intel.polymarket.arbitrage import detect_complement_arbitrage
from ztrader_intel.polymarket.models import ArbitrageRequest, MarketQuote


def quote(outcome: str, ask: float, size: float) -> MarketQuote:
    return MarketQuote(
        market_id="m1",
        token_id=outcome,
        outcome=outcome,
        best_ask=ask,
        available_ask=size,
    )


def test_complement_arbitrage_accounts_for_costs_and_liquidity():
    result = detect_complement_arbitrage(
        ArbitrageRequest(
            market_id="m1",
            yes=quote("YES", 0.45, 1000),
            no=quote("NO", 0.50, 1000),
            capital_usd=100,
            fee_bps=20,
            slippage_bps=10,
            latency_bps=5,
            min_edge_bps=10,
        )
    )
    assert result.executable is True
    assert result.gross_edge_bps == 500
    assert result.estimated_cost_bps == 35
    assert result.net_edge_bps == 465
    assert result.max_capital_usd == 95.0
    assert result.estimated_profit_usd == 4.4175


def test_complement_arbitrage_rejects_negative_net_edge():
    result = detect_complement_arbitrage(
        ArbitrageRequest(
            market_id="m1",
            yes=quote("YES", 0.50, 1000),
            no=quote("NO", 0.51, 1000),
            capital_usd=100,
            fee_bps=20,
            slippage_bps=20,
            latency_bps=20,
            min_edge_bps=10,
        )
    )
    assert result.executable is False
    assert result.net_edge_bps < 0
