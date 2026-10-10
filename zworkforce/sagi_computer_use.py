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
    if is_mutation and binding.requires_approval is not True:
        raise ValueError("mutation must be covered by a mutating plan")
    payload = {
        "tenant_id": binding.tenant_id, "actor_id": binding.actor_id,
        "loop_id": binding.loop_id, "plan_digest": binding.plan_digest,
        "session_id": session_id, "step_id": step_id,
        "action": action.value, "target": target,
        "screen_evidence_digest": screen_evidence_digest,
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return ComputerUseIntent(
        tenant_id=binding.tenant_id, actor_id=binding.actor_id,
        loop_id=binding.loop_id, plan_digest=binding.plan_digest,
        session_id=session_id, step_id=step_id, action=action,
        target=target, screen_evidence_digest=screen_evidence_digest,
        request_digest=digest, requires_approval=is_mutation,
    )
