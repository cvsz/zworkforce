# Z Platform Project Overview

This document explains the project shape of `z-platform`: why it exists, what it contains, how work is organized, and how delivery decisions connect to the architecture, requirements, migration plan, and production readiness documents.

## Project purpose

`z-platform` is a clean, security-first platform foundation extracted incrementally from `cvsz/zeaz-platform`. It preserves the useful product direction of the legacy platform while replacing direct provider access, unsafe financial surfaces, in-memory migration-only adapters, and unapproved execution paths with explicit platform boundaries.

The project exists to provide:

- Gateway-first AI access for coding and chat products.
- Durable, auditable agent orchestration.
- Sandboxed workspace generation and execution.
- Idempotent usage and billing boundaries.
- Production-grade operational controls before external traffic.
- A repository structure that can be tested, reviewed, and released safely.

## Project principles

| Principle | Meaning |
|---|---|
| Security first | No browser-visible provider secrets, wallet keys, payment secrets, MPC shares, KYC payloads, or production infrastructure credentials. |
| Gateway first | AI provider access flows through the AI Gateway, not directly from browser clients. |
| Explicit approval | Mutating agent tools, shell execution, deployment, infrastructure, and production rollout require approval gates. |
| Durable state | Jobs, usage records, audit events, workspace metadata, and billing state must survive process restarts. |
| Incremental migration | Legacy code is selected, reviewed, tested, and documented one boundary at a time. |
| Production blocking | External traffic waits for CI, observability, backups, identity, Cloudflare Access, and operator sign-off. |

## Current project scope

| Area | Repository location | Scope |
|---|---|---|
| ZAI Coder Web | `apps/zaicoder/web` | Browser coding UI, gateway proxy, streaming, upload proxy, workspace metadata adapter. |
| ZAI Coder Backend/CLI | `apps/zaicoder/backend` | CLI and local runtime helpers that use the platform gateway. |
| AI Gateway | `services/ai-gateway` | Provider routing, service-token auth, model catalog, upload/attachment adapters, usage event emission. |
| ZChat | `apps/zchat` | Thin chat UI and server-side gateway proxy. |
| Agent Orchestrator | `services/agent-orchestrator` | Durable jobs, approval state, queue adapters, sandbox worker, cancellation, retry, audit export. |
| ZAI Factory | `tools/zai-factory` | Audited templates, project generation, validation, generated-file ownership. |
| Workspace Runtime | `services/workspace-runtime` | Isolated validation, shell, and deployment boundary with approval grants. |
| ZOW | `apps/zow` | Workspace user interface and proxy only. |
| Billing Ledger | `services/billing-ledger` | Idempotent usage ledger, credits, invoice intents. |
| ZWallet | `apps/zwallet` | Billing-ledger adapter surface only; unsafe wallet/payment paths denied. |
| Contracts | `packages/contracts` | Versioned schemas for API and event boundaries. |
| Operations | `.github/workflows`, `tools/ops`, `docs/operations` | CI, validation, secret scanning, dependency policy, SBOM, provenance, runbooks, readiness gates. |

## Out of scope unless separately approved

- Direct browser access to upstream AI providers.
- Browser-visible provider API keys or service tokens.
- Wallet signing, swaps, card processing, KYC capture, MPC key handling, or payment credential custody.
- Production infrastructure apply from an automated agent without operator approval.
- External production traffic before staging readiness is complete.
- Bulk-copying legacy applications without dependency inventory, tests, security review, and rollback notes.

## Delivery model

Work moves through the project in small migration or operations increments:

1. Identify the source boundary in `cvsz/zeaz-platform` or a new platform requirement.
2. Define target ownership in `apps`, `services`, `packages`, `tools`, `infra`, or `docs`.
3. Implement the smallest independently testable slice.
4. Add or update tests for success, failure, authorization, timeout, and denial paths.
5. Update requirements, migration manifest, execution plan, and runbooks when behavior changes.
6. Run CI, validation, secret scanning, dependency policy, SBOM, and provenance gates.
7. Promote only after staging readiness and operator approval when production is affected.

## Milestone map

| Phase | Theme | Status | Primary evidence |
|---|---|---|---|
| Phase 0 | Foundation | complete | Repository layout, baseline policies, architecture docs. |
| Phase 1 | AI foundation | complete | Gateway-backed ZAI Coder web/CLI, model catalog, uploads, workspace metadata, CI. |
| Phase 2 | Agent orchestration | complete | Durable jobs, queue, approvals, sandbox runtime, audit, production adapter boundaries. |
| Phase 3 | ZChat migration | complete | Gateway-only ZChat, streaming, session handling, correlation IDs. |
| Phase 4 | Generator and workspace migration | complete | ZAI Factory templates, generated-file validation, ZOW/runtime split, shell/deploy approval. |
| Phase 5 | Usage and billing boundary | complete | Usage events, idempotent ledger, credits, invoice intents, ZWallet denial boundary. |
| Phase 6 | Platform operations | complete | CI expansion, operations workflow, SBOM, provenance, Cloudflare/observability/backups/incidents/readiness docs. |

## Ownership model

| Owner type | Responsibility |
|---|---|
| Product owner | Confirms product scope, UX acceptance, tenant model, and launch priorities. |
| Platform owner | Maintains service boundaries, contracts, gateway policy, and runtime architecture. |
| Security owner | Reviews secrets, access control, approval gates, financial exclusions, and incident readiness. |
| Operations owner | Owns CI gates, Cloudflare Access, observability, backups, readiness review, and release approval. |
| Billing owner | Approves currency, tax, payment processor, invoice policy, and jurisdiction requirements. |
| Operator | Approves production providers, infrastructure changes, deployment, rollback, and external traffic. |

Until real owners are assigned, production remains blocked by the production master document and staging readiness review.

## GitHub workflow expectations

- Work should land in small, reviewable commits or pull requests.
- Each PR should reference the relevant requirement, migration item, or runbook.
- GitHub Actions should run repository-local tests for migrated Node and Python runtimes.
- Validation should reject missing package test scripts in migrated workspaces.
- Secret scanning, dependency policy, SBOM generation, and provenance verification should pass before production release.
- Release records should include commit SHA, workflow result, artifact set, rollback SHA, and operator approval.

## Project risks

| Risk | Mitigation |
|---|---|
| Provider secret exposure | Gateway-only access, secret scanning, browser config review, redacted logs. |
| Unsafe financial capability leakage | ZWallet adapter denial tests and billing-ledger-only integration. |
| Agent side effects without approval | Explicit approval state, scoped tool grants, sandbox runtime, audit events. |
| Workspace execution escape | Runtime isolation, approval grants, resource limits, denied secret-bearing paths. |
| Duplicate billing | Usage idempotency keys and ledger duplicate handling. |
| Production launch without operations visibility | Staging readiness review, health checks, logs, metrics, traces, alerts. |
| Irreversible migration | Manifest tracking, rollback notes, phase-level done criteria. |

## Success criteria

The project is ready for production consideration when:

- Requirements are traceable and current.
- All migrated apps and services pass repository-local tests.
- Browser clients cannot receive provider secrets or service credentials.
- Agent jobs can be submitted, approved, executed with scoped tools, cancelled, retried idempotently, and audited.
- Workspace generation is reproducible and rejects unsafe files.
- Usage is reconciled through the billing ledger without wallet/card/KYC/MPC/swap access.
- CI, validation, secret scanning, dependency policy, SBOM, and provenance gates pass.
- Staging readiness is signed off by the operator.
- Rollback, incident, backup, and restore paths are documented and tested.

## Canonical project documents

- [Master requirements](../requirements/master-requirements.md)
- [Production master document](../operations/production-master.md)
- [Execution plan](../migration/execution-plan.md)
- [Migration manifest](../migration/manifest.md)
- [Architecture](../architecture/README.md)
- [Operations index](../operations/README.md)
- [Staging readiness review](../operations/staging-readiness.md)
