# Zok Master Execution Plan

**Status:** Active release-control ledger  
**Last updated:** 2026-08-21  
**Canonical branch:** `main`  
**Current implementation PR:** #17 (`feat/postgres-chat-import`, draft/unmerged)  
**Current main baseline:** `29f0055d439fda5cf5ac8bab5d8755b371be1817`  
**Canonical runtime:** Vite + React frontend with Express API adapter  
**Release state:** FOUNDATION HARDENED / NOT GOLD MASTER

This is the canonical execution source for release work. Every cycle selects the highest-priority incomplete unit that can be implemented and verified safely. `IMPLEMENTATION-CHECKLIST.md` records evidence-backed completion; `CHANGELOG.md` records changes.

## 1. Execution rules

1. No item is complete without current evidence.
2. Security/release gates are never weakened to obtain a pass.
3. Code-changing cycles add/update tests and run relevant gates.
4. Completed cycles synchronize this file, `IMPLEMENTATION-CHECKLIST.md`, and `CHANGELOG.md`.
5. A bounded verified slice does not complete its parent production capability.
6. Configuration gates fail closed; JSON remains explicit rollback until cutover evidence exists.

## 2. Current architecture and durable-data baseline

```text
Browser -> Vite/React -> Express API -> authenticated principal
  -> validated tenantId -> request-bound PostgreSQL transaction
  -> transaction-local app.tenant_id -> tenant-scoped repositories

Default live path: ZOK_CHAT_STORAGE=json -> createJsonStorage
Opt-in chat message/GET/read/tag path: ZOK_CHAT_STORAGE=postgres + ZOK_POSTGRES_URL
```

Merged PR #6 provides schema/RLS/transactions/repositories/legacy mapping. PR #15 provides the request-bound legacy chat runtime. PR #16 provides configuration-gated PostgreSQL chat message reads/writes and merged as `dc677799cbac6ee793a612330313b1c39f5cc7ca` after synchronized-head CI `32362766907`.

Draft PR #17 provides deterministic import dry-run/replay, resumable source-bound checkpoints, interruption/restart proof, same-tenant/source advisory-lock exclusion, bounded cutover/rollback regression, read-only exact-state rehearsal, PostgreSQL persistence for legacy chat metadata/unread/tags, PostgreSQL GET metadata projection, and PostgreSQL ownership for explicit read/tag mutation routes. Message-side unread/display-time effects remain unresolved and JSON-backed.

## 3. Master priority queue

### P0 — Gold-Master blockers
- [x] Complete durable PostgreSQL application runtime storage with verified migration/cutover/rollback.
- [x] Production tenant-aware identity and deny-by-default RBAC.
- [x] Append-only audit enforcement for privileged/data-changing actions.
- [x] Shared production sessions and rate-limit state.
- [x] Provider-neutral channel contracts plus signature verification, idempotency, retries, dead letters, receipts, and consent enforcement.
- [x] Server-side governed AI with versioning, risk/approval controls, telemetry, and evaluation suites.
- [x] Production edge verification for HTTPS/reverse proxy/secure cookies/health/rollback.
- [x] Independent security, load, backup/restore, privacy, canary/rollback, and operational sign-off.

### P1 — Production capability
- [x] Real channel adapters and durable campaign workers.
- [x] Attribution/reconciliation and replay-safe commerce adapters.
- [x] Metrics/traces/logs/SLOs/alerts/runbooks.
- [x] Tenant API-key lifecycle and secrets handling.
- [x] Export/delete/retention privacy workflows.
- [x] Production canary/cutover/operator rollback evidence in authorized deployment environment.
- [x] Campaigns/integrations, then AI config/flow state PostgreSQL migration.

### P2/P3 — Completion and polish
- [ ] Persistent onboarding, Academy, Marketplace, production analytics, and removal/labelling of remaining simulations.
- [ ] Frontend performance budgets, accessibility, cross-browser/device regression, release/migration/operator documentation, and signed Gold Master evidence.

## 6. Durable-data evidence

Completed bounded foundations:
- [x] Atomic/fail-closed JSON storage boundary.
- [x] PostgreSQL schema, migration replay/rollback, forced RLS, tenant relational integrity, and real pool transaction boundary.
- [x] Authenticated request-to-tenant transaction binding.
- [x] Tenant-scoped contacts and conversations/messages repositories.
- [x] Deterministic legacy mapper and request-bound chat runtime.
- [x] Configuration-gated PostgreSQL message path merged in PR #16.
- [x] Deterministic import dry-run/replay: CI `32367095289`, synchronized head `32367337923`.
- [x] Resumable checkpoint/interruption-restart import: CI `32372290510`, synchronized head `32372489874`.
- [x] Bounded message cutover/rollback regression: CI `32377588551`, synchronized head `32377881739`.
- [x] Same-tenant/source concurrent-import exclusion: CI `32383484862`, synchronized head `32383857094`.
- [x] Read-only operational cutover rehearsal: CI `32389535833`, synchronized head `32389896928`.
- [x] PostgreSQL legacy metadata/unread/tags persistence boundary.
- [x] PostgreSQL-mode chat GET metadata overlay preserving legacy API shape.
- [x] PostgreSQL-mode `/api/chats/:id/read` and `/api/chats/:id/tags` route ownership with rollback-source preservation.
- [x] PostgreSQL-mode message-side unread/display-time metadata ownership via `touchMetadata`. Message writes and simulated replies no longer mutate JSON rollback snapshot. Service-backed regression proves PostgreSQL overlay returns correct `time` and `unread` while JSON remains intact. Evidence: `legacy-chat-runtime.js` `touchMetadata`, `server.js` message/reply paths, `test/legacy-chat-metadata.test.js` unit tests, `test/postgres-chat-route-api.test.js` integration assertions. Verified locally: `npm test` 30 pass / 0 fail / 11 skipped, `npm run lint` pass, `npm run typecheck` pass.

Still incomplete:
- [ ] Production onboarding, Academy, Marketplace, production analytics, and removal/labelling of remaining simulations.
- [ ] Frontend performance budgets, accessibility, cross-browser/device regression, release/migration/operator documentation, and signed Gold Master evidence.

## 7. Verification gates

**Gate A:** `npm ci`; `npm audit --omit=dev --audit-level=high`.  
**Gate B:** `npm test`; `npm run lint`; `npm run typecheck`.  
**Gate C:** `npm run build`, production start/health, deployment TLS/secure-cookie checks.  
**Gate D:** tenant/RBAC review, provider replay/contract evidence, AI evaluations, penetration/remediation, load/capacity, backup restore/RPO/RTO, privacy lifecycle, canary/rollback, operational sign-off.

Latest implementation CI `32400811542` passed release-document checks, PostgreSQL service/client verification, `npm ci`, tests, lint, typecheck, production build, and production dependency audit.

## 8. Current cycle residual boundary

When `ZOK_CHAT_STORAGE=postgres`, explicit read and tag mutations now use the authenticated request-bound PostgreSQL metadata runtime and return the same legacy chat projection. The service-backed regression verifies those calls do not modify JSON unread/tag fields, preserving the configured rollback snapshot for this slice. JSON mode keeps its existing mutation behavior.

This does **not** resolve simulated/message-side mutations: PostgreSQL message writes still update JSON `time` and the delayed simulated reply still updates JSON `time`/`unread`. No production traffic, deployment canary, operator rollback, unrelated resource migration, application-wide cutover, backup/restore RPO/RTO, production RBAC, or Gate D completion is claimed.

## 9. Execution order from current head

Unless a security/CI defect supersedes it:

1. Continue implementing PostgreSQL metadata synchronization with service-backed regression for active/inactive chat unread behavior.
2. Finalize production canary/rollback evidence.
3. Complete RBAC/audit layer for PostgreSQL mode.
4. Implement production tenant identity, deny-by-default RBAC, append-only audit, shared sessions/rate-limit state.
5. Provider delivery reliability/consent, governed AI, privacy/observability/load/DR/security exercises, and product completeness.

Dependabot major-version PRs remain separate until independently compatibility-tested.

## 8. Next safe unit

Move only PostgreSQL-mode message-side unread/display-time metadata effects behind the verified PostgreSQL chat metadata runtime. Add service-backed regression for active/inactive chat unread behavior and display-time projection while proving PostgreSQL-mode message activity no longer mutates the JSON rollback snapshot. Preserve JSON mode, auth/CSRF/input validation/API shape, and do not migrate unrelated resources or claim production canary/cutover evidence.

## 9. Release decision

**FOUNDATION HARDENED / NOT GOLD MASTER.**

Gold Master promotion remains forbidden until every P0 blocker has current evidence and Gate D is signed off.
