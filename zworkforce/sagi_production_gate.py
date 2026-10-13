"""Fail-closed production admission for SAGI Computer Use.

Evidence is supplied by independent deployment and security authorities;
application configuration or a PR status cannot fabricate these attestations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import FrozenSet

REQUIRED = frozenset({
    "canonical_approval_action_binding",
    "atomic_claim_and_worker_fencing",
    "durable_audit_and_reconciliation",
    "tenant_session_isolation",
    "network_egress_enforcement",
    "inflight_emergency_stop",
    "trusted_screen_freshness",
    "live_chromium_e2e",
    "negative_network_isolation_e2e",
    "independent_security_approval",
})


@dataclass(frozen=True)
class DeploymentEvidence:
    gate: str
    reference: str
    attested_at: datetime
    reviewed_by: str
    deployment_sha: str


def assert_sagi_production_ready(
    *,
    evidence: tuple[DeploymentEvidence, ...],
    deployment_sha: str,
    now: datetime,
    max_evidence_age_days: int = 7,
) -> None:
    """Reject rollout unless all independently attested gates are present.

    This is a validation contract, not a cryptographic attestation verifier.
    Callers must load these records from a trusted evidence authority and
    validate that source's access control and signatures independently.
    """
    if not isinstance(deployment_sha, str) or len(deployment_sha) != 40 or any(
        char not in "0123456789abcdef" for char in deployment_sha
    ):
        raise PermissionError("immutable deployment commit SHA required")
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise PermissionError("aware clock required")
    if not isinstance(max_evidence_age_days, int) or not 1 <= max_evidence_age_days <= 30:
        raise PermissionError("invalid evidence age")
    seen = set()
    for item in evidence:
        if not isinstance(item, DeploymentEvidence) or item.gate not in REQUIRED:
            raise PermissionError("unknown production evidence")
        if item.gate in seen:
            raise PermissionError("duplicate production evidence")
        seen.add(item.gate)
        if not all(isinstance(v, str) and v.strip() for v in
                   (item.reference, item.reviewed_by, item.deployment_sha)):
            raise PermissionError("unattributed evidence")
        if item.deployment_sha != deployment_sha:
            raise PermissionError("evidence is for a different deployment")
        if not isinstance(item.attested_at, datetime) or item.attested_at.tzinfo is None:
            raise PermissionError("evidence timestamp missing")
        age = (now.astimezone(timezone.utc) -
               item.attested_at.astimezone(timezone.utc)).total_seconds()
        if not 0 <= age <= max_evidence_age_days * 86400:
            raise PermissionError("expired or future-dated evidence")
    if seen != REQUIRED:
        raise PermissionError("missing SAGI production security gates")
