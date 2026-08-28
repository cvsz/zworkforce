# Phase 6 Operator-Owned Status

Status: `PENDING_OPERATOR`

The following items remain open because they require real production account values, legal/business decisions, approved external services, or human sign-off. Repository automation must not fabricate these values. The repository now carries machine-readable operator records and workflows for the sign-off path, but those records remain placeholders until an authorized operator fills them with real values.

The canonical machine-readable register is `scripts/phase-6-operator-inputs.json`, validated by `scripts/validate-phase-6-operator-inputs.mjs`. It mirrors the remaining Issue #1 `PENDING_OPERATOR` stack without inventing any real values.

- Cloudflare account/zone/team/application and Access policy references
- External identity provider and production claim mapping
- Production secret-manager selection
- Managed production data services, region, backup target, and retention authority
- Billing currency, jurisdiction, tax treatment, merchant responsibilities, and payment processor
- Eligible `main` provenance-attestation evidence
- Approved upstream AI streaming, upload, multi-provider, quota, and failover evidence
- Production browser bundle and network credential inspection
- Agent cancellation and real failure/retry evidence
- Deployed ZWallet and ZChat QA evidence
- Staging reviewer, production approver, incident owner, escalation route, and watch window

Use `phase-6-operator-inputs.md` for the decision register, `docs/release/operational-ownership.md` and `docs/release/production-release-record.md` for the release-owned sign-off forms, and `phase-6-verification-commands.md` for evidence collection.

## Issue #1 operator mapping

| Issue item | Record or workflow that must hold the operator value |
|---|---|
| External identity provider and production claim mapping | `docs/operations/phase-6-operator-inputs.md`, `docs/operations/phase-6-decisions.md`, `docs/operations/cloudflare-access.md`, `scripts/staging-decision-record.json`, `scripts/validate-staging-decision-record.mjs`, `scripts/phase-6-operator-inputs.json`, `scripts/validate-phase-6-operator-inputs.mjs` |
| Production secret-manager selection | `docs/operations/phase-6-operator-inputs.md`, `docs/operations/phase-6-decisions.md`, `docs/operations/github-environments.md`, `scripts/phase-6-operator-inputs.json`, `scripts/validate-phase-6-operator-inputs.mjs` |
| Managed production data services, region, retention authority, observability platform, and external backup target | `docs/operations/phase-6-operator-inputs.md`, `docs/operations/phase-6-decisions.md`, `docs/release/operational-ownership.md`, `scripts/phase-6-operator-inputs.json`, `scripts/validate-phase-6-operator-inputs.mjs` |
| Billing currency, jurisdiction, tax treatment, merchant responsibilities, and payment processor | `docs/operations/phase-6-operator-inputs.md`, `docs/operations/phase-6-decisions.md`, `docs/release/production-release-record.md`, `scripts/phase-6-operator-inputs.json`, `scripts/validate-phase-6-operator-inputs.mjs` |
| Staging reviewer, production approver, incident owner, escalation route, and watch window | `docs/operations/phase-6-operator-inputs.md`, `docs/release/operational-ownership.md`, `.github/workflows/external-staging-readiness.yml`, `.github/workflows/final-release-readiness.yml`, `scripts/phase-6-operator-inputs.json`, `scripts/validate-phase-6-operator-inputs.mjs` |
