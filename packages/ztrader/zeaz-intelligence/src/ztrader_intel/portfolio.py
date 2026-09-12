from __future__ import annotations

from .models import (
    PortfolioAllocation,
    PortfolioRequest,
    PortfolioResponse,
    RiskProfile,
)


def build_portfolio(payload: PortfolioRequest) -> PortfolioResponse:
    reserve_by_risk = {
        RiskProfile.CONSERVATIVE: 35.0,
        RiskProfile.MODERATE: 20.0,
        RiskProfile.AGGRESSIVE: 10.0,
    }
    per_asset_cap = {
        RiskProfile.CONSERVATIVE: 12.0,
        RiskProfile.MODERATE: 20.0,
        RiskProfile.AGGRESSIVE: 30.0,
    }
    loss_budget_pct = {
        RiskProfile.CONSERVATIVE: 0.5,
        RiskProfile.MODERATE: 1.0,
        RiskProfile.AGGRESSIVE: 2.0,
    }

    reserve = reserve_by_risk[payload.risk]
    investable_pct = 100 - reserve

    raw: list[tuple[float, object]] = []
    for candidate in payload.candidates:
        intel = candidate.intelligence
        if intel.action.value == "AVOID" or intel.scores.risk >= 75:
            continue
        score = max(
            0.0,
            intel.scores.opportunity * 0.6
            + intel.scores.confidence * 0.3
            - intel.scores.risk * 0.45,
        )
        if score > 0:
            raw.append((score, candidate))

    total = sum(score for score, _ in raw) or 1.0
    cap = per_asset_cap[payload.risk]
    allocations: list[PortfolioAllocation] = []

    for score, candidate in sorted(raw, key=lambda item: item[0], reverse=True):
        weight = min(cap, investable_pct * (score / total))
        amount = payload.capital_usd * weight / 100
        loss_budget = payload.capital_usd * loss_budget_pct[payload.risk] / 100
        allocations.append(
            PortfolioAllocation(
                token=candidate.token,
                weight_pct=round(weight, 2),
                amount_usd=round(amount, 2),
                category=candidate.category,
                max_loss_budget_usd=round(loss_budget, 2),
            )
        )

    used = sum(item.weight_pct for item in allocations)
    if used > investable_pct and used > 0:
        scale = investable_pct / used
        for item in allocations:
            item.weight_pct = round(item.weight_pct * scale, 2)
            item.amount_usd = round(payload.capital_usd * item.weight_pct / 100, 2)

    return PortfolioResponse(
        allocations=allocations,
        reserve_pct=reserve,
        rebalance_trigger_pct=10.0 if payload.risk == RiskProfile.AGGRESSIVE else 7.5,
        notes=[
            "allocation excludes AVOID/high-risk-gate candidates",
            "reserve remains unallocated by design",
            "weights should be recalculated when risk/confidence changes materially",
        ],
    )
