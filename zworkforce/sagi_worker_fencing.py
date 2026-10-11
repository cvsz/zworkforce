"""Strict fencing checks for computer-use execution handoff.

A fencing token is a monotonic, *durably issued* generation from the existing
canonical store. A local process may validate a token, but cannot mint it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ExecutionLease:
    tenant_id: str
    effect_id: str
    worker_id: str
    generation: int
    active: bool


class DurableFenceAuthority(Protocol):
    def load_execution_lease(self, tenant_id: str, effect_id: str) -> ExecutionLease | None: ...


def require_live_fence(
    *, tenant_id: str, effect_id: str, worker_id: str,
    generation: int, authority: DurableFenceAuthority,
) -> None:
    """Fail closed on stale, replaced, revoked or cross-tenant worker leases.

    This is a preflight only. A production completion write MUST include the
    same generation check in its database UPDATE predicate and use CAS.
    """
    if not all(isinstance(v, str) and v.strip() for v in
               (tenant_id, effect_id, worker_id)):
        raise PermissionError("worker identity is required")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
        raise PermissionError("invalid fencing generation")
    current = authority.load_execution_lease(tenant_id, effect_id)
    if (not isinstance(current, ExecutionLease) or not current.active or
        current.tenant_id != tenant_id or current.effect_id != effect_id or
        current.worker_id != worker_id or current.generation != generation):
        raise PermissionError("worker lease missing, revoked or stale")
