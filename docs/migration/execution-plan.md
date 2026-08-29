# Z Platform Execution Plan

## Objective

Create a clean, secure platform successor to `https://github.com/cvsz/z-platform` without bulk-copying legacy architecture, secrets, deployment identifiers, or unsafe financial capabilities.

## Operating rules

- Preserve the legacy repository as the migration source of record.
- Every migration is independently buildable, testable, reversible, and documented.
- Provider credentials remain server-side.
- AI agents never receive wallet signing, card data, MPC shares, or production infrastructure authority.
- Infrastructure plans may be generated, but deployment requires explicit operator approval.

## Phase 1 — AI foundation

### Completed

- ZAI Coder Python runtime primitives: streaming render gate, secure MCP payload builder, model preflight.
- Gateway-backed CLI.
- Browser terminal, server-side gateway proxy, response streaming, and file upload proxy.
- AI Gateway service skeleton with service-token authentication and upstream isolation.
- AI Gateway request IDs, structured error codes, redacted audit events, and cancellation propagation.
- Generic OpenAI-compatible attachment reference translation for platform file references.
- Shared AI contracts.
- ZAI Coder web file-backed workspace metadata boundary with owner fields, retention timestamps, and uploaded-file links.
- AI Gateway attachment adapter registry with OpenAI-compatible and Anthropic message-shape translators plus unit coverage.
- AI Gateway upstream provider selection wired into chat attachment translation.
- Hugging Face free/local model catalog exposed through the AI Gateway model list endpoint.
- AI Gateway upload adapter registry with OpenAI-compatible binary/content pass-through, safe filename normalization, and unsupported-provider failure handling.
- ZAI Coder web workspace metadata adapter boundary with tenant owner enforcement and explicit retention cleanup hooks.
- ZAI Coder web scheduled workspace cleanup runner with structured cleanup output.
- ZAI Coder web production workspace metadata adapter with HTTP durable metadata service wiring.
- Repository-local test workflows for Node and Python runtimes covering gateway-only ZAI Coder paths, model catalog, provider adapters, workspace metadata, uploads, streaming, and failure paths.
- Eligible CI, dependency, secret-scan, SBOM, provenance, and deployed smoke evidence recorded for the Phase 6 verification commits.

### Remaining

- Record a new workflow result when a newer `main` head is selected as a release candidate; evidence from an earlier immutable commit must not be silently transferred to a later commit.

**Done when:** ZAI Coder web and CLI use only the gateway; browser clients never receive provider secrets; tests cover chat, streaming, file upload, workspace metadata, model catalog, provider attachment adapters, and failure paths.

## Phase 2 — Agent orchestration

### Completed

- Defined `agent.job.requested.v1`, `agent.job.approved.v1`, and `agent.job.completed.v1` contracts with JSON schemas and validation tests.
- Implemented the agent orchestrator job-store, queue, approval, sandbox worker, cancellation, retry, and audit adapter boundaries with lifecycle tests.
- Added operator-approved production provider adapters for job storage, queueing, observability audit export, identity approval checks, and sandbox execution before external traffic.
- Verified durable provider persistence, cancellation, deterministic failure, retry, and completed audit evidence in isolated Compose.

### Remaining

- Verify managed production provider endpoints, external identity mapping, and selected staging infrastructure before setting `AGENT_EXTERNAL_TRAFFIC_ENABLED=true`.

**Done when:** an agent job can be submitted, approved, executed with scoped tools, cancelled, retried idempotently, and audited.

## Phase 3 — ZChat migration

### Completed

- Imported only the thin presentation and conversation-state layers into the platform-owned ZChat shell.
- Replaced direct model/provider configuration with the AI Gateway model catalog.
- Added tenant scope headers, shared conversation IDs, request IDs, and usage correlation.
- Added streaming proxy support, logout/session-expiry handling, and accessible responsive UI structure with test coverage.
- Added automated deployed static checks for semantic labels, live regions, responsive CSS, and logout storage clearing.

### Remaining

- Run human keyboard-only, screen-reader, target-device responsive, and external session-provider QA after the operator selects the platform identity provider.

**Done when:** ZChat works against the platform gateway and no browser configuration can contain an upstream key.

## Phase 4 — Generator and workspace migration

### Completed

- Moved audited generator/template boundaries into `tools/zai-factory` with a safe node-service template.
- Defined template manifests, validation, and generated-file ownership checks.
- Split ZOW into a user-facing workspace UI/proxy and isolated `services/workspace-runtime` execution boundary.
- Prohibited generated deployments and shell execution unless an explicit approval policy grants `deploy` or `shell`.

### Remaining

- Run operator review of additional legacy templates before adding them to `tools/zai-factory/templates`.

**Done when:** a generator produces a validated project in a sandbox with reproducible output and no secret-bearing files.

## Phase 5 — Usage and billing boundary

### Completed

- Added immutable `ai.usage.recorded.v1` usage contract and server-side AI Gateway emission.
- Added idempotent usage recording before ledger entries are accepted.
- Implemented credits and invoice intents in `services/billing-ledger`.
- Integrated `apps/zwallet` only through audited billing-ledger adapters.
- Blocked wallet signing, swaps, cards, KYC, MPC shares, and payment-provider credentials from the AI request path and ZWallet adapter boundary.
- Verified deployed Billing Ledger idempotency and ZWallet prohibited-capability rejection contracts in isolated Compose.

### Remaining

- Operator selection of billing currency, tax rules, payment processor, merchant-of-record responsibilities, and jurisdiction before production payment collection.

**Done when:** usage can be reconciled to an idempotent ledger record without access to signing authority or payment-card data.

## Phase 6 — Platform operations

### Completed

- Added CI coverage for migrated Node and Python runtimes, dependency policy checks, secret scanning, and service-specific test gates.
- Added SBOM generation and provenance verification workflow artifacts.
- Defined Cloudflare Access service-to-service policy requirements.
- Added health, structured logging, metrics, trace, backup, restore, and incident runbooks.
- Added staging readiness review checklist before any production deployment.
- Deployed and verified the seven-service isolated Compose readiness topology.
- Verified durable Agent Provider state, backup/restore, restart persistence, retention cleanup, lifecycle cancellation, failure, retry, and audit evidence.
- Verified Workspace Runtime approval boundaries, Billing Ledger idempotency, ZWallet denial paths, and automated ZChat static QA.
- Recorded eligible workflow runs, SBOMs, provenance, smoke artifacts, rollback candidates, and repository-controlled execution evidence.
- Added `docs/operations/phase-6-evidence-matrix.md` to separate repository, Compose, external staging, and production-approval evidence.
- Added a dotenv-backed GitHub environment helper that imports `STAGING_REVIEWER`, `INCIDENT_OWNER`, `ESCALATION_ROUTE`, `WATCH_WINDOW`, and production review selectors from the loaded overlays into the environment bootstrap path.
- Implemented Full-Stack Agent Control Panel for provider API key management and rotation.
- Verified AI multi-provider routing, fallback quotas, and failover using Redis pool limits.
- Implemented Cloudflare edge routing and identity proxy configuration; real external account and policy evidence remains **PENDING_EXTERNAL**.
- Implemented AI streaming, upload/file proxy, multi-provider, and failover verification harnesses; approved-account execution remains **PENDING_EXTERNAL**.
- Implemented a read-only Supabase Data API bridge in `services/phase6-api` with authenticated access, env-based URL/anon-key/table selection, and deterministic success/failure coverage; real Supabase project evidence remains **PENDING_EXTERNAL**.
- Implemented browser bundle and HAR credential scanners; actual deployed artifacts remain **PENDING_EXTERNAL**.
- Implemented automated ZChat accessibility, responsive, session, and external-readiness contracts; human target-environment QA remains **PENDING_EXTERNAL**.
- Implemented a CodeQL Advanced workflow that runs on the available self-hosted Linux/X64 lane with the broader `security-and-quality` query suite and explicit language toolchain setup, plus repository-local drift tests for the workflow shape and setup ordering.
- Removed tracked Cloudflare Terraform state, backup state, and committed `terraform.tfvars`, and added stack-local ignore rules so future state files stay out of the repository.
- Added a machine-readable Phase 6 operator-input register at `scripts/phase-6-operator-inputs.json` so the remaining operator-owned items are tracked as a validated pending contract instead of loose prose.

### Remaining

- Record billing/legal decisions, staging reviewer, production approver, incident owner, escalation route, and post-launch watch window.
- Record the remaining operator-owned values in `scripts/phase-6-operator-inputs.json` and keep that register fail-closed until an authorized operator supplies the real values.
- Record a passing workflow and immutable artifacts for the exact commit selected as the next release candidate.
- Record verified Supabase project/table evidence for the exact release candidate after the read-only bridge is exercised against an approved external project.
- Run CodeQL Advanced on the available self-hosted runner for the exact selected SHA and capture the alert-closure evidence before promoting any new release candidate.
- **VERIFIED** - Current `main` SHA `36fc7f594c933137a1d8da2855bac752fb2f03b3` has passing CI, secret and browser scans, Compose build, deployed smoke, SBOM, provenance, and CodeQL workflows. `validate` run `29431079935` produced smoke artifact `8349399112` with digest `sha256:68526290de0f0325123e58e0adfe68246ecf57d617fbd207eff1e568a6bd6495`.
- **IMPLEMENTED** - AI Gateway disconnect-aware upstream cancellation exists on this branch. PR-head validation and immutable artifact evidence are still required before the branch can be selected as a release candidate.

**Done when:** every service has health checks, least-privilege identity, observability, rollback notes, a passing CI gate for the selected release, completed external staging evidence, and explicit production approval.

## Required operator decisions

- Identity provider and tenant claim model.
- Queue, database, object-storage vendors, regions, and retention periods.
- Approved upstream AI providers, model allowlist, quota, failover, privacy, residency, and data-governance policy.
- Billing currency, tax, payment processor, merchant responsibilities, and jurisdiction requirements.
- Cloudflare environment, domain routing, and production secret-management location.
- Observability platform, alert routing, external backup target, incident ownership, and watch window.
- Production deployment approval for the exact release in each environment.
- The operator-input register in `scripts/phase-6-operator-inputs.json` must stay aligned with those decisions without exposing real production identifiers.

## Validation gate for every pull request

1. Scope matches a single migration item.
2. No credentials or real production identifiers.
3. Unit tests and lint pass for changed runtime.
4. Input validation, authorization, timeout, and failure paths are tested.
5. Migration manifest, evidence matrix, and runbook are updated when readiness evidence changes.
6. Financial, infrastructure, destructive, external-traffic, or production changes have explicit operator approval.
7. Evidence is tied to an immutable commit or image digest and is not transferred to a newer release without verification.
