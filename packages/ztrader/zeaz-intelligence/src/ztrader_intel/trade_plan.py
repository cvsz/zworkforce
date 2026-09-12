from __future__ import annotations

from .models import TradePlanRequest, TradePlanResponse, TradeVerdict


def build_trade_plan(payload: TradePlanRequest) -> TradePlanResponse:
    price = payload.current_price
    atr_fraction = payload.atr_pct / 100

    support = payload.support or price * (1 - atr_fraction)
    resistance = payload.resistance or price * (1 + atr_fraction * 1.8)

    entry_low = max(0.00000001, support * 1.005)
    entry_high = min(price, support * 1.03)
    stop = max(0.00000001, support * (1 - atr_fraction * 0.75))
    dca = [
        round(max(0.00000001, entry_low * 0.97), 12),
        round(max(0.00000001, entry_low * 0.94), 12),
    ]
    targets = [
        round(resistance, 12),
        round(resistance * 1.08, 12),
        round(resistance * 1.18, 12),
    ]

    risk_per_unit = max(entry_high - stop, price * 0.005)
    loss_budget = payload.account_equity_usd * (payload.risk_per_trade_pct / 100)
    units = loss_budget / risk_per_unit
    max_position = min(payload.account_equity_usd * 0.25, units * entry_high)

    reward = max(targets[0] - entry_high, 0)
    rr = reward / max(risk_per_unit, 1e-12)

    verdict = TradeVerdict.WAIT
    reasons = ["trade plan is a deterministic risk simulation, not an automatic order"]

    intel = payload.intelligence
    if intel:
        if intel.scores.risk >= 75 or intel.action.value == "AVOID":
            verdict = TradeVerdict.EXIT
            reasons.append("risk gate is above allowed threshold")
        elif price >= targets[0] and intel.narrative.value in {"CROWDED", "FADING"}:
            verdict = TradeVerdict.TAKE_PROFIT
            reasons.append("price reached first target while narrative is crowded/fading")
        elif (
            intel.scores.opportunity >= 65
            and intel.scores.risk < 55
            and intel.scores.confidence >= 50
            and entry_low <= price <= entry_high * 1.02
        ):
            verdict = TradeVerdict.ENTER
            reasons.append("price is inside the risk-defined entry zone and intelligence gates pass")
        else:
            reasons.append("intelligence gates do not justify simulated entry")
    else:
        reasons.append("no intelligence response supplied; defaulting to WAIT")

    return TradePlanResponse(
        verdict=verdict,
        entry_zone=(round(entry_low, 12), round(entry_high, 12)),
        dca_levels=dca,
        take_profit_levels=targets,
        stop_loss=round(stop, 12),
        max_position_usd=round(max(0.0, max_position), 2),
        risk_reward_estimate=round(rr, 2),
        reasons=reasons,
    )
