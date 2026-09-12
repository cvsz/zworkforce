"""Deterministic economics helpers for ZeaZ managed-service brokering.

The module intentionally contains no marketplace automation.  It models the
commercial guardrails used before a human approves a quote, supplier, or job.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING


MoneyLike = Decimal | int | str


def _money(value: MoneyLike, *, name: str) -> Decimal:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"{name} must be a finite non-negative amount")
    return amount


@dataclass(frozen=True, slots=True)
class JobEconomics:
    revenue: Decimal
    supplier_cost: Decimal
    acquisition_cost: Decimal
    operations_cost: Decimal
    risk_reserve: Decimal
    contribution: Decimal
    contribution_margin: Decimal

    @property
    def profitable(self) -> bool:
        return self.contribution > 0


def evaluate_job(
    *,
    revenue: MoneyLike,
    supplier_cost: MoneyLike,
    acquisition_cost: MoneyLike = 0,
    operations_cost: MoneyLike = 0,
    risk_reserve: MoneyLike = 0,
) -> JobEconomics:
    """Return contribution economics for one managed-service job.

    Contribution is revenue less supplier, customer-acquisition, operations,
    and risk-reserve costs.  The margin is expressed as a ratio (0.20 = 20%).
    """

    revenue_d = _money(revenue, name="revenue")
    supplier_d = _money(supplier_cost, name="supplier_cost")
    acquisition_d = _money(acquisition_cost, name="acquisition_cost")
    operations_d = _money(operations_cost, name="operations_cost")
    reserve_d = _money(risk_reserve, name="risk_reserve")

    contribution = revenue_d - supplier_d - acquisition_d - operations_d - reserve_d
    margin = contribution / revenue_d if revenue_d else Decimal("0")

    return JobEconomics(
        revenue=revenue_d,
        supplier_cost=supplier_d,
        acquisition_cost=acquisition_d,
        operations_cost=operations_d,
        risk_reserve=reserve_d,
        contribution=contribution,
        contribution_margin=margin,
    )


def max_supplier_cost(
    *,
    revenue: MoneyLike,
    target_contribution: MoneyLike,
    acquisition_cost: MoneyLike = 0,
    operations_cost: MoneyLike = 0,
    risk_reserve: MoneyLike = 0,
) -> Decimal:
    """Return the maximum supplier cost compatible with the contribution target."""

    revenue_d = _money(revenue, name="revenue")
    target_d = _money(target_contribution, name="target_contribution")
    acquisition_d = _money(acquisition_cost, name="acquisition_cost")
    operations_d = _money(operations_cost, name="operations_cost")
    reserve_d = _money(risk_reserve, name="risk_reserve")

    ceiling = revenue_d - target_d - acquisition_d - operations_d - reserve_d
    return max(Decimal("0"), ceiling)


def max_acquisition_cost(
    *,
    revenue: MoneyLike,
    supplier_cost: MoneyLike,
    target_contribution: MoneyLike,
    operations_cost: MoneyLike = 0,
    risk_reserve: MoneyLike = 0,
) -> Decimal:
    """Return the maximum CAC compatible with the contribution target."""

    revenue_d = _money(revenue, name="revenue")
    supplier_d = _money(supplier_cost, name="supplier_cost")
    target_d = _money(target_contribution, name="target_contribution")
    operations_d = _money(operations_cost, name="operations_cost")
    reserve_d = _money(risk_reserve, name="risk_reserve")

    ceiling = revenue_d - supplier_d - target_d - operations_d - reserve_d
    return max(Decimal("0"), ceiling)


def jobs_required(*, monthly_target: MoneyLike, contribution_per_job: MoneyLike) -> int:
    """Return the minimum whole jobs required to meet a monthly target."""

    target_d = _money(monthly_target, name="monthly_target")
    contribution_d = _money(contribution_per_job, name="contribution_per_job")
    if target_d == 0:
        return 0
    if contribution_d <= 0:
        raise ValueError("contribution_per_job must be greater than zero")
    return int((target_d / contribution_d).to_integral_value(rounding=ROUND_CEILING))
