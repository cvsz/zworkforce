"""Trusted-screen evidence freshness preflight for SAGI computer use.

A stored digest or timestamp from untrusted model output is not evidence.
The worker must generate the snapshot from its own session and clock.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hmac

from zworkforce.sagi_computer_use import ComputerUseIntent


@dataclass(frozen=True)
class TrustedScreenSnapshot:
    tenant_id: str
    actor_id: str
    session_id: str
    sha256: str
    captured_at: datetime
    generation: int


def require_fresh_screen(
    intent: ComputerUseIntent, snapshot: TrustedScreenSnapshot,
    *, now: datetime, max_age_seconds: int = 5, expected_generation: int
) -> None:
    if not isinstance(intent, ComputerUseIntent) or not isinstance(snapshot, TrustedScreenSnapshot):
        raise PermissionError("trusted screen snapshot required")
    if not isinstance(now, datetime) or now.tzinfo is None or snapshot.captured_at.tzinfo is None:
        raise PermissionError("timezone-aware timestamps required")
    if not 1 <= max_age_seconds <= 60 or not isinstance(expected_generation, int):
        raise PermissionError("invalid screen policy")
    if (intent.tenant_id, intent.actor_id, intent.session_id) != (
        snapshot.tenant_id, snapshot.actor_id, snapshot.session_id
    ):
        raise PermissionError("screen session mismatch")
    if snapshot.generation != expected_generation:
        raise PermissionError("stale screen generation")
    if not isinstance(snapshot.sha256, str) or not hmac.compare_digest(
        intent.screen_evidence_digest, snapshot.sha256
    ):
        raise PermissionError("screen digest mismatch")
    age = (now.astimezone(timezone.utc) - snapshot.captured_at.astimezone(timezone.utc)).total_seconds()
    if not 0 <= age <= max_age_seconds:
        raise PermissionError("screen evidence expired or from the future")
