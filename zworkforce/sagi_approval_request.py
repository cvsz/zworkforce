"""SAGI approval request metadata; never an authorization or execution grant."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from zworkforce.sagi_zloop_binding import PlanBinding


_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class ApprovalRequest:
    loop_id: str
    tenant_id: str
    actor_id: str
    plan_digest: str
    action: str
    target: str
    idempotency_key: str


def create_approval_request(
    *,
    binding: PlanBinding,
    action: str,
    target: str,
    step_id: str,
) -> ApprovalRequest:
    """Build immutable, deterministic request data for the canonical approval authority.

    A returned request is NOT an authorization; the canonical approval service
    must validate policy, expiry, reviewer separation, and record version.
    """
    if not isinstance(binding, PlanBinding) or binding.requires_approval is not True:
        raise ValueError("mutation approval binding required")
    values = (binding.loop_id, binding.tenant_id, binding.actor_id, action, target, step_id)
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise ValueError("approval request fields are required")
    if not isinstance(binding.plan_digest, str) or not _DIGEST.fullmatch(binding.plan_digest):
        raise ValueError("invalid plan digest")
    if action not in ("execute", "repair"):
        raise ValueError("unsupported mutation action")
    if len(step_id) > 128 or len(target) > 2048:
        raise ValueError("approval scope too large")
    payload = {
        "loop_id": binding.loop_id,
        "tenant_id": binding.tenant_id,
        "actor_id": binding.actor_id,
        "plan_digest": binding.plan_digest,
        "action": action,
        "target": target,
        "step_id": step_id,
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return ApprovalRequest(
        loop_id=binding.loop_id,
        tenant_id=binding.tenant_id,
        actor_id=binding.actor_id,
        plan_digest=binding.plan_digest,
        action=action,
        target=target,
        idempotency_key=fingerprint,
    )
