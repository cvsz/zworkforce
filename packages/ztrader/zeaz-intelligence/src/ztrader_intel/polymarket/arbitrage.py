from __future__ import annotations

from .models import ArbitrageOpportunity, ArbitrageRequest


def _bps(value: float) -> float:
    return round(value * 10_000, 10)


def detect_complement_arbitrage(request: ArbitrageRequest) -> ArbitrageOpportunity:
    """Detect the executable YES+NO complement mispricing.

    Buying both outcomes costs ask_yes + ask_no. A complete binary market pays
    1.00 at resolution, so edge exists only when the executable cost is below
    1.00 after conservative execution costs.
    """
    yes_ask = request.yes.best_ask
    no_ask = request.no.best_ask
    reasons: list[str] = []

    if yes_ask is None or no_ask is None:
        return ArbitrageOpportunity(
            market_id=request.market_id,
            executable=False,
            strategy="COMPLEMENT_YES_NO",
            gross_edge_bps=0,
            estimated_cost_bps=0,
            net_edge_bps=0,
            max_capital_usd=0,
            estimated_profit_usd=0,
            limiting_liquidity_usd=0,
            reasons=["both executable asks are required"],
        )

    if yes_ask >= 1 or no_ask >= 1:
        reasons.append("one or more asks are outside the binary complement range")

    pair_cost = yes_ask + no_ask
    gross_edge = 1.0 - pair_cost
    gross_bps = _bps(gross_edge)
    estimated_cost_bps = request.fee_bps + request.slippage_bps + request.latency_bps
    net_bps = gross_bps - estimated_cost_bps

    yes_liquidity = request.yes.available_ask * yes_ask
    no_liquidity = request.no.available_ask * no_ask
    limiting = max(0.0, min(yes_liquidity, no_liquidity))
    requested_capital = request.capital_usd * max(0.0, pair_cost)
    capital = min(requested_capital, limiting)
    profit = capital * max(0.0, net_bps) / 10_000

    if limiting <= 0:
        reasons.append("insufficient executable ask liquidity")
    if net_bps < request.min_edge_bps:
        reasons.append("net edge is below configured minimum")

    executable = (
        gross_edge > 0
        and net_bps >= request.min_edge_bps
        and limiting > 0
        and capital > 0
    )

    if executable:
        reasons.append("both legs can be sized from the limiting ask liquidity")

    return ArbitrageOpportunity(
        market_id=request.market_id,
        executable=executable,
        strategy="COMPLEMENT_YES_NO",
        gross_edge_bps=gross_bps,
        estimated_cost_bps=estimated_cost_bps,
        net_edge_bps=net_bps,
        max_capital_usd=capital,
        estimated_profit_usd=profit,
        limiting_liquidity_usd=limiting,
        reasons=reasons,
    )
