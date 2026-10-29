from __future__ import annotations

RELEASE_GATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS release_gate_evidence2 (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    release_version TEXT NOT NULL,
    candidate_sha TEXT NOT NULL CHECK(length(candidate_sha)=40),
    gate_id TEXT NOT NULL CHECK(gate_id IN ('A','B','C','D','E','F','G','H')),
    status TEXT NOT NULL CHECK(status IN ('PASS','FAIL','BLOCKED','PENDING')),
    evidence_json TEXT NOT NULL,
    evidence_digest TEXT NOT NULL,
    record_hash TEXT NOT NULL,
    recorded_by TEXT NOT NULL,
    recorded_by_key_id TEXT NOT NULL,
    evaluator TEXT NOT NULL,
    rationale TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_release_gate_evidence_candidate
    ON release_gate_evidence2(tenant_id, release_version, candidate_sha, gate_id, created_at);
CREATE TABLE IF NOT EXISTS release_gate_approvals2 (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    release_version TEXT NOT NULL,
    candidate_sha TEXT NOT NULL CHECK(length(candidate_sha)=40),
    gate_bundle_digest TEXT NOT NULL,
    requested_gate_bundle_digest TEXT NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('APPROVE','REJECT','BLOCKED')),
    approver TEXT NOT NULL,
    approver_key_id TEXT NOT NULL,
    rationale TEXT NOT NULL,
    record_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_release_gate_approvals_candidate
    ON release_gate_approvals2(tenant_id, release_version, candidate_sha, gate_bundle_digest, created_at);
CREATE TABLE IF NOT EXISTS release_gate_decisions2 (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    release_version TEXT NOT NULL,
    candidate_sha TEXT NOT NULL CHECK(length(candidate_sha)=40),
    decision TEXT NOT NULL CHECK(decision IN ('GO','NO_GO')),
    gate_bundle_digest TEXT NOT NULL,
    approval_id TEXT NOT NULL DEFAULT '',
    rollback_target TEXT NOT NULL DEFAULT '',
    release_authority TEXT NOT NULL,
    authority_key_id TEXT NOT NULL,
    rationale TEXT NOT NULL,
    record_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_release_gate_decisions_candidate
    ON release_gate_decisions2(tenant_id, release_version, candidate_sha, created_at);
"""