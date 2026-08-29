# Z Platform Master Requirements

This document is the complete requirements baseline for `z-platform`. It combines product, architecture, security, migration, GitHub, CI, production, observability, billing, agent, workspace, and operational requirements into one auditable reference.

## Scope

`z-platform` is a clean, security-first successor platform extracted incrementally from `cvsz/zeaz-platform`. The legacy repository remains the source of migration reference, but this repository is the production system of record.

The platform includes:

- AI coding and chat surfaces.
- AI Gateway provider isolation.
- Agent orchestration with approval, sandboxing, retry, cancellation, and audit.
- Workspace generation and runtime execution boundaries.
- ZChat gateway-only messaging.
- ZOW workspace UI/proxy.
- ZWallet billing-ledger adapter only.
- Usage and billing ledger boundary.
- Shared contracts and event schemas.
- CI, security, SBOM, provenance, and operations gates.

## Requirement language

| Word | Meaning |
|---|---|
| MUST | Required before merge or production use |
| MUST NOT | Prohibited behavior |
| SHOULD | Expected unless an operator-approved exception exists |
| MAY | Optional behavior |
| OPERATOR APPROVAL | Explicit human approval recorded outside automated agent execution |

## System objectives

| ID | Requirement | Acceptance criteria |
|---|---|---|
| OBJ-001 | The platform MUST isolate browser clients from provider secrets. | Browser code and API responses contain no upstream provider keys, service tokens, payment secrets, wallet keys, or infrastructure credentials. |
| OBJ-002 | The platform MUST route AI provider access through the AI Gateway. | ZAI Coder, ZChat, and related clients use gateway endpoints only. |
| OBJ-003 | The platform MUST use least-privilege service boundaries. | Each app or service has documented ownership, trusted callers, and denied capabilities. |
| OBJ-004 | The platform MUST be independently buildable and testable. | Repository-local CI covers migrated runtimes and fails on missing package tests. |
| OBJ-005 | The platform MUST keep unsafe financial and wallet capabilities outside AI paths. | Signing, cards, KYC, MPC, and swap payloads are denied by ZWallet and billing boundaries. |

## Repository and GitHub requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| GH-001 | The default branch MUST remain protected by CI policy. | Required workflows are enabled before production. |
| GH-002 | Pull requests SHOULD map to a single migration or operational item. | PR description references the relevant manifest item, runbook, or requirement ID. |
| GH-003 | Commits MUST NOT include credentials, production identifiers, API keys, wallet keys, MPC shares, card data, or KYC payloads. | Secret scanning passes and review confirms no sensitive material. |
| GH-004 | GitHub Actions MUST run repository-local tests for migrated runtimes. | CI covers Node and Python packages listed in migration docs. |
| GH-005 | GitHub Actions MUST produce dependency, SBOM, and provenance signals before production release. | Operations workflow runs dependency check, SBOM generation, and provenance verification. |
| GH-006 | Documentation changes MUST accompany behavior changes that affect operations, security, billing, or migration state. | Related docs are updated in the same PR or commit series. |
| GH-007 | Release commits MUST be traceable. | Production records identify commit SHA, workflow result, artifact set, and rollback SHA. |

## Architecture requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| ARCH-001 | User-facing applications MUST stay in `apps/*`. | Product UI code lives under app directories and calls services through approved APIs. |
| ARCH-002 | Deployable service boundaries MUST stay in `services/*`. | Runtime APIs and workers have explicit package boundaries. |
| ARCH-003 | Shared schemas MUST stay in `packages/contracts`. | Versioned contracts include tests and are not duplicated ad hoc. |
| ARCH-004 | Infrastructure plans MAY be generated but MUST require operator approval to apply. | No automated agent can deploy production infrastructure without approval. |
| ARCH-005 | Service boundaries MUST deny capabilities outside their responsibility. | Deny rules are tested or documented per service. |

## AI Gateway requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| AI-001 | The AI Gateway MUST be the only production holder of upstream AI provider credentials. | Clients and apps send requests to the gateway only. |
| AI-002 | The gateway MUST enforce service-token authentication. | Unauthorized requests fail with structured errors. |
| AI-003 | The gateway MUST expose a model catalog. | Clients load available models from gateway metadata, not browser config. |
| AI-004 | The gateway MUST translate provider-specific attachment and upload formats through adapters. | OpenAI-compatible paths are supported and unsupported provider paths fail safely. |
| AI-005 | The gateway MUST emit usage records server-side. | `ai.usage.recorded.v1` events are generated with idempotency keys. |
| AI-006 | The gateway MUST redact secrets and unsafe payloads from logs and traces. | Audit and trace outputs contain no credentials, card data, wallet signatures, KYC payloads, or MPC shares. |

## ZAI Coder requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| ZAI-001 | ZAI Coder web MUST use server-side gateway proxies. | Browser requests never target upstream providers directly. |
| ZAI-002 | ZAI Coder CLI MUST use the gateway-backed client. | CLI configuration does not require browser-visible provider secrets. |
| ZAI-003 | Streaming responses MUST be proxied through the gateway boundary. | SSE or streaming tests cover delta forwarding and failure paths. |
| ZAI-004 | File upload MUST be proxied through the platform gateway. | Upload tests cover safe filenames, unsupported providers, and failure paths. |
| ZAI-005 | Workspace metadata MUST use an adapter boundary. | Local and production metadata adapters enforce tenant ownership and retention. |

## ZChat requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| CHAT-001 | ZChat MUST be a thin UI and server-side gateway proxy. | Browser configuration cannot include upstream provider keys. |
| CHAT-002 | ZChat MUST load models from the AI Gateway. | Model catalog requests are gateway-only. |
| CHAT-003 | ZChat MUST propagate tenant, conversation, request, and usage-correlation IDs. | Tests verify headers or metadata forwarding. |
| CHAT-004 | ZChat MUST handle session expiry and logout. | UI and proxy tests cover session failure states. |
| CHAT-005 | ZChat MUST support streaming through the gateway. | Streaming proxy tests cover success and error paths. |

## Agent orchestration requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| AGENT-001 | Agent jobs MUST be durable. | Job state persists through a job-store adapter. |
| AGENT-002 | Agent execution MUST be queue-backed. | Approved work is enqueued through a replaceable queue adapter. |
| AGENT-003 | Mutating jobs MUST require explicit approval state. | Jobs without approval cannot execute mutating tools. |
| AGENT-004 | Tools MUST be scoped by explicit grants. | Tool grant checks deny missing or out-of-scope tools. |
| AGENT-005 | Workers MUST run in a sandbox with resource limits. | Sandbox adapter controls time, memory, filesystem, network, and tool access. |
| AGENT-006 | Jobs MUST support cancellation. | Cancelled jobs reach a terminal cancelled state without unsafe side effects. |
| AGENT-007 | Jobs MUST support idempotent retry. | Retry preserves job identity or idempotency key and avoids duplicate side effects. |
| AGENT-008 | Agent lifecycle events MUST be audited. | Requested, approved, completed, failed, cancelled, and retried states emit audit events. |
| AGENT-009 | External traffic MUST wait for production adapters. | DB, queue, observability, identity, and sandbox providers are operator-approved before enablement. |

## Generator and workspace requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| WORK-001 | Generators MUST use audited templates only. | Template manifests declare ownership, allowed files, and validation rules. |
| WORK-002 | Generated output MUST be reproducible and validated. | Generator tests compare expected output and reject unsafe paths. |
| WORK-003 | Generated files MUST NOT include secret-bearing paths or values. | Validation rejects environment secrets, credentials, and production identifiers. |
| WORK-004 | ZOW MUST remain a UI/proxy surface. | Shell and deploy execution live in `services/workspace-runtime`. |
| WORK-005 | Workspace shell MUST require explicit approval. | Requests without `shell` grant are denied. |
| WORK-006 | Workspace deploy MUST require explicit approval. | Requests without `deploy` grant are denied. |
| WORK-007 | Runtime execution MUST be sandboxed. | Runtime provider enforces filesystem, process, time, and network boundaries. |

## Billing and ZWallet requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| BILL-001 | Usage records MUST be immutable and idempotent. | Duplicate idempotency keys are rejected or returned as duplicates without double-charge. |
| BILL-002 | Billing Ledger MUST own credits and invoice intents. | Credits and invoices are recorded through ledger APIs only. |
| BILL-003 | ZWallet MUST integrate only through audited billing-ledger adapters. | ZWallet adapter forwards only credits and invoice intents. |
| BILL-004 | ZWallet MUST reject signing, card, KYC, MPC, and swap payloads. | Tests cover each denied capability. |
| BILL-005 | Production payment collection MUST wait for operator decisions. | Currency, tax rules, payment processor, and jurisdiction are approved before launch. |
| BILL-006 | Billing logs MUST exclude card data and payment credentials. | Observability outputs contain no prohibited payment data. |

## Identity and access requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| IAM-001 | Production MUST use an operator-approved identity provider. | Tenant claim mapping is documented and tested. |
| IAM-002 | Service-to-service calls MUST use scoped service tokens. | Cloudflare Access or equivalent policies map caller to target. |
| IAM-003 | Browser clients MUST NOT access service tokens. | Tokens are stored only server-side in approved secret storage. |
| IAM-004 | Tenant boundaries MUST be enforced server-side. | Tenant IDs are validated before data access or execution. |
| IAM-005 | Break-glass access MUST be documented. | Operator owner, rotation steps, and audit requirements are recorded. |

## Data, privacy, and retention requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| DATA-001 | Workspace metadata MUST have owner, retention, and cleanup semantics. | Metadata adapter includes owner fields, retention timestamps, and cleanup hooks. |
| DATA-002 | Audit events MUST be retained in an approved pipeline. | Retention policy is documented before production. |
| DATA-003 | Prompts and raw provider payloads SHOULD NOT be stored in traces. | Trace attributes use correlation IDs and redacted metadata. |
| DATA-004 | Backups MUST exclude provider credentials, wallet signing keys, MPC shares, card data, and payment secrets. | Backup scope documents approved stores only. |
| DATA-005 | Restore MUST be tested in staging before production promotion. | Restore checklist includes integrity and idempotency checks. |

## Observability requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| OBS-001 | Every deployed service MUST provide a health signal or CI gate. | Health endpoints or package tests are documented. |
| OBS-002 | Logs MUST be structured JSON. | Logs include `ts`, `service`, `event`, `request_id`, optional `tenant_id`, `status`, and redacted error code. |
| OBS-003 | Metrics MUST cover request count, latency, upstream failures, usage ledger states, approval denials, and agent terminal states. | Dashboards or metric queries exist before production. |
| OBS-004 | Traces MUST propagate request, tenant, conversation, and usage-correlation IDs. | Cross-service calls preserve correlation identifiers. |
| OBS-005 | Alerts MUST exist for critical safety failures. | Alerts cover credential exposure, unauthorized execution, billing idempotency failure, failed protected CI, and health degradation. |

## CI, security, and supply-chain requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| CI-001 | CI MUST run repository-local Node tests. | Migrated Node workspaces are tested by GitHub Actions. |
| CI-002 | CI MUST run repository-local Python tests. | ZAI Coder backend tests run in GitHub Actions. |
| CI-003 | Validation MUST fail when package test scripts are missing. | Validate workflow checks expected workspaces. |
| CI-004 | Secret scanning MUST run in CI. | Secret scan step passes before production. |
| CI-005 | Dependency policy MUST reject forbidden packages. | `tools/ops/check-dependencies.mjs` exits nonzero on forbidden dependency use. |
| CI-006 | SBOM generation MUST run in CI. | `tools/ops/generate-sbom.mjs` produces SPDX JSON artifact. |
| CI-007 | Provenance verification MUST run in CI. | `tools/ops/verify-provenance.mjs` validates the SBOM artifact. |

## Production requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| PROD-001 | Production deployment MUST be blocked until staging readiness is complete. | Staging readiness checklist is signed off by the operator. |
| PROD-002 | Production MUST have rollback notes. | Rollback SHA, service version, data migration status, and verification commands are recorded. |
| PROD-003 | Production traffic MUST remain gated until health, logs, metrics, traces, and alerts are visible. | Operator confirms visibility before external traffic. |
| PROD-004 | Production provider endpoints MUST be verified in staging. | AI, database, queue, observability, identity, billing, backup, and sandbox providers pass smoke tests. |
| PROD-005 | Production launch MUST have an incident owner and escalation path. | Incident commander, on-call, and communication channel are assigned. |

## Migration requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| MIG-001 | The legacy repository MUST remain unchanged as the source of migration reference. | Migration commits target `z-platform` only unless explicitly requested. |
| MIG-002 | Legacy code MUST NOT be bulk-copied without review. | Each migration item records source, target, selection rule, tests, and rollback plan. |
| MIG-003 | Migration status MUST be tracked in the manifest. | Items are marked pending, partial, or complete with definitions. |
| MIG-004 | Migration phases MUST remain independently testable and reversible. | Each phase includes done criteria and validation gates. |
| MIG-005 | Operator decisions MUST be explicit. | Identity, queues, databases, billing, Cloudflare, AI providers, and production deployments are recorded. |

## Documentation requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| DOC-001 | Architecture documentation MUST define domain ownership and trust boundaries. | `docs/architecture/README.md` stays current. |
| DOC-002 | Execution plan MUST describe completed and remaining migration work. | `docs/migration/execution-plan.md` stays current. |
| DOC-003 | Migration manifest MUST track candidate migrations and statuses. | `docs/migration/manifest.md` stays current. |
| DOC-004 | Production operations MUST be documented. | `docs/operations/production-master.md` and runbooks stay current. |
| DOC-005 | Requirements MUST be traceable. | Changes reference requirement IDs when feasible. |

## Acceptance matrix

| Area | Required evidence |
|---|---|
| Gateway-only AI | ZAI Coder, ZChat, and CLI tests plus gateway config review |
| Provider secrecy | Secret scan, browser bundle/config review, redacted logs |
| Agent lifecycle | Submit, approve, execute, cancel, retry, audit tests |
| Workspace runtime | Generate, validate, shell-deny, deploy-deny, approval-allow tests |
| Billing boundary | Usage idempotency, credit, invoice, and forbidden ZWallet payload tests |
| Production readiness | CI, SBOM, provenance, staging readiness, rollback, incident owner |
| Observability | Health, logs, metrics, traces, alerts visible in staging |
| Backup recovery | Staging restore test with integrity and idempotency checks |

## Linked source documents

- [Architecture](../architecture/README.md)
- [Execution plan](../migration/execution-plan.md)
- [Migration manifest](../migration/manifest.md)
- [Production master document](../operations/production-master.md)
- [Operations index](../operations/README.md)
- [Cloudflare Access policies](../operations/cloudflare-access.md)
- [Observability and health](../operations/observability.md)
- [Backup and restore runbook](../operations/backups.md)
- [Incident runbook](../operations/incident-runbook.md)
- [Staging readiness review](../operations/staging-readiness.md)
