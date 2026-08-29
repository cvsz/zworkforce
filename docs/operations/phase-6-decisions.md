# Phase 6 Provider, Identity, Operations, and Business Decisions

This document records the implemented defaults and the values that still require an authorized operator. It must not contain credentials, account IDs, zone IDs, payment secrets, or personal data.

## Identity and tenant model

- Service-to-service identity: bearer `Z_PLATFORM_SERVICE_TOKEN`, stored outside the repository.
- Tenant context: `X-Tenant-Id`; subject context: `X-Subject-Id`.
- Approval policy: authenticated user identity with separation of duties; a job requester must not self-approve in production.
- External identity provider: operator-selected OIDC provider. Required claims: `sub`, `iss`, `aud`, tenant claim, roles/groups, and MFA assurance where available.
- Browser applications must call a backend-for-frontend and must never receive provider credentials or service tokens.
- The operator-owned identity decision snapshot is tracked in `scripts/staging-decision-record.json`, described by `schemas/operations/staging-decision-record.schema.json`, and validated by `scripts/validate-staging-decision-record.mjs`; it carries the approved identity-provider class and tenant-claim mapping reference without exposing secret values.

## Cloudflare Access mapping

- Edge control: Cloudflare Access in front of browser-facing staging and production origins.
- Team domain, account ID, zone ID, application IDs, and policy IDs: operator-supplied through the approved secret manager or deployment variables.
- Minimum policies: deny by default; require organization identity; require MFA for operator surfaces; service-token policy only for non-browser workloads; no bypass policy for production.
- Validation gate: deployment fails when required Cloudflare identifiers are absent in staging/production.

## Secret management

- Local development: uncommitted `.env`, mode `0600`.
- CI/staging bootstrap: GitHub Environment secrets with required reviewers, configured through the repository helper script or the GitHub UI.
- Production: external secret manager selected by the infrastructure owner. GitHub stores only workload-identity/bootstrap references, not long-lived production credentials.
- Rotation: service/provider tokens rotate at least every 90 days and immediately after suspected disclosure.

## Data and runtime providers

- Local/staging durable baseline: `agent-provider` with a Docker named volume.
- Job store: durable JSON state implementing idempotent lookup and atomic replacement.
- Queue: durable FIFO queue with duplicate enqueue suppression by `(job_id, attempt)`.
- Audit: append-only event collection exposed only to authenticated service clients.
- Workspace metadata: durable records plus retention cleanup endpoint.
- Sandbox: approval-gated `/execute`; mutating grants require restricted sandbox constraints.
- Supabase read-only bridge: authenticated Phase 6 API route reading a Supabase Data API table using `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_TABLE`; the anon key stays server-side and the route remains read-only.
- Production database/queue/object storage: managed services selected by the infrastructure owner before production traffic.

## Observability

- Logs: structured JSON for application events.
- Metrics: Prometheus-compatible `/metrics` endpoint for the durable agent provider.
- Tracing: W3C Trace Context is the required propagation standard; deployment verification remains required for all services.
- Alert minimums: service unavailable, elevated 5xx, queue depth, provider quota exhaustion, backup failure, restore failure, and credential misuse.

## Backup and retention

- Local/staging backup: authenticated `/backup/export` and `/backup/restore` for agent-provider state.
- Backup artifacts must be encrypted outside the service and stored in operator-approved object storage.
- Default staging retention recommendation: application logs 30 days, audit events 365 days, ephemeral workspace metadata 30 days after completion, backups 35 days.
- Production retention requires legal/privacy approval and supersedes these defaults.

## Upstream AI provider and model policy

- Verified staging provider: Hugging Face Router using the OpenAI-compatible API.
- Verified staging model: `Qwen/Qwen2.5-Coder-32B-Instruct`.
- Production model use requires an explicit allowlist, data-processing review, regional/privacy approval, quota monitoring, timeout limits, and tested fallback behavior.
- Browser clients may reference model aliases only; provider tokens remain exclusively in AI Gateway.

## Billing decisions

- Billing Ledger records usage and invoice intents but has no wallet, card, KYC, MPC, signing, or swap authority.
- Currency, merchant jurisdiction, tax treatment, invoice rules, and payment processor are operator/business decisions and must be documented before enabling chargeable production traffic.
- Until those values are approved, invoice intents remain `requires_payment_processor` and no payment execution is authorized.

## Production sign-off

Production traffic remains disabled until the issue checklist contains evidence for CI, SBOM, provenance, backups/restores, observability, security boundaries, reviewer identity, approving operator, rollback SHA, incident owner, and watch window.

## Environment bootstrap

- `scripts/configure-github-environments.sh` is the supported repository-local helper for creating or updating `ci`, `staging`, and `production`.
- The helper requires explicit `user:LOGIN` or `team:SLUG` reviewer selectors and fails closed if they are omitted.
- The helper updates environment protection rules and branch policies and imports populated keys from the loaded env overlays into the relevant GitHub environment variables and secrets; it does not invent values or reviewers.
- The protected staging decision record, `scripts/staging-decision-record.json`, is the canonical machine-readable source for the approved identity-provider and claim-mapping decision used by the external staging workflow, and `schemas/operations/staging-decision-record.schema.json` captures the expected contract for repository-local validation.
