"""Bounded, provider-neutral SAGI planning contracts.

Planning is never authority to execute tools or mutate resources. Existing
zWorkforce approval, queue, budget and audit services remain authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import hashlib
import json
import math


@dataclass(frozen=True)
class MissionLimits:
    max_steps: int = 16
    max_depth: int = 3
    max_fanout: int = 4
    max_cost: float = 5.0

    def __post_init__(self) -> None:
        if not 1 <= self.max_steps <= 256:
            raise ValueError("max_steps out of bounds")
        if not 1 <= self.max_depth <= 16:
            raise ValueError("max_depth out of bounds")
        if not 1 <= self.max_fanout <= 32:
            raise ValueError("max_fanout out of bounds")
        if not math.isfinite(self.max_cost) or self.max_cost <= 0:
            raise ValueError("max_cost must be finite and positive")


@dataclass(frozen=True)
class ProposedStep:
    step_id: str
    description: str
    depends_on: tuple[str, ...] = ()
    depth: int = 0
    estimated_cost: float = 0.0
    mutation: bool = False


@dataclass(frozen=True)
class ValidatedPlan:
    tenant_id: str
    actor_id: str
    goal: str
    steps: tuple[ProposedStep, ...]
    digest: str

    @property
    def requires_approval(self) -> bool:
        return any(step.mutation for step in self.steps)


def validate_plan(
    *,
    tenant_id: str,
    actor_id: str,
    goal: str,
    proposed_steps: Iterable[ProposedStep],
    limits: MissionLimits,
) -> ValidatedPlan:
    """Validate untrusted planner output; return data, never execute actions."""
    if not all(isinstance(v, str) and v.strip() for v in (tenant_id, actor_id, goal)):
        raise ValueError("tenant, actor and goal are required")
    steps = tuple(proposed_steps)
    if not 1 <= len(steps) <= limits.max_steps:
        raise ValueError("step count out of bounds")
    ids: set[str] = set()
    fanout: dict[str, int] = {}
    total_cost = 0.0
    for step in steps:
        if not isinstance(step, ProposedStep):
            raise ValueError("invalid step")
        if not isinstance(step.step_id, str) or not step.step_id.strip() or len(step.step_id) > 128:
            raise ValueError("invalid step id")
        if step.step_id in ids:
            raise ValueError("duplicate step id")
        if not isinstance(step.description, str) or not step.description.strip():
            raise ValueError("step description required")
        if not isinstance(step.depth, int) or isinstance(step.depth, bool) or not 0 <= step.depth < limits.max_depth:
            raise ValueError("step depth out of bounds")
        if not isinstance(step.mutation, bool):
            raise ValueError("mutation must be boolean")
        if not isinstance(step.estimated_cost, (int, float)) or isinstance(step.estimated_cost, bool) or not math.isfinite(step.estimated_cost) or step.estimated_cost < 0:
            raise ValueError("invalid cost")
        if not isinstance(step.depends_on, tuple) or len(set(step.depends_on)) != len(step.depends_on):
            raise ValueError("invalid dependencies")
        for dep in step.depends_on:
            if dep not in ids:
                raise ValueError("dependencies must precede their dependent step")
            fanout[dep] = fanout.get(dep, 0) + 1
            if fanout[dep] > limits.max_fanout:
                raise ValueError("max fanout exceeded")
        ids.add(step.step_id)
        total_cost += step.estimated_cost
        if total_cost > limits.max_cost:
            raise ValueError("estimated budget exceeded")
    canonical = {
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "goal": goal,
        "steps": [
            {"id": s.step_id, "description": s.description, "depends_on": list(s.depends_on),
             "depth": s.depth, "cost": s.estimated_cost, "mutation": s.mutation}
            for s in steps
        ],
    }
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return ValidatedPlan(tenant_id, actor_id, goal, steps, digest)
