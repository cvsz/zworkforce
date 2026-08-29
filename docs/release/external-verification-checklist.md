# External Verification Checklist

Initial state: `PENDING_EXTERNAL`

A checkbox is not evidence. Every passed control must reference an immutable artifact, GitHub Actions run, signed attestation, deployment log, or redacted machine-readable report tied to the exact commit and image digests under review.

## Candidate identity

- [ ] Full 40-character commit SHA recorded.
- [ ] Every deployed image digest recorded.
- [ ] Staging environment, region, deployment time, and operator recorded.
- [ ] Deployed revision equals the candidate under review.

## Infrastructure verification

- [ ] Database connectivity, migration state, backup policy, and restore evidence.
- [ ] Queue publish, consume, retry, dead-letter, and idempotency evidence.
- [ ] Object storage read/write/delete and access-control evidence.
- [ ] IdP authentication, token validation, expiry, and role mapping evidence.
- [ ] Sandbox isolation, resource limits, cancellation, and cleanup evidence.
- [ ] Observability logs, metrics, traces, alert routing, and audit export evidence.
- [ ] Secret manager workload identity and rotation metadata evidence.

## Application verification

- [ ] Health and readiness probes pass against deployed endpoints.
- [ ] Browser and CLI clients use the gateway boundary only.
- [ ] Authentication and authorization success and denial paths pass.
- [ ] Provider model discovery/connectivity passes with staging credentials.
- [ ] Job lifecycle passes: submit -> approve -> execute -> complete.
- [ ] Cancellation is effective and auditable.
- [ ] Retry is idempotent and does not duplicate side effects.
- [ ] Tool grants and mutation approvals are enforced.
- [ ] File upload and workspace metadata paths pass.
- [ ] Streaming behavior and disconnect cleanup pass.

## Resilience and security verification

- [ ] Provider timeout, 4xx, 5xx, and malformed-response paths are exercised.
- [ ] Rate-limit/quota behavior is bounded and observable.
- [ ] Database, queue, storage, and worker degradation paths are exercised.
- [ ] Secrets are absent from browser payloads, logs, reports, and screenshots.
- [ ] TLS and endpoint identity are verified.
- [ ] Audit records identify actor, action, target, decision, and timestamp.

## Required evidence bundle

- [ ] `evidence.json` or equivalent machine-readable report.
- [ ] GitHub Actions run URL and run ID.
- [ ] Deployment logs or GitOps synchronization record.
- [ ] Test report with start/end timestamps.
- [ ] Exact commit and image digests.
- [ ] Redacted account/project/tenant identifiers.
- [ ] Checksums or attestations for generated artifacts.
- [ ] Reviewer-accessible evidence location.

## State transition

`PENDING_EXTERNAL -> VERIFIED_EXTERNAL` is permitted only when:

1. every mandatory check passes;
2. evidence is bound to the same commit and image digests;
3. no unresolved critical/high finding remains;
4. an authorized staging reviewer records the decision;
5. the evidence bundle is retained according to policy.

Otherwise the state remains `PENDING_EXTERNAL` or moves to `EXTERNAL_VERIFICATION_FAILED`.