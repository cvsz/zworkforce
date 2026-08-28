# Production Master Document

This document is the production control plane for `z-platform`. It consolidates the architecture, migration gates, operational runbooks, and go-live requirements that must be satisfied before any external production traffic is enabled.

## Production objective

Run `z-platform` as a least-privilege, auditable, gateway-first platform where browser clients never receive provider secrets, agent and workspace execution require explicit approval grants, billing is reconciled through an idempotent ledger, and operational recovery is documented before launch.

## Non-negotiable boundaries

- Provider credentials stay server-side in the AI Gateway or approved secret manager.
- Browser clients never receive upstream provider keys, service tokens, payment credentials, wallet keys, MPC shares, KYC payloads, card data, or production infrastructure credentials.
- Agent jobs require durable job storage, queue-backed execution, explicit approval state, scoped tool grants, sandbox resource limits, cancellation, retry idempotency, and audit export.
- Workspace shell and deployment actions require explicit `shell` or `deploy` approval grants.
- Billing accepts usage events, credits, and invoice intents only. It never receives signing authority, card data, KYC payloads, MPC shares, or swap routes.
- Production deployment requires operator approval for every environment.

## Production service map

| Domain | Runtime | Production responsibility | Required gate |
|---|---|---|---|
| ZAI Coder Web | `apps/zaicoder/web` | Browser UI, gateway-only chat/upload/workspace metadata proxy | CI, gateway secret isolation, workspace metadata adapter |
| ZAI Coder CLI | `apps/zaicoder/backend` | Gateway-backed CLI and local runtime helpers | CI, no direct provider secret leakage |
| AI Gateway | `services/ai-gateway` | Provider routing, model catalog, upload/attachment adapters, usage emission | Service token auth, provider allowlist, observability |
| ZChat | `apps/zchat` | Thin chat UI and server-side gateway proxy | Gateway-only model catalog, session QA |
| Agent Orchestrator | `services/agent-orchestrator` | Durable jobs, approvals, scoped tools, sandbox execution, audits | Production DB/queue/identity/sandbox adapters |
| Workspace Runtime | `services/workspace-runtime` | Generated project validation, shell/deploy approval boundary | Sandbox runtime, approval policy, health checks |
| ZOW | `apps/zow` | Workspace UI/proxy only | Runtime-only execution path |
| Billing Ledger | `services/billing-ledger` | Idempotent usage ledger, credits, invoice intents | Durable ledger, duplicate protection, audit logs |
| ZWallet Adapter | `apps/zwallet` | Billing-ledger UI/adapter surface | Reject signing, cards, KYC, MPC, swaps |
| Contracts | `packages/contracts` | Versioned API and event schemas | Schema tests and compatibility review |

## Environment model

| Environment | Purpose | Traffic | Promotion requirement |
|---|---|---|---|
| Local | Developer validation | none | Unit tests and secret scan only |
| CI | Pull request and main validation | none | All required workflows pass |
| Staging | Production-equivalent verification | internal/operator only | Staging readiness review signed off |
| Production | External traffic | public or tenant-scoped | Operator approval, rollback plan, incident owner |

Production must not be the first environment to exercise a provider, queue, database, identity policy, sandbox profile, billing integration, Cloudflare rule, or restore path.

## k3s CNI migration

The repository includes a fail-closed Cilium migration preflight and installer
under `scripts/cilium-migration-preflight.sh` and
`scripts/install-cilium-k3s.sh`. The installer requires a pinned
`CILIUM_CHART_VERSION` and the explicit maintenance acknowledgment
`CILIUM_MAINTENANCE_ACK=I_HAVE_APPROVED_CNI_MIGRATION`; it will not install over
an active Flannel daemonset. Confirm a tested rollback plan before execution.
The currently verified chart pin is documented in
`infrastructure/kubernetes/cilium/version.env.example`.
The corresponding k3s settings are staged in
`infrastructure/kubernetes/cilium/k3s-config-migration.yaml.example`; they
must be merged with the existing config and followed by a controlled k3s
restart, never applied as an unreviewed overwrite.

## Required production providers

| Capability | Required production provider decision |
|---|---|
| Identity and tenant claims | Operator-selected identity provider and tenant claim mapping |
| Service access | Cloudflare Access account, zone, team domain, service-token rotation policy |
| Secrets | Approved secret manager, rotation schedule, break-glass owner |
| AI providers | Approved provider/model allowlist and quota policy |
| Workspace metadata | Durable metadata database or service |
| Agent jobs | Durable database plus queue and dead-letter queue |
| Agent sandbox | Resource-limited sandbox runtime with network/file/tool scope controls |
| Observability | Logs, metrics, traces, dashboards, alert routing |
| Audit events | Durable audit/event pipeline with retention policy |
| Billing | Currency, tax rules, payment processor, invoice policy, jurisdiction review |
| Backups | Backup provider, retention policy, restore test schedule |

## CI and release gates

Every production release must satisfy:

1. Repository CI passes for Node and Python runtimes.
2. Validation workflow covers migrated workspaces.
3. Secret scanning passes.
4. Dependency policy check passes.
5. SBOM is generated and stored as a workflow artifact.
6. Provenance verification passes.
7. Changed service tests include success, failure, auth, timeout, and boundary-denial paths.
8. Migration manifest, execution plan, and runbooks are updated when behavior changes.
9. Rollback notes identify commit SHA, service version, data migration state, and verification commands.

## Security controls

### Access control

- Cloudflare Access protects service-to-service paths.
- Service tokens are scoped per caller/target pair.
- Tenant IDs are propagated through trusted headers only after identity verification.
- Browser clients are denied direct access to service tokens and upstream providers.

### Approval control

- Mutating agent jobs require explicit approval state and scoped tool grants.
- Workspace `shell` and `deploy` actions require explicit approval grants.
- Infrastructure plans may be generated, but execution requires operator approval.
- Billing and ZWallet routes must reject wallet signing, cards, KYC, MPC, and swaps.

### Data control

- Prompts, provider payloads, card data, wallet signatures, KYC payloads, and MPC shares must not be stored in traces.
- Logs must redact credentials and use structured error codes.
- Backups cover only approved durable stores and exclude production secrets.

## Observability requirements

Before external traffic, each deployed service must provide:

- Health signal or package-level CI gate.
- Structured JSON logs with `ts`, `service`, `event`, `request_id`, optional `tenant_id`, `status`, and redacted error code.
- Metrics for request count, latency, upstream failures, approval denials, usage ledger acceptance, duplicate usage records, and agent terminal states.
- Trace propagation for request ID, tenant ID, conversation ID, and usage-correlation ID.
- Alerts for failed CI on protected branch, provider secret exposure, unauthorized execution, billing idempotency failure, and health degradation.

## Backup and recovery requirements

Production backup scope includes:

- workspace metadata store
- agent job store
- queue dead-letter store
- billing ledger
- audit/event store
- generated project object store

Production restore must be tested in staging before production promotion. Restore approval requires an incident commander, operator approval, integrity checks, idempotency duplicate checks, health verification, and updated rollback notes.

## Deployment sequence

1. Confirm provider decisions and production owners.
2. Verify CI, secret scanning, dependency policy, SBOM generation, and provenance verification.
3. Configure identity, Cloudflare Access, service tokens, and secret manager paths.
4. Deploy durable databases, queues, audit sinks, observability sinks, and backup policies to staging.
5. Run staging readiness review.
6. Execute smoke tests for chat, streaming, file upload, workspace metadata, model catalog, provider adapters, agent lifecycle, workspace runtime approvals, usage ledger, and ZWallet denial paths.
7. Confirm rollback commit SHA, service versions, data migration status, and verification commands.
8. Promote to production only after operator approval.
9. Keep external traffic gated until health checks, logs, metrics, traces, and alerts are visible.
10. Open traffic gradually and monitor error budget, latency, billing idempotency, provider failures, and approval denials.

## Go-live checklist

- [ ] Required GitHub workflows pass on the production commit.
- [ ] Cloudflare Access service-to-service policies are mapped and tested.
- [ ] Identity provider and tenant claim mapping are verified.
- [ ] Service tokens are stored in the approved secret manager and have rotation owners.
- [ ] AI Gateway is the only holder of upstream provider credentials.
- [ ] Browser clients cannot access provider secrets or service credentials.
- [ ] Agent Orchestrator uses production DB, queue, identity, observability, and sandbox adapters.
- [ ] Workspace Runtime blocks shell/deploy without approval grants.
- [ ] Billing Ledger records usage idempotently and rejects duplicate keys.
- [ ] ZWallet adapter rejects signing, card, KYC, MPC, and swap payloads.
- [ ] Health checks respond for every deployed service.
- [ ] Logs, metrics, traces, and alerts are visible to the operator.
- [ ] Backups are configured and a staging restore has passed.
- [ ] Incident owner, escalation path, rollback notes, and post-launch watch window are assigned.

## Rollback policy

Rollback is mandatory when any production launch exposes credentials, bypasses approval gates, breaks billing idempotency, routes wallet/card/KYC/MPC/swap data into AI or billing paths, or fails a protected CI gate. Rollback must preserve logs and audit events, rotate affected credentials, disable impacted adapters, and document follow-up prevention items.

## Linked runbooks

- [Execution plan](../migration/execution-plan.md)
- [Migration manifest](../migration/manifest.md)
- [Architecture](../architecture/README.md)
- [Cloudflare Access policies](cloudflare-access.md)
- [Observability and health](observability.md)
- [Backup and restore](backups.md)
- [Incident runbook](incident-runbook.md)
- [Staging readiness review](staging-readiness.md)
