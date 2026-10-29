# ARIN-Z Release Gate Governance

## Purpose and authority boundaries

This contract adds an exact-SHA release gate ledger for zWorkforce. It does not replace the repository's release evidence requirements, GitHub branch protection, independent code review, or the governing release authority.

| Principal | Authority | Prohibited authority |
| --- | --- | --- |
| ARIN-Z | Record stage evidence and run the deterministic evaluator | Approve its own evidence or issue the final release decision |
| policedbc | Independent approval or rejection for the current gate-bundle digest | Record the evidence being approved or issue the final release GO |
| cvsz | Issue the final GO or NO_GO decision after policy evaluation | Override missing/failed gates, stale approvals, invalid audit records, or the rollback requirement |
| zWorkforce | Persist evidence, approvals, decisions, and hash-chained audit events | Infer external production success from CI or a model-generated assertion |

The default identities can be changed only through server-side environment configuration:

- ZWORKFORCE_RELEASE_GATE_RECORDER=arin-z
- ZWORKFORCE_RELEASE_INDEPENDENT_APPROVER=policedbc
- ZWORKFORCE_RELEASE_AUTHORITY=cvsz

The identity check is case-insensitive. API calls must also carry the appropriate role and scope; knowing a principal name is not authentication.

## Exact-SHA binding

Every record requires a stable release version and the full 40-character Git commit SHA. Abbreviated SHAs, branch names, tags, and moving refs are rejected.

Each evidence record includes a server-computed SHA-256 digest of the normalized evidence JSON. The submitted artifact_sha256 is a separate, operator-attested digest of the referenced external artifact. The evaluator validates its format and records the artifact URI; it does not download or independently hash the external artifact. The independent reviewer must verify the referenced artifact, its digest, environment, and observed result.

The gate-bundle digest is calculated from the release version, exact candidate SHA, and the latest immutable record hash/status for each mandatory stage. Approval binds to both the exact candidate SHA and this digest. Any later evidence record changes the bundle digest and makes the prior approval stale.

Once a candidate has a GO decision, evidence and approval mutations for that candidate are frozen. The release authority must first record a NO_GO revocation before the same candidate can be re-evaluated. This prevents an unnoticed evidence update from silently changing the approved bundle.

## Deterministic evaluator

The evaluator is ARIN-Z/deterministic-v1. It is not an LLM judgment and does not accept a caller-supplied status. It evaluates allowlisted fields for Stages A–H:

| Stage | Required assertion family |
| --- | --- |
| A | Immutable deployed image digest, ingress hostname, managed database endpoint class, secret-store reference, and egress-policy reference |
| B | Backup identity, restore run, PITR verification, observed RPO/RTO, and target RPO/RTO; observed values must not exceed targets |
| C | OIDC issuer/JWKS key, successful positive authentication, rejected negative authentication, and API-key lifecycle verification |
| D | Provider failover, bounded execution, and mutation deny-by-default |
| E | Exclusive scheduler lease, worker failover, exclusive outbox claim, and dead-letter verification |
| F | External object PUT, GET, and SHA-256 verification |
| G | Trace correlation, alert delivery receipt, and an operator-owned receiver |
| H | Signature, publisher, timestamp, and live-install smoke verification, plus the signed MSIX digest |

Every stage also requires a timestamp with timezone, environment, result summary, durable artifact URI, valid artifact SHA-256, and either a command descriptor or HTTPS run URL.

Statuses are computed as follows:

- PASS: common evidence is complete and all stage assertions pass deterministic checks.
- FAIL: a required assertion is false, a digest is malformed, or an RPO/RTO target is exceeded.
- BLOCKED: the operator records a blocking reason.
- PENDING: required evidence is missing.

Stage I is not submitted as evidence. It is the final release decision produced by the release authority. For v3.0.4, the final decision requires Stages A–H all PASS, a current independent APPROVE, valid ledger record hashes and audit links, a valid tenant audit hash chain, and rollback target v3.0.3.

## Audit and immutability

Each accepted evidence record, approval attempt, and final decision is inserted as a new record and emits a hash-chained audit event in the same database transaction. The audit event includes the exact candidate SHA, bundle digest where applicable, actor/key ID, outcome, and record hash. API endpoints expose no update/delete operation for these records.

GET /api/v1/release-gates/{version}/{sha}/verify checks the current decision, bundle digest, independent approval, ledger record hashes/audit links, and the tenant audit chain. Release publication must fail closed if verification is unavailable or not GO.

The hash chain detects changes and reordering, while ledger cross-checks detect missing audit links and modified gate rows. As with any database-resident ledger, this is not a substitute for protected database administration, backups, external log retention, or periodic independent audit.

## API and scopes

| Operation | Endpoint | Minimum role and scope | Required identity |
| --- | --- | --- | --- |
| Read current gate snapshot | GET /api/v1/release-gates/{version}/{sha} | viewer + release:read | Any authorized reader |
| Verify release readiness | GET /api/v1/release-gates/{version}/{sha}/verify | viewer + release:verify | Release workflow verifier |
| Record and evaluate evidence | POST /api/v1/release-gates/evidence | operator + release:record | ARIN-Z |
| Independent approval/rejection | POST /api/v1/release-gates/{version}/{sha}/approval | admin + release:approve | policedbc |
| Final decision | POST /api/v1/release-gates/{version}/{sha}/decision | admin + release:decide | cvsz |

Create narrowly scoped API keys and store their one-time secrets outside the repository. The release workflow verifier key should be viewer with only release:verify. Do not use a wildcard scope for service identities.

Example key creation commands for the default tenant (the CLI stores each one-time secret in a protected mode-0600 file and prints the file path):

```bash
zworkforce key-create --name arin-z --role operator --scopes release:record
zworkforce key-create --name policedbc --role admin --scopes release:approve
zworkforce key-create --name cvsz --role admin --scopes release:decide
zworkforce key-create --name release-gate-verifier --role viewer --scopes release:verify
```

Provision these keys in the deployed zWorkforce database. The GitHub workflow secret must contain only the release-gate-verifier key; do not copy recorder, reviewer, or release-authority credentials into GitHub Actions.

Example final approval request:

```json
{
  "decision": "APPROVE",
  "expected_gate_bundle_digest": "<digest returned by the exact-SHA snapshot>",
  "rationale": "Independent review completed against the referenced evidence bundle."
}
```

Example final decision request:

```json
{
  "decision": "GO",
  "rollback_target": "v3.0.3",
  "rationale": "Release authority reviewed the current exact-SHA evidence and approval."
}
```

The service records BLOCKED if approval is attempted against a stale digest, the mandatory gates are incomplete, the approver shares a recorder key, or the candidate is already frozen by GO. A GO request becomes NO_GO whenever any mandatory condition is not met. A NO_GO request is always recorded and can be used to revoke a prior GO before re-evaluation.

## Release workflow enforcement

For version 3.0.4 and later, .github/workflows/release.yml calls scripts/verify_release_gate.py before release build work and again immediately before publishing the OCI image and GitHub Release. The check requires:

- Repository variable ZWORKFORCE_RELEASE_GATE_URL, set to the HTTPS origin of the deployed zWorkforce API.
- Repository secret ZWORKFORCE_RELEASE_GATE_TOKEN, containing a dedicated viewer token with only release:verify.

Missing configuration, API errors, wrong SHA/version, stale digest, failed audit verification, or a non-GO decision stops publication. This workflow check blocks artifact publication; it cannot prevent a Git tag from being created, so the pre-tag operator procedure and tag governance remain mandatory.

## v3.0.4 status boundary

Adding this mechanism does not create external evidence or upgrade any existing gate status. The current source of truth remains docs/PRODUCTION-EVIDENCE.md. Stages that are PENDING, PARTIAL, or BLOCKED stay that way until an operator records real, candidate-bound evidence and the independent reviewer verifies it. No v3.0.4 tag or publication is authorized by this document.
