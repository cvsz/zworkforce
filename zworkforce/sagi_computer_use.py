"""Deny-by-default computer-use intent contracts.

This module validates untrusted UI action proposals. It does not capture
screens, click, type, connect to a browser, grant permission or execute tools.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import re

from zworkforce.sagi_zloop_binding import PlanBinding
from zworkforce.sagi_planning import ValidatedPlan


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class ComputerAction(str, Enum):
    OBSERVE = "observe"
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    KEY = "key"


@dataclass(frozen=True)
class ComputerUseIntent:
    tenant_id: str
    actor_id: str
    loop_id: str
    plan_digest: str
    session_id: str
    step_id: str
    action: ComputerAction
    target: str
    screen_evidence_digest: str
    parameters: tuple[tuple[str, object], ...]
    request_digest: str
    requires_approval: bool


def prepare_computer_use_intent(
    *,
    binding: PlanBinding,
    session_id: str,
    step_id: str,
    action: ComputerAction,
    target: str,
    screen_evidence_digest: str,
    plan: ValidatedPlan | None = None,
    text: str | None = None,
    scroll_delta: int | None = None,
    key: str | None = None,
    modifiers: tuple[str, ...] = (),
) -> ComputerUseIntent:
    """Produce non-executable proposal metadata for downstream policy review.

    All actions require explicit session authority at execution time. Mutating
    actions additionally require canonical approval bound to the exact plan
    digest, action, target, and fresh screen evidence.
    """
    if not isinstance(binding, PlanBinding):
        raise ValueError("validated plan binding required")
    if not isinstance(action, ComputerAction):
        raise ValueError("unsupported computer action")
    values = (binding.tenant_id, binding.actor_id, binding.loop_id, session_id, step_id, target)
    if not all(isinstance(v, str) and v.strip() for v in values):
        raise ValueError("scope and target are mandatory")
    if len(session_id) > 128 or len(step_id) > 128 or len(target) > 1024:
        raise ValueError("computer action scope too large")
    if not isinstance(binding.plan_digest, str) or not _SHA256.fullmatch(binding.plan_digest):
        raise ValueError("invalid plan digest")
    if not isinstance(screen_evidence_digest, str) or not _SHA256.fullmatch(screen_evidence_digest):
        raise ValueError("screen evidence digest required")
    is_mutation = action is not ComputerAction.OBSERVE
    if is_mutation:
        if binding.requires_approval is not True or not isinstance(plan, ValidatedPlan):
            raise ValueError("mutation requires a validated plan")
        if (plan.digest, plan.tenant_id, plan.actor_id) != (
            binding.plan_digest, binding.tenant_id, binding.actor_id
        ):
            raise ValueError("plan binding mismatch")
        if not any(step.step_id == step_id and step.mutation is True for step in plan.steps):
            raise ValueError("step is not an authorized mutating plan step")
    elif plan is not None and (not isinstance(plan, ValidatedPlan) or
                              plan.digest != binding.plan_digest):
        raise ValueError("observation plan mismatch")
    if not isinstance(modifiers, tuple) or len(modifiers) > 4 or any(
        not isinstance(m, str) or m not in ("Shift", "Ctrl", "Alt", "Meta") for m in modifiers
    ) or len(set(modifiers)) != len(modifiers):
        raise ValueError("invalid modifiers")
    if action is ComputerAction.TYPE:
        if not isinstance(text, str) or not 1 <= len(text) <= 4096:
            raise ValueError("invalid type text")
    elif text is not None:
        raise ValueError("text is only valid for TYPE")
    if action is ComputerAction.SCROLL:
        if type(scroll_delta) is not int or not -10000 <= scroll_delta <= 10000 or scroll_delta == 0:
            raise ValueError("invalid scroll distance")
    elif scroll_delta is not None:
        raise ValueError("scroll distance is only valid for SCROLL")
    if action is ComputerAction.KEY:
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9]{1,32}", key):
            raise ValueError("invalid key")
    elif key is not None:
        raise ValueError("key is only valid for KEY")
    if modifiers and action not in (ComputerAction.KEY, ComputerAction.CLICK):
        raise ValueError("modifiers are invalid for this action")
    params = tuple(sorted((name, value) for name, value in (
        ("text", text), ("scroll_delta", scroll_delta), ("key", key)
    ) if value is not None)) + (("modifiers", modifiers),)
    payload = {
        "tenant_id": binding.tenant_id, "actor_id": binding.actor_id,
        "loop_id": binding.loop_id, "plan_digest": binding.plan_digest,
        "session_id": session_id, "step_id": step_id,
        "action": action.value, "target": target,
        "screen_evidence_digest": screen_evidence_digest,
        "parameters": dict(params),
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return ComputerUseIntent(
        tenant_id=binding.tenant_id, actor_id=binding.actor_id,
        loop_id=binding.loop_id, plan_digest=binding.plan_digest,
        session_id=session_id, step_id=step_id, action=action,
        target=target, screen_evidence_digest=screen_evidence_digest,
        parameters=params, request_digest=digest, requires_approval=is_mutation,
    )
