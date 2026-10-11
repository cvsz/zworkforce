"""Side-effect-free SAGI-to-ZLoop plan binding.

This module validates mission identity, lifecycle and budget compatibility.
It never dispatches work, approves mutations or persists state.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import math

from zworkforce.sagi_planning import ValidatedPlan
from zworkforce.zloop_bridge import LoopBudget, LoopPhase, ZLoopState


@dataclass(frozen=True)
class PlanBinding:
    loop_id: str
    tenant_id: str
    actor_id: str
    plan_digest: str
    requires_approval: bool


def bind_plan_to_loop(
    *,
    plan: ValidatedPlan,
    state: ZLoopState,
    loop_budget: LoopBudget,
) -> PlanBinding:
    """Bind a validated plan to a matching, pre-execution ZLoop snapshot.

    The returned value is metadata only, never an execution capability.
    The durable repository must separately enforce compare-and-set of the
    loop version, approval digest binding, and canonical cost accounting.
    """
    if not isinstance(plan, ValidatedPlan) or not isinstance(state, ZLoopState):
        raise ValueError("invalid plan or loop state")
    if not all(isinstance(v, str) and v.strip() for v in
               (state.loop_id, state.tenant_id, state.actor_id, state.goal)):
        raise ValueError("missing loop identity")
    if (plan.tenant_id, plan.actor_id, plan.goal) != (
        state.tenant_id, state.actor_id, state.goal
    ):
        raise ValueError("plan and loop identities do not match")
    if state.phase != LoopPhase.PLAN:
        raise ValueError("plan binding is only allowed during PLAN phase")
    for count in (state.iteration, state.repairs, state.tokens_used):
        if type(count) is not int or count < 0:
            raise ValueError("invalid loop counters")
    if not isinstance(loop_budget, LoopBudget):
        raise ValueError("invalid loop budget")
    for count in (loop_budget.max_iterations, loop_budget.max_repairs, loop_budget.max_tokens):
        if type(count) is not int or count <= 0:
            raise ValueError("invalid loop budget counters")
    if isinstance(state.cost_used, bool) or not isinstance(state.cost_used, (int, float)) or not math.isfinite(state.cost_used) or state.cost_used < 0:
        raise ValueError("invalid loop cost")
    if isinstance(loop_budget.max_cost, bool) or not isinstance(loop_budget.max_cost, (int, float)) or not math.isfinite(loop_budget.max_cost) or loop_budget.max_cost <= 0:
        raise ValueError("invalid loop budget")
    if (state.iteration >= loop_budget.max_iterations
        or state.repairs > loop_budget.max_repairs
        or state.tokens_used > loop_budget.max_tokens
        or state.cost_used >= loop_budget.max_cost):
        raise ValueError("loop budget exhausted")
    if not plan.steps or not isinstance(plan.digest, str) or len(plan.digest) != 64:
        raise ValueError("invalid validated plan")
    projected = sum((Decimal(str(step.estimated_cost)) for step in plan.steps), Decimal(0))
    if projected > Decimal(str(loop_budget.max_cost)) - Decimal(str(state.cost_used)):
        raise ValueError("plan exceeds remaining loop budget")
    return PlanBinding(
        loop_id=state.loop_id,
        tenant_id=state.tenant_id,
        actor_id=state.actor_id,
        plan_digest=plan.digest,
        requires_approval=plan.requires_approval,
    )
