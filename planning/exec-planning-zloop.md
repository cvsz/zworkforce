# ZLoop Integration Execution Plan

**Status:** Forward roadmap  
**Parent:** `planning/exec-planning.master.md`, `planning/exec-planning-zwf.md`, `AGENTS.md`  
**Source architecture:** `docs/ZLOOP-INTEGRATION.md`

ZLoop adds a reusable Discover → Plan → Execute → Verify → Review → Repair feedback cycle to zWorkforce while preserving zWorkforce as the sole authority for durable state, approvals, queueing, provider access, costs, audit and secrets.

## ZL-0 — Contract and safety baseline

- [x] Add bounded coordinator and lifecycle.
- [x] Require tenant and actor binding.
- [x] Require existing authorization for execute/repair.
- [x] Stable tenant-bound idempotency key.
- [x] Independent verifier contract.
- [x] `INCONCLUSIVE` → `HANDOFF` fail-closed behavior.
- [x] Hard iteration/token/cost budget handoff.
- [x] Unit tests for core safety invariants.
- [x] Architecture and adapter map documentation.

## ZL-1 — Durable repository adapter

- [ ] Add canonical zWorkforce repository representation for loop state.
- [ ] PostgreSQL + SQLite compatibility.
- [ ] Optimistic/versioned transition guard or equivalent transactional compare-and-set.
- [ ] Crash/resume tests for every non-terminal phase.
- [ ] Tenant isolation tests and malformed checkpoint rejection.

**Gate:** no alternate ZLoop database or JSONL state becomes production authority.

## ZL-2 — Approval and policy adapter

- [ ] Bind loop mutation to durable approval authority.
- [ ] Bind tenant, actor, action, target, phase, iteration and idempotency key.
- [ ] Reject expired/rejected/cancelled/replayed approval.
- [ ] Preserve four-eyes constraints and per-agent grants.
- [ ] Audit approval decision and mutation result.

**Gate:** there is no local/admin/debug bypass around the canonical approval authority.

## ZL-3 — Transactional queue adapter

- [ ] Submit approved steps through the existing distributed queue.
- [ ] Preserve lease ownership, retry classification and cancellation.
- [ ] Deduplicate successful side effects after crash/retry windows.
- [ ] Carry loop/tenant/actor/idempotency metadata to workers.
- [ ] HA lease-expiry and worker-restart tests.

**Gate:** ZLoop does not create a parallel worker queue.

## ZL-4 — Model routing and canonical cost ledger

- [ ] Map loop roles to existing model-router policy.
- [ ] Debit canonical cost/usage ledger.
- [ ] Cheap-first/fallback routing must preserve provider policy and budgets.
- [ ] Structured-output validation for stage results.
- [ ] Provider errors must not bypass token/cost ceilings.

## ZL-5 — Verification and repair pipeline

- [ ] Registry for tests, static analysis, security, policy and outcome evaluators.
- [ ] Normalized PASS/FAIL/INCONCLUSIVE evidence records.
- [ ] Failure/evidence fingerprint for no-progress detection.
- [ ] Bounded repair attempts.
- [ ] Mandatory regression verification after repair.
- [ ] Executor may never set SHIPPED directly.

## ZL-6 — API and UI

- [ ] Read-only mission/list/detail/status/evidence APIs.
- [ ] Mutating start/cancel/retry endpoints behind canonical authorization.
- [ ] Dashboard Loop/Mission card with progress, budget and evidence.
- [ ] No provider credentials, database strings or approval bypass state in static/browser assets.

## ZL-7 — Fleet loops

- [ ] Scoped child missions with parent budget inheritance.
- [ ] Max depth/fan-out/concurrency.
- [ ] Worktree/workspace ownership for mutating coding agents.
- [ ] Conflict detection before integration.
- [ ] Global independent verifier owns final acceptance.

## ZL-8 — Production evidence

- [ ] Full Python test matrix.
- [ ] PostgreSQL integration/recovery tests.
- [ ] security-invariants and CodeQL.
- [ ] approval replay/fail-closed tests.
- [ ] tenant-isolation tests.
- [ ] queue lease/failure drill.
- [ ] OTLP/audit correlation evidence.
- [ ] required external evidence recorded when release authority binds ZLoop to a release candidate.

## Integration completion rule

Do not mark the integration complete solely because the bridge exists. Production completion requires concrete adapters to existing authorities, exact-candidate required checks, recovery/idempotency evidence, security review and any applicable operator-owned external evidence.
