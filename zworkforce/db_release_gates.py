from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import math
import os
import re
import uuid
from urllib.parse import urlsplit
from typing import Any

from .db_base import json_dumps, json_loads

RELEASE_GATE_EVALUATOR = "ARIN-Z/deterministic-v1"
REQUIRED_RELEASE_GATES = {
    "A": "Staging topology and immutable deployment identity",
    "B": "Managed PostgreSQL backup, restore, and PITR",
    "C": "Production OIDC/JWKS identity and API-key lifecycle",
    "D": "Provider routing, failover, bounded execution, and mutation policy",
    "E": "Scheduler/worker/outbox HA, takeover, and dead-letter behavior",
    "F": "External object storage write/read and SHA-256 verification",
    "G": "Trace correlation and operator-owned alert receipt",
    "H": "Trusted Windows signing, publisher verification, and install smoke",
}

_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IMAGE_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_SECRET_MATERIAL_RE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._~+/=-]{8,}|"
    r"(?:password|token|secret|api[_-]?key)\s*[:=]\s*['\"]?[^,\s;]+|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)

_COMMON_FIELDS = {
    "environment",
    "observed_at_utc",
    "command",
    "run_url",
    "artifact_uri",
    "artifact_sha256",
    "result_summary",
    "blocked_reason",
}
_STAGE_FIELDS = {
    "A": {
        "deployed_image_digest", "ingress_hostname", "database_endpoint_class",
        "secret_store_ref", "egress_policy_ref",
    },
    "B": {
        "backup_id", "restore_run_url", "observed_rpo_seconds", "observed_rto_seconds",
        "target_rpo_seconds", "target_rto_seconds", "pitr_verified",
    },
    "C": {
        "issuer", "jwks_kid", "positive_auth_passed", "negative_auth_rejected",
        "api_key_lifecycle_verified",
    },
    "D": {
        "provider_failover_verified", "bounded_execution_verified",
        "mutation_deny_by_default_verified",
    },
    "E": {
        "scheduler_lease_exclusive", "worker_failover_verified",
        "outbox_claim_exclusive", "dead_letter_verified",
    },
    "F": {"put_object_succeeded", "get_object_succeeded", "sha256_verified"},
    "G": {"trace_correlation_verified", "alert_receipt_verified", "operator_owned_receiver"},
    "H": {
        "signature_verified", "publisher_verified", "timestamp_verified",
        "live_install_smoke_passed", "signed_msix_sha256",
    },
}
_BOOLEAN_FIELDS = {
    "pitr_verified", "positive_auth_passed", "negative_auth_rejected",
    "api_key_lifecycle_verified", "provider_failover_verified",
    "bounded_execution_verified", "mutation_deny_by_default_verified",
    "scheduler_lease_exclusive", "worker_failover_verified", "outbox_claim_exclusive",
    "dead_letter_verified", "put_object_succeeded", "get_object_succeeded",
    "sha256_verified", "trace_correlation_verified", "alert_receipt_verified",
    "operator_owned_receiver", "signature_verified", "publisher_verified",
    "timestamp_verified", "live_install_smoke_passed",
}
_NUMERIC_FIELDS = {
    "observed_rpo_seconds", "observed_rto_seconds",
    "target_rpo_seconds", "target_rto_seconds",
}
_TEXT_FIELDS = {
    "environment", "command", "run_url", "artifact_uri", "artifact_sha256",
    "result_summary", "blocked_reason", "deployed_image_digest", "ingress_hostname",
    "database_endpoint_class", "secret_store_ref", "egress_policy_ref", "backup_id",
    "restore_run_url", "issuer", "jwks_kid", "signed_msix_sha256",
}


def _digest(value: Any) -> str:
    return hashlib.sha256(json_dumps(value).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _identity(env_name: str, default: str) -> str:
    return os.getenv(env_name, default).strip().casefold()


def _configured_key_id(env_name: str) -> str:
    return os.getenv(env_name, "").strip()


def _release_version(value: str) -> str:
    result = str(value or "").strip()
    if not _VERSION_RE.fullmatch(result):
        raise ValueError("release_version must be a stable semantic version such as 3.0.4")
    return result


def _candidate_sha(value: str) -> str:
    result = str(value or "").strip().lower()
    if not _SHA40_RE.fullmatch(result):
        raise ValueError("candidate_sha must be the full 40-character Git commit SHA")
    return result


def _safe_url(value: str, field: str, allow_artifact_scheme: bool = False) -> str:
    result = value.strip()
    parsed = urlsplit(result)
    allowed = {"https", "artifact"} if allow_artifact_scheme else {"https"}
    if (
        parsed.scheme.lower() not in allowed
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{field} must be a credential-free HTTPS or supported artifact URI")
    return result


def _normalize_evidence(gate_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be a JSON object")
    allowed = _COMMON_FIELDS | _STAGE_FIELDS[gate_id]
    unknown = sorted(set(evidence) - allowed)
    if unknown:
        raise ValueError("unsupported evidence fields: " + ", ".join(unknown))

    normalized: dict[str, Any] = {}
    for key, value in evidence.items():
        if value is None:
            continue
        if key in _BOOLEAN_FIELDS:
            if type(value) is not bool:
                raise ValueError(f"{key} must be a boolean")
            normalized[key] = value
            continue
        if key in _NUMERIC_FIELDS:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{key} must be a non-negative number")
            if not math.isfinite(float(value)) or float(value) < 0:
                raise ValueError(f"{key} must be a finite non-negative number")
            normalized[key] = value
            continue
        if key == "observed_at_utc":
            raw_time = str(value).strip()
            if not raw_time:
                continue
            try:
                parsed_time = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("observed_at_utc must be an offset-aware ISO-8601 timestamp") from exc
            if parsed_time.tzinfo is None or parsed_time.utcoffset() is None:
                raise ValueError("observed_at_utc must include a timezone")
            normalized[key] = parsed_time.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            continue
        if key in _TEXT_FIELDS:
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a string")
            text = value.strip()
            if not text:
                continue
            if len(text) > (2048 if key in {"run_url", "artifact_uri", "restore_run_url", "issuer"} else 1000):
                raise ValueError(f"{key} exceeds the permitted length")
            if _SECRET_MATERIAL_RE.search(text):
                raise ValueError(f"{key} appears to contain secret material; record a secret reference, not a secret")
            if key in {"run_url", "restore_run_url", "issuer"}:
                normalized[key] = _safe_url(text, key)
            elif key == "artifact_uri":
                normalized[key] = _safe_url(text, key, allow_artifact_scheme=True)
            else:
                normalized[key] = text
            continue
        raise ValueError(f"unsupported evidence field: {key}")

    return normalized


def _evaluate_gate(gate_id: str, evidence: dict[str, Any]) -> tuple[str, str]:
    blocked_reason = evidence.get("blocked_reason", "").strip()
    if blocked_reason:
        return "BLOCKED", blocked_reason[:500]

    artifact_hash = str(evidence.get("artifact_sha256", "")).lower()
    if artifact_hash and not _SHA256_RE.fullmatch(artifact_hash):
        return "FAIL", "artifact_sha256 is not a valid 64-character SHA-256 digest"
    if gate_id == "A" and "deployed_image_digest" in evidence:
        if not _IMAGE_DIGEST_RE.fullmatch(str(evidence["deployed_image_digest"]).lower()):
            return "FAIL", "deployed_image_digest must be an immutable sha256 image digest"
    if gate_id == "H" and "signed_msix_sha256" in evidence:
        if not _SHA256_RE.fullmatch(str(evidence["signed_msix_sha256"]).lower()):
            return "FAIL", "signed_msix_sha256 is not a valid 64-character SHA-256 digest"

    check_fields = {
        "B": ("pitr_verified",),
        "C": ("positive_auth_passed", "negative_auth_rejected", "api_key_lifecycle_verified"),
        "D": ("provider_failover_verified", "bounded_execution_verified", "mutation_deny_by_default_verified"),
        "E": ("scheduler_lease_exclusive", "worker_failover_verified", "outbox_claim_exclusive", "dead_letter_verified"),
        "F": ("put_object_succeeded", "get_object_succeeded", "sha256_verified"),
        "G": ("trace_correlation_verified", "alert_receipt_verified", "operator_owned_receiver"),
        "H": ("signature_verified", "publisher_verified", "timestamp_verified", "live_install_smoke_passed"),
    }.get(gate_id, ())
    failed_checks = [field for field in check_fields if evidence.get(field) is False]
    if failed_checks:
        return "FAIL", "required checks failed: " + ", ".join(failed_checks)

    if gate_id == "B":
        if "observed_rpo_seconds" in evidence and "target_rpo_seconds" in evidence:
            if evidence["observed_rpo_seconds"] > evidence["target_rpo_seconds"]:
                return "FAIL", "observed RPO exceeds the declared target"
        if "observed_rto_seconds" in evidence and "target_rto_seconds" in evidence:
            if evidence["observed_rto_seconds"] > evidence["target_rto_seconds"]:
                return "FAIL", "observed RTO exceeds the declared target"

    required = {
        "environment", "observed_at_utc", "artifact_uri", "artifact_sha256", "result_summary",
    } | _STAGE_FIELDS[gate_id]
    if not evidence.get("command") and not evidence.get("run_url"):
        required.add("command_or_run_url")
    missing = sorted(field for field in required if field not in evidence)
    if missing:
        return "PENDING", "missing required evidence fields: " + ", ".join(missing)

    return "PASS", "required evidence fields and deterministic stage assertions passed"

def _evidence_material(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "release_version": row["release_version"],
        "candidate_sha": row["candidate_sha"],
        "gate_id": row["gate_id"],
        "status": row["status"],
        "evidence": json_loads(row["evidence_json"], {}),
        "evidence_digest": row["evidence_digest"],
        "recorded_by": row["recorded_by"],
        "recorded_by_key_id": row["recorded_by_key_id"],
        "evaluator": row["evaluator"],
        "rationale": row["rationale"],
        "created_at": row["created_at"],
    }


def _approval_material(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "release_version": row["release_version"],
        "candidate_sha": row["candidate_sha"],
        "gate_bundle_digest": row["gate_bundle_digest"],
        "requested_gate_bundle_digest": row["requested_gate_bundle_digest"],
        "decision": row["decision"],
        "approver": row["approver"],
        "approver_key_id": row["approver_key_id"],
        "rationale": row["rationale"],
        "created_at": row["created_at"],
    }


def _decision_material(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "release_version": row["release_version"],
        "candidate_sha": row["candidate_sha"],
        "decision": row["decision"],
        "gate_bundle_digest": row["gate_bundle_digest"],
        "approval_id": row["approval_id"],
        "rollback_target": row["rollback_target"],
        "release_authority": row["release_authority"],
        "authority_key_id": row["authority_key_id"],
        "rationale": row["rationale"],
        "created_at": row["created_at"],
    }


class ReleaseGateMixin:
    def _begin_release_transaction(self, c, tenant_id: str) -> None:
        if self.backend_kind == "postgres":
            c.execute("BEGIN")
            row = c.execute("SELECT id FROM tenants WHERE id=? FOR UPDATE", (tenant_id,)).fetchone()
        else:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT id FROM tenants WHERE id=?", (tenant_id,)).fetchone()
        if not row:
            raise ValueError("tenant not found")

    def _append_release_audit_cursor(
        self,
        c,
        tenant_id: str,
        actor: str,
        action: str,
        target_type: str,
        target_id: str,
        details: dict[str, Any],
    ) -> str:
        now = _now()
        details_json = json_dumps(details)
        prev = c.execute(
            "SELECT event_hash FROM audit_events2 WHERE tenant_id=? ORDER BY id DESC LIMIT 1",
            (tenant_id,),
        ).fetchone()
        prev_hash = str(prev[0]) if prev else ""
        material = json_dumps({
            "tenant_id": tenant_id,
            "actor": actor,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "details": json_loads(details_json, {}),
            "prev_hash": prev_hash,
            "created_at": now,
        })
        event_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
        c.execute(
            "INSERT INTO audit_events2(tenant_id,actor,action,target_type,target_id,details_json,prev_hash,event_hash,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (tenant_id, actor, action, target_type, target_id, details_json, prev_hash, event_hash, now),
        )
        self._append_dashboard_event_cursor(
            c, tenant_id, "audit.changed", target_type, target_id, {"summary": {"action": action}}
        )
        return event_hash

    def _latest_decision_cursor(self, c, tenant_id: str, version: str, sha: str):
        return c.execute(
            "SELECT * FROM release_gate_decisions2 WHERE tenant_id=? AND release_version=? AND candidate_sha=? "
            "ORDER BY created_at DESC,id DESC LIMIT 1",
            (tenant_id, version, sha),
        ).fetchone()

    def _candidate_evidence_cursor(self, c, tenant_id: str, version: str, sha: str) -> list[dict[str, Any]]:
        rows = c.execute(
            "SELECT * FROM release_gate_evidence2 WHERE tenant_id=? AND release_version=? AND candidate_sha=? "
            "ORDER BY created_at DESC,id DESC",
            (tenant_id, version, sha),
        ).fetchall()
        return [dict(row) for row in rows]

    def _is_independent_approval_cursor(
        self,
        c,
        tenant_id: str,
        version: str,
        sha: str,
        bundle_digest: str,
        approval: dict[str, Any] | None,
        evidence_rows: list[dict[str, Any]] | None = None,
    ) -> bool:
        if not approval or approval.get("decision") != "APPROVE":
            return False
        if approval.get("gate_bundle_digest") != bundle_digest:
            return False
        expected_approver = _identity("ZWORKFORCE_RELEASE_INDEPENDENT_APPROVER", "policedbc")
        configured_recorder = _identity("ZWORKFORCE_RELEASE_GATE_RECORDER", "arin-z")
        configured_authority = _identity("ZWORKFORCE_RELEASE_AUTHORITY", "cvsz")
        recorder_key_id = _configured_key_id("ZWORKFORCE_RELEASE_GATE_RECORDER_KEY_ID")
        approver_key_id = _configured_key_id("ZWORKFORCE_RELEASE_INDEPENDENT_APPROVER_KEY_ID")
        authority_key_id = _configured_key_id("ZWORKFORCE_RELEASE_AUTHORITY_KEY_ID")
        if (
            expected_approver in {configured_recorder, configured_authority}
            or not all((recorder_key_id, approver_key_id, authority_key_id))
            or len({recorder_key_id, approver_key_id, authority_key_id}) != 3
            or str(approval.get("approver_key_id", "")) != approver_key_id
        ):
            return False
        if str(approval.get("approver", "")).casefold() != expected_approver:
            return False
        rows = evidence_rows if evidence_rows is not None else self._candidate_evidence_cursor(c, tenant_id, version, sha)
        recorder_keys = {str(row.get("recorded_by_key_id", "")) for row in rows}
        recorder_keys.discard("")
        return recorder_keys == {recorder_key_id} and approver_key_id not in recorder_keys

    def _snapshot_cursor(self, c, tenant_id: str, version: str, sha: str) -> dict[str, Any]:
        all_rows = self._candidate_evidence_cursor(c, tenant_id, version, sha)
        latest: dict[str, dict[str, Any]] = {}
        for row in all_rows:
            latest.setdefault(str(row["gate_id"]), row)

        gates: list[dict[str, Any]] = []
        bundle_gates: dict[str, Any] = {}
        for gate_id, gate_name in REQUIRED_RELEASE_GATES.items():
            row = latest.get(gate_id)
            if row:
                evidence = json_loads(row["evidence_json"], {})
                gate = {
                    "gate_id": gate_id,
                    "name": gate_name,
                    "status": row["status"],
                    "rationale": row["rationale"],
                    "evidence_digest": row["evidence_digest"],
                    "record_hash": row["record_hash"],
                    "recorded_by": row["recorded_by"],
                    "evaluated_by": row["evaluator"],
                    "created_at": row["created_at"],
                    "evidence": evidence,
                }
                bundle_gates[gate_id] = {"status": row["status"], "record_hash": row["record_hash"]}
            else:
                gate = {
                    "gate_id": gate_id,
                    "name": gate_name,
                    "status": "PENDING",
                    "rationale": "no evidence record exists for this exact candidate SHA",
                    "evidence_digest": "",
                    "record_hash": "",
                    "recorded_by": "",
                    "evaluated_by": RELEASE_GATE_EVALUATOR,
                    "created_at": "",
                    "evidence": None,
                }
                bundle_gates[gate_id] = {"status": "PENDING", "record_hash": ""}
            gates.append(gate)

        bundle_digest = _digest({
            "tenant_id": tenant_id,
            "release_version": version,
            "candidate_sha": sha,
            "gates": bundle_gates,
        })
        approval_row = c.execute(
            "SELECT * FROM release_gate_approvals2 WHERE tenant_id=? AND release_version=? AND candidate_sha=? "
            "AND gate_bundle_digest=? AND decision IN ('APPROVE','REJECT') ORDER BY created_at DESC,id DESC LIMIT 1",
            (tenant_id, version, sha, bundle_digest),
        ).fetchone()
        approval = dict(approval_row) if approval_row else None
        decision_row = self._latest_decision_cursor(c, tenant_id, version, sha)
        decision = dict(decision_row) if decision_row else None
        independent = self._is_independent_approval_cursor(
            c, tenant_id, version, sha, bundle_digest, approval, all_rows
        )
        return {
            "release_version": version,
            "candidate_sha": sha,
            "gate_bundle_digest": bundle_digest,
            "all_gates_pass": all(gate["status"] == "PASS" for gate in gates),
            "gates": gates,
            "approval_valid": independent,
            "approval": approval,
            "decision": decision,
            "_all_evidence_rows": all_rows,
            "_latest_evidence_rows": latest,
            "_approval_row": approval,
            "_decision_row": decision,
        }

    def get_release_gate_snapshot(self, tenant_id: str, release_version: str, candidate_sha: str) -> dict[str, Any]:
        version = _release_version(release_version)
        sha = _candidate_sha(candidate_sha)
        with self.connection() as c:
            snapshot = self._snapshot_cursor(c, tenant_id, version, sha)
        approval = snapshot["_approval_row"]
        decision = snapshot["_decision_row"]
        public_approval = None
        if approval:
            public_approval = {
                "id": approval["id"],
                "decision": approval["decision"],
                "approver": approval["approver"],
                "gate_bundle_digest": approval["gate_bundle_digest"],
                "rationale": approval["rationale"],
                "record_hash": approval["record_hash"],
                "created_at": approval["created_at"],
            }
        public_decision = None
        if decision:
            public_decision = {
                "id": decision["id"],
                "decision": decision["decision"],
                "candidate_sha": decision["candidate_sha"],
                "gate_bundle_digest": decision["gate_bundle_digest"],
                "approval_id": decision["approval_id"],
                "rollback_target": decision["rollback_target"],
                "release_authority": decision["release_authority"],
                "rationale": decision["rationale"],
                "record_hash": decision["record_hash"],
                "created_at": decision["created_at"],
            }
        return {
            "release_version": snapshot["release_version"],
            "candidate_sha": snapshot["candidate_sha"],
            "gate_bundle_digest": snapshot["gate_bundle_digest"],
            "all_gates_pass": snapshot["all_gates_pass"],
            "gates": snapshot["gates"],
            "approval_valid": snapshot["approval_valid"],
            "approval": public_approval,
            "decision": public_decision,
        }

    def record_release_gate_evidence(
        self,
        tenant_id: str,
        release_version: str,
        candidate_sha: str,
        gate_id: str,
        evidence: dict[str, Any],
        recorded_by: str,
        recorded_by_key_id: str,
    ) -> dict[str, Any]:
        version = _release_version(release_version)
        sha = _candidate_sha(candidate_sha)
        gate = str(gate_id or "").strip().upper()
        if gate not in REQUIRED_RELEASE_GATES:
            raise ValueError("gate_id must be one of A through H; Stage I is the derived release decision")
        if not str(recorded_by or "").strip() or not str(recorded_by_key_id or "").strip():
            raise ValueError("authenticated recorder identity and key ID are required")
        normalized = _normalize_evidence(gate, evidence)
        status, rationale = _evaluate_gate(gate, normalized)
        evidence_digest = _digest(normalized)
        record_id = uuid.uuid4().hex
        configured_recorder = _identity("ZWORKFORCE_RELEASE_GATE_RECORDER", "arin-z")

        with self.connection() as c:
            try:
                self._begin_release_transaction(c, tenant_id)
                latest_decision = self._latest_decision_cursor(c, tenant_id, version, sha)
                configured_recorder_key_id = _configured_key_id("ZWORKFORCE_RELEASE_GATE_RECORDER_KEY_ID")
                if (
                    str(recorded_by).casefold() != configured_recorder
                    or not configured_recorder_key_id
                    or recorded_by_key_id != configured_recorder_key_id
                ):
                    self._append_release_audit_cursor(
                        c, tenant_id, recorded_by, "release_gate.evidence.denied",
                        "release_gate", record_id,
                        {"release_version": version, "candidate_sha": sha, "gate_id": gate,
                         "principal_key_id": recorded_by_key_id, "reason": "recorder identity/key ID is not configured ARIN-Z"},
                    )
                    c.execute("COMMIT")
                    return {"recorded": False, "status": "BLOCKED", "gate_id": gate,
                            "candidate_sha": sha, "rationale": "only the configured ARIN-Z recorder key may submit gate evidence"}
                if latest_decision and latest_decision["decision"] == "GO":
                    self._append_release_audit_cursor(
                        c, tenant_id, recorded_by, "release_gate.evidence.denied_after_go",
                        "release_gate", record_id,
                        {"release_version": version, "candidate_sha": sha, "gate_id": gate,
                         "principal_key_id": recorded_by_key_id, "reason": "candidate is frozen by a GO decision"},
                    )
                    c.execute("COMMIT")
                    return {"recorded": False, "status": "BLOCKED", "gate_id": gate,
                            "candidate_sha": sha, "rationale": "candidate is frozen by GO; record NO_GO before changing its evidence"}

                now = _now()
                material = {
                    "id": record_id,
                    "tenant_id": tenant_id,
                    "release_version": version,
                    "candidate_sha": sha,
                    "gate_id": gate,
                    "status": status,
                    "evidence": normalized,
                    "evidence_digest": evidence_digest,
                    "recorded_by": recorded_by,
                    "recorded_by_key_id": recorded_by_key_id,
                    "evaluator": RELEASE_GATE_EVALUATOR,
                    "rationale": rationale,
                    "created_at": now,
                }
                record_hash = _digest(material)
                c.execute(
                    "INSERT INTO release_gate_evidence2(id,tenant_id,release_version,candidate_sha,gate_id,status,"
                    "evidence_json,evidence_digest,record_hash,recorded_by,recorded_by_key_id,evaluator,rationale,created_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (record_id, tenant_id, version, sha, gate, status, json_dumps(normalized), evidence_digest,
                     record_hash, recorded_by, recorded_by_key_id, RELEASE_GATE_EVALUATOR, rationale, now),
                )
                self._append_release_audit_cursor(
                    c, tenant_id, recorded_by, "release_gate.evidence.recorded", "release_gate_evidence", record_id,
                    {"release_version": version, "candidate_sha": sha, "gate_id": gate, "status": status,
                     "evidence_digest": evidence_digest, "record_hash": record_hash,
                     "principal_key_id": recorded_by_key_id, "evaluator": RELEASE_GATE_EVALUATOR},
                )
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise

        return {
            "recorded": True,
            "id": record_id,
            "release_version": version,
            "candidate_sha": sha,
            "gate_id": gate,
            "status": status,
            "evidence_digest": evidence_digest,
            "record_hash": record_hash,
            "recorded_by": recorded_by,
            "evaluated_by": RELEASE_GATE_EVALUATOR,
            "rationale": rationale,
            "created_at": now,
        }

    def approve_release_candidate(
        self,
        tenant_id: str,
        release_version: str,
        candidate_sha: str,
        decision: str,
        expected_gate_bundle_digest: str,
        approver: str,
        approver_key_id: str,
        rationale: str = "",
    ) -> dict[str, Any]:
        version = _release_version(release_version)
        sha = _candidate_sha(candidate_sha)
        requested = str(decision or "").strip().upper()
        if requested not in {"APPROVE", "REJECT"}:
            raise ValueError("decision must be APPROVE or REJECT")
        expected_digest = str(expected_gate_bundle_digest or "").strip().lower()
        if not _SHA256_RE.fullmatch(expected_digest):
            raise ValueError("expected_gate_bundle_digest must be a 64-character SHA-256 digest")
        if not str(approver or "").strip() or not str(approver_key_id or "").strip():
            raise ValueError("authenticated approver identity and key ID are required")

        approval_id = uuid.uuid4().hex
        configured_approver = _identity("ZWORKFORCE_RELEASE_INDEPENDENT_APPROVER", "policedbc")

        with self.connection() as c:
            try:
                self._begin_release_transaction(c, tenant_id)
                snapshot = self._snapshot_cursor(c, tenant_id, version, sha)
                latest_decision = snapshot["_decision_row"]
                stored_decision = requested
                reasons: list[str] = []
                configured_recorder = _identity("ZWORKFORCE_RELEASE_GATE_RECORDER", "arin-z")
                configured_authority = _identity("ZWORKFORCE_RELEASE_AUTHORITY", "cvsz")
                recorder_key_id = _configured_key_id("ZWORKFORCE_RELEASE_GATE_RECORDER_KEY_ID")
                configured_approver_key_id = _configured_key_id("ZWORKFORCE_RELEASE_INDEPENDENT_APPROVER_KEY_ID")
                authority_key_id = _configured_key_id("ZWORKFORCE_RELEASE_AUTHORITY_KEY_ID")
                if str(approver).casefold() != configured_approver:
                    reasons.append("approver identity is not the configured independent reviewer")
                if len({configured_recorder, configured_approver, configured_authority}) != 3:
                    reasons.append("configured recorder, approver, and release authority identities are not independent")
                if (
                    not all((recorder_key_id, configured_approver_key_id, authority_key_id))
                    or len({recorder_key_id, configured_approver_key_id, authority_key_id}) != 3
                ):
                    reasons.append("configured recorder, approver, and release authority key IDs are missing or not independent")
                if approver_key_id != configured_approver_key_id:
                    reasons.append("approver key ID does not match the provisioned independent reviewer key")
                if str(approver).casefold() in {configured_recorder, configured_authority}:
                    reasons.append("approver identity is not independent from recorder and release authority")
                if expected_digest != snapshot["gate_bundle_digest"]:
                    reasons.append("approval request is bound to a stale gate bundle digest")
                recorder_names = {str(row.get("recorded_by", "")).casefold() for row in snapshot["_all_evidence_rows"]}
                if str(approver).casefold() in recorder_names:
                    reasons.append("approver identity is also a gate-evidence recorder")
                recorder_keys = {str(row.get("recorded_by_key_id", "")) for row in snapshot["_all_evidence_rows"]}
                if approver_key_id in recorder_keys:
                    reasons.append("approver key is also a gate-evidence recorder key")
                if requested == "APPROVE" and not snapshot["all_gates_pass"]:
                    reasons.append("one or more mandatory gates are not PASS")
                if latest_decision and latest_decision["decision"] == "GO":
                    reasons.append("candidate is frozen by an existing GO decision")
                if reasons:
                    stored_decision = "BLOCKED"

                note = str(rationale or "").strip()[:1000]
                final_rationale = "; ".join(reasons + ([note] if note else [])) or (
                    "Independent reviewer rejected the candidate." if stored_decision == "REJECT"
                    else "Independent reviewer approved the current exact-SHA gate bundle."
                )
                now = _now()
                approval_material = {
                    "id": approval_id,
                    "tenant_id": tenant_id,
                    "release_version": version,
                    "candidate_sha": sha,
                    "gate_bundle_digest": snapshot["gate_bundle_digest"],
                    "requested_gate_bundle_digest": expected_digest,
                    "decision": stored_decision,
                    "approver": approver,
                    "approver_key_id": approver_key_id,
                    "rationale": final_rationale,
                    "created_at": now,
                }
                record_hash = _digest(approval_material)
                c.execute(
                    "INSERT INTO release_gate_approvals2(id,tenant_id,release_version,candidate_sha,gate_bundle_digest,"
                    "requested_gate_bundle_digest,decision,approver,approver_key_id,rationale,record_hash,created_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (approval_id, tenant_id, version, sha, snapshot["gate_bundle_digest"], expected_digest,
                     stored_decision, approver, approver_key_id, final_rationale, record_hash, now),
                )
                self._append_release_audit_cursor(
                    c, tenant_id, approver, "release_gate.approval.recorded", "release_gate_approval", approval_id,
                    {"release_version": version, "candidate_sha": sha, "gate_bundle_digest": snapshot["gate_bundle_digest"],
                     "requested_gate_bundle_digest": expected_digest, "decision": stored_decision,
                     "principal_key_id": approver_key_id, "record_hash": record_hash, "rationale": final_rationale},
                )
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise

        return {
            "id": approval_id,
            "release_version": version,
            "candidate_sha": sha,
            "gate_bundle_digest": snapshot["gate_bundle_digest"],
            "requested_gate_bundle_digest": expected_digest,
            "decision": stored_decision,
            "approver": approver,
            "record_hash": record_hash,
            "rationale": final_rationale,
            "created_at": now,
        }

    def decide_release_candidate(
        self,
        tenant_id: str,
        release_version: str,
        candidate_sha: str,
        requested_decision: str,
        rollback_target: str,
        release_authority: str,
        authority_key_id: str,
        rationale: str = "",
    ) -> dict[str, Any]:
        version = _release_version(release_version)
        sha = _candidate_sha(candidate_sha)
        requested = str(requested_decision or "").strip().upper()
        if requested not in {"GO", "NO_GO"}:
            raise ValueError("decision must be GO or NO_GO")
        if not str(release_authority or "").strip() or not str(authority_key_id or "").strip():
            raise ValueError("authenticated release-authority identity and key ID are required")

        decision_id = uuid.uuid4().hex
        configured_authority = _identity("ZWORKFORCE_RELEASE_AUTHORITY", "cvsz")
        normalized_rollback = str(rollback_target or "").strip()
        with self.connection() as c:
            try:
                self._begin_release_transaction(c, tenant_id)
                snapshot = self._snapshot_cursor(c, tenant_id, version, sha)
                configured_authority_key_id = _configured_key_id("ZWORKFORCE_RELEASE_AUTHORITY_KEY_ID")
                if (
                    str(release_authority).casefold() != configured_authority
                    or not configured_authority_key_id
                    or authority_key_id != configured_authority_key_id
                ):
                    rationale_text = "release decision request did not authenticate as the provisioned release-authority key"
                    self._append_release_audit_cursor(
                        c, tenant_id, release_authority, "release_gate.decision.denied",
                        "release_gate", decision_id,
                        {"release_version": version, "candidate_sha": sha,
                         "principal_key_id": authority_key_id, "reason": rationale_text},
                    )
                    c.execute("COMMIT")
                    return {
                        "id": decision_id,
                        "release_version": version,
                        "candidate_sha": sha,
                        "decision": "BLOCKED",
                        "recorded": False,
                        "gate_bundle_digest": snapshot["gate_bundle_digest"],
                        "rationale": rationale_text,
                        "created_at": _now(),
                    }
                approval = snapshot["_approval_row"]
                all_recorders = {str(row.get("recorded_by_key_id", "")) for row in snapshot["_all_evidence_rows"]}
                all_recorders.discard("")
                ledger_result = self._verify_release_gate_ledger_cursor(c, tenant_id, version, sha)
                audit_result = self._verify_audit_chain_cursor(c, tenant_id)
                reasons: list[str] = []
                configured_recorder = _identity("ZWORKFORCE_RELEASE_GATE_RECORDER", "arin-z")
                configured_approver = _identity("ZWORKFORCE_RELEASE_INDEPENDENT_APPROVER", "policedbc")
                recorder_key_id = _configured_key_id("ZWORKFORCE_RELEASE_GATE_RECORDER_KEY_ID")
                configured_approver_key_id = _configured_key_id("ZWORKFORCE_RELEASE_INDEPENDENT_APPROVER_KEY_ID")
                configured_authority_key_id = _configured_key_id("ZWORKFORCE_RELEASE_AUTHORITY_KEY_ID")

                if str(release_authority).casefold() != configured_authority:
                    reasons.append("release authority identity is not the configured authority")
                if len({configured_recorder, configured_approver, configured_authority}) != 3:
                    reasons.append("configured recorder, approver, and release authority identities are not independent")
                if (
                    not all((recorder_key_id, configured_approver_key_id, configured_authority_key_id))
                    or len({recorder_key_id, configured_approver_key_id, configured_authority_key_id}) != 3
                ):
                    reasons.append("configured recorder, approver, and release authority key IDs are missing or not independent")
                if authority_key_id != configured_authority_key_id:
                    reasons.append("release authority key ID does not match the provisioned authority key")
                if approval and str(approval.get("approver_key_id", "")) != configured_approver_key_id:
                    reasons.append("independent approval key ID does not match the provisioned reviewer key")
                recorder_names = {str(row.get("recorded_by", "")).casefold() for row in snapshot["_all_evidence_rows"]}
                if str(release_authority).casefold() in recorder_names:
                    reasons.append("release authority identity is also a gate-evidence recorder")
                if approval and str(release_authority).casefold() == str(approval.get("approver", "")).casefold():
                    reasons.append("release authority identity must be distinct from the independent approver")
                if authority_key_id in all_recorders:
                    reasons.append("release authority key is also a gate-evidence recorder key")
                if not snapshot["all_gates_pass"]:
                    pending = [f'{gate["gate_id"]}={gate["status"]}' for gate in snapshot["gates"] if gate["status"] != "PASS"]
                    reasons.append("mandatory gates are not all PASS: " + ", ".join(pending))
                if not snapshot["approval_valid"]:
                    reasons.append("no current independent APPROVE exists for the exact gate bundle digest")
                if approval and authority_key_id == approval.get("approver_key_id"):
                    reasons.append("release authority key must be distinct from the independent approver key")
                if not ledger_result["ok"]:
                    reasons.append("release gate ledger hashes or audit links failed verification")
                if not audit_result["ok"]:
                    reasons.append("tenant audit hash chain failed verification")
                if version == "3.0.4" and normalized_rollback != "v3.0.3":
                    reasons.append("v3.0.4 requires rollback_target=v3.0.3")

                if requested == "NO_GO":
                    stored_decision = "NO_GO"
                    final_rationale = str(rationale or "").strip()[:1000] or "Release authority explicitly recorded NO_GO."
                else:
                    stored_decision = "GO" if not reasons else "NO_GO"
                    note = str(rationale or "").strip()[:1000]
                    if stored_decision == "GO":
                        final_rationale = "All mandatory gates, independent approval, exact-SHA binding, audit verification, and rollback checks passed."
                        if note:
                            final_rationale += " Authority note: " + note
                    else:
                        final_rationale = "; ".join(reasons + ([note] if note else []))

                approval_id = str(approval.get("id", "")) if approval else ""
                now = _now()
                material = {
                    "id": decision_id,
                    "tenant_id": tenant_id,
                    "release_version": version,
                    "candidate_sha": sha,
                    "decision": stored_decision,
                    "gate_bundle_digest": snapshot["gate_bundle_digest"],
                    "approval_id": approval_id,
                    "rollback_target": normalized_rollback,
                    "release_authority": release_authority,
                    "authority_key_id": authority_key_id,
                    "rationale": final_rationale,
                    "created_at": now,
                }
                record_hash = _digest(material)
                c.execute(
                    "INSERT INTO release_gate_decisions2(id,tenant_id,release_version,candidate_sha,decision,"
                    "gate_bundle_digest,approval_id,rollback_target,release_authority,authority_key_id,rationale,record_hash,created_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (decision_id, tenant_id, version, sha, stored_decision, snapshot["gate_bundle_digest"],
                     approval_id, normalized_rollback, release_authority, authority_key_id, final_rationale, record_hash, now),
                )
                self._append_release_audit_cursor(
                    c, tenant_id, release_authority, "release_gate.decision.recorded", "release_gate_decision", decision_id,
                    {"release_version": version, "candidate_sha": sha, "decision": stored_decision,
                     "gate_bundle_digest": snapshot["gate_bundle_digest"], "approval_id": approval_id,
                     "rollback_target": normalized_rollback, "principal_key_id": authority_key_id,
                     "record_hash": record_hash, "rationale": final_rationale},
                )
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise

        return {
            "id": decision_id,
            "release_version": version,
            "candidate_sha": sha,
            "decision": stored_decision,
            "gate_bundle_digest": snapshot["gate_bundle_digest"],
            "approval_id": approval_id,
            "rollback_target": normalized_rollback,
            "release_authority": release_authority,
            "record_hash": record_hash,
            "rationale": final_rationale,
            "created_at": now,
        }

    def _verify_audit_chain_cursor(self, c, tenant_id: str) -> dict[str, Any]:
        rows = c.execute("SELECT * FROM audit_events2 WHERE tenant_id=? ORDER BY id ASC", (tenant_id,)).fetchall()
        previous = ""
        for row in rows:
            record = dict(row)
            material = json_dumps({
                "tenant_id": record["tenant_id"],
                "actor": record["actor"],
                "action": record["action"],
                "target_type": record["target_type"],
                "target_id": record["target_id"],
                "details": json_loads(record["details_json"], {}),
                "prev_hash": previous,
                "created_at": record["created_at"],
            })
            expected = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if record["prev_hash"] != previous or record["event_hash"] != expected:
                return {"ok": False, "events": len(rows), "bad_event_id": record["id"]}
            previous = record["event_hash"]
        return {"ok": True, "events": len(rows), "head": previous}

    def _verify_release_gate_ledger_cursor(
        self, c, tenant_id: str, version: str, sha: str
    ) -> dict[str, Any]:
        evidence_rows = [
            dict(row) for row in c.execute(
                "SELECT * FROM release_gate_evidence2 WHERE tenant_id=? AND release_version=? AND candidate_sha=?",
                (tenant_id, version, sha),
            ).fetchall()
        ]
        approval_rows = [
            dict(row) for row in c.execute(
                "SELECT * FROM release_gate_approvals2 WHERE tenant_id=? AND release_version=? AND candidate_sha=?",
                (tenant_id, version, sha),
            ).fetchall()
        ]
        decision_rows = [
            dict(row) for row in c.execute(
                "SELECT * FROM release_gate_decisions2 WHERE tenant_id=? AND release_version=? AND candidate_sha=?",
                (tenant_id, version, sha),
            ).fetchall()
        ]
        expected_events: set[tuple[str, str, str, str]] = set()
        valid = True
        for row in evidence_rows:
            evidence = json_loads(row["evidence_json"], {})
            evaluated_status, evaluated_rationale = _evaluate_gate(row["gate_id"], evidence)
            if (
                _digest(evidence) != row["evidence_digest"]
                or _digest(_evidence_material(row)) != row["record_hash"]
                or row["evaluator"] != RELEASE_GATE_EVALUATOR
                or row["recorded_by"].casefold() != _identity("ZWORKFORCE_RELEASE_GATE_RECORDER", "arin-z")
                or evaluated_status != row["status"]
                or evaluated_rationale != row["rationale"]
            ):
                valid = False
            expected_events.add(("release_gate.evidence.recorded", "release_gate_evidence", row["id"], row["record_hash"]))
        for row in approval_rows:
            if _digest(_approval_material(row)) != row["record_hash"]:
                valid = False
            expected_events.add(("release_gate.approval.recorded", "release_gate_approval", row["id"], row["record_hash"]))
        for row in decision_rows:
            if _digest(_decision_material(row)) != row["record_hash"]:
                valid = False
            expected_events.add(("release_gate.decision.recorded", "release_gate_decision", row["id"], row["record_hash"]))

        audit_rows = c.execute(
            "SELECT action,target_type,target_id,details_json FROM audit_events2 WHERE tenant_id=?",
            (tenant_id,),
        ).fetchall()
        actual_events: set[tuple[str, str, str, str]] = set()
        for row in audit_rows:
            audit = dict(row)
            details = json_loads(audit["details_json"], {})
            if details.get("release_version") != version or details.get("candidate_sha") != sha:
                continue
            action = str(audit["action"])
            if action not in {
                "release_gate.evidence.recorded",
                "release_gate.approval.recorded",
                "release_gate.decision.recorded",
            }:
                continue
            actual_events.add((action, str(audit["target_type"]), str(audit["target_id"]), str(details.get("record_hash", ""))))
        if expected_events != actual_events:
            valid = False
        return {
            "ok": valid,
            "evidence_records": len(evidence_rows),
            "approval_records": len(approval_rows),
            "decision_records": len(decision_rows),
        }

    def verify_release_candidate(self, tenant_id: str, release_version: str, candidate_sha: str) -> dict[str, Any]:
        version = _release_version(release_version)
        sha = _candidate_sha(candidate_sha)
        with self.connection() as c:
            try:
                self._begin_release_transaction(c, tenant_id)
                snapshot = self._snapshot_cursor(c, tenant_id, version, sha)
                ledger_result = self._verify_release_gate_ledger_cursor(c, tenant_id, version, sha)
                audit_result = self._verify_audit_chain_cursor(c, tenant_id)
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise

        reasons: list[str] = []
        if not ledger_result["ok"]:
            reasons.append("release gate ledger hashes or audit links failed verification")
        if not audit_result["ok"]:
            reasons.append("tenant audit hash chain failed verification")
        if not snapshot["all_gates_pass"]:
            pending = [f'{gate["gate_id"]}={gate["status"]}' for gate in snapshot["gates"] if gate["status"] != "PASS"]
            reasons.append("mandatory gates are not all PASS: " + ", ".join(pending))
        if not snapshot["approval_valid"]:
            reasons.append("current independent approval is missing, stale, rejected, or not independent")

        decision = snapshot["_decision_row"]
        approval = snapshot["_approval_row"]
        if not decision:
            reasons.append("Stage I release decision is missing")
        else:
            if decision["decision"] != "GO":
                reasons.append("latest release decision is NO_GO")
            if decision["gate_bundle_digest"] != snapshot["gate_bundle_digest"]:
                reasons.append("release decision is bound to a stale gate bundle digest")
            if not approval or decision["approval_id"] != approval.get("id") or approval.get("decision") != "APPROVE":
                reasons.append("release decision does not reference the current independent approval")
            if version == "3.0.4" and decision["rollback_target"] != "v3.0.3":
                reasons.append("v3.0.4 rollback target is not v3.0.3")
            configured_authority = _identity("ZWORKFORCE_RELEASE_AUTHORITY", "cvsz")
            configured_recorder = _identity("ZWORKFORCE_RELEASE_GATE_RECORDER", "arin-z")
            configured_approver = _identity("ZWORKFORCE_RELEASE_INDEPENDENT_APPROVER", "policedbc")
            recorder_key_id = _configured_key_id("ZWORKFORCE_RELEASE_GATE_RECORDER_KEY_ID")
            configured_approver_key_id = _configured_key_id("ZWORKFORCE_RELEASE_INDEPENDENT_APPROVER_KEY_ID")
            configured_authority_key_id = _configured_key_id("ZWORKFORCE_RELEASE_AUTHORITY_KEY_ID")
            if str(decision["release_authority"]).casefold() != configured_authority:
                reasons.append("release decision was not issued by the configured release authority")
            if len({configured_recorder, configured_approver, configured_authority}) != 3:
                reasons.append("configured recorder, approver, and release authority identities are not independent")
            if (
                not all((recorder_key_id, configured_approver_key_id, configured_authority_key_id))
                or len({recorder_key_id, configured_approver_key_id, configured_authority_key_id}) != 3
            ):
                reasons.append("configured recorder, approver, and release authority key IDs are missing or not independent")
            if decision["authority_key_id"] != configured_authority_key_id:
                reasons.append("release decision key ID does not match the provisioned authority key")
            if approval and approval.get("approver_key_id") != configured_approver_key_id:
                reasons.append("independent approval key ID does not match the provisioned reviewer key")
            recorder_names = {str(row.get("recorded_by", "")).casefold() for row in snapshot["_all_evidence_rows"]}
            if str(decision["release_authority"]).casefold() in recorder_names:
                reasons.append("release authority identity is also a gate-evidence recorder")
            if approval and str(decision["release_authority"]).casefold() == str(approval.get("approver", "")).casefold():
                reasons.append("release authority identity is not distinct from the independent approver")
            recorder_keys = {str(row.get("recorded_by_key_id", "")) for row in snapshot["_all_evidence_rows"]}
            recorder_keys.discard("")
            if recorder_keys and recorder_keys != {recorder_key_id}:
                reasons.append("gate evidence was not recorded by the configured ARIN-Z key")
            if decision["authority_key_id"] in recorder_keys:
                reasons.append("release authority key is not independent from gate recording")
            if approval and decision["authority_key_id"] == approval.get("approver_key_id"):
                reasons.append("release authority key is not independent from the approver")

        public_decision = None
        if decision:
            public_decision = {
                "id": decision["id"],
                "decision": decision["decision"],
                "candidate_sha": decision["candidate_sha"],
                "gate_bundle_digest": decision["gate_bundle_digest"],
                "approval_id": decision["approval_id"],
                "rollback_target": decision["rollback_target"],
                "release_authority": decision["release_authority"],
                "rationale": decision["rationale"],
                "created_at": decision["created_at"],
                "record_hash": decision["record_hash"],
            }
        public_approval = None
        if approval:
            public_approval = {
                "id": approval["id"],
                "decision": approval["decision"],
                "approver": approval["approver"],
                "gate_bundle_digest": approval["gate_bundle_digest"],
                "rationale": approval["rationale"],
                "created_at": approval["created_at"],
                "record_hash": approval["record_hash"],
            }
        return {
            "release_version": version,
            "candidate_sha": sha,
            "release_ready": not reasons,
            "decision": decision["decision"] if decision else None,
            "gate_bundle_digest": snapshot["gate_bundle_digest"],
            "all_gates_pass": snapshot["all_gates_pass"],
            "independent_approval_valid": snapshot["approval_valid"],
            "ledger_valid": ledger_result["ok"],
            "ledger_verification": ledger_result,
            "audit_chain": audit_result,
            "approval": public_approval,
            "release_decision": public_decision,
            "rollback_target": decision["rollback_target"] if decision else None,
            "reasons": reasons,
        }
