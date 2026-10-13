"""Fail-closed, dependency-injected computer session authorization guard.

This module never issues grants, executes UI actions, or persists approvals.
Production authorities must supply fresh canonical session and approval data.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol
import hmac

from zworkforce.sagi_computer_use import ComputerAction, ComputerUseIntent


@dataclass(frozen=True)
class SessionSnapshot:
    session_id: str
    tenant_id: str
    actor_id: str
    expires_at: datetime
    revoked: bool
    stopped: bool
    permitted: bool


@dataclass(frozen=True)
class ApprovalSnapshot:
    tenant_id: str
    actor_id: str
    session_id: str
    request_digest: str
    plan_digest: str
    expires_at: datetime
    approved: bool
    consumed: bool


class SessionAuthority(Protocol):
    def load_session(self, session_id: str) -> SessionSnapshot | None: ...


class ApprovalAuthority(Protocol):
    def load_approval(self, request_digest: str) -> ApprovalSnapshot | None: ...


def verify_computer_use(
    *,
    intent: ComputerUseIntent,
    sessions: SessionAuthority,
    approvals: ApprovalAuthority,
    now: datetime,
    emergency_stop: Callable[[], bool],
) -> bool:
    """Return True only for valid snapshots; failure raises PermissionError.

    Snapshot validation is a *preflight only*. An execution adapter must recheck
    canonical versions and atomically consume mutating approvals to stop replay.
    """
    if not isinstance(intent, ComputerUseIntent):
        raise PermissionError("invalid intent")
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise PermissionError("timezone-aware time required")
    now = now.astimezone(timezone.utc)
    if emergency_stop():
        raise PermissionError("emergency stop is active")
    session = sessions.load_session(intent.session_id)
    if (not isinstance(session, SessionSnapshot) or session.revoked or
        session.stopped or not session.permitted or
        session.expires_at.tzinfo is None or
        session.expires_at.astimezone(timezone.utc) <= now or
        (session.session_id, session.tenant_id, session.actor_id) !=
        (intent.session_id, intent.tenant_id, intent.actor_id)):
        raise PermissionError("invalid or expired session")
    if intent.action is ComputerAction.OBSERVE:
        return True
    approval = approvals.load_approval(intent.request_digest)
    if (not isinstance(approval, ApprovalSnapshot) or
        not approval.approved or approval.consumed or
        approval.expires_at.tzinfo is None or
        approval.expires_at.astimezone(timezone.utc) <= now or
        (approval.tenant_id, approval.actor_id, approval.session_id) !=
        (intent.tenant_id, intent.actor_id, intent.session_id) or
        not hmac.compare_digest(approval.plan_digest, intent.plan_digest) or
        not hmac.compare_digest(approval.request_digest, intent.request_digest)):
        raise PermissionError("approval missing, expired, consumed or mismatched")
    return True
