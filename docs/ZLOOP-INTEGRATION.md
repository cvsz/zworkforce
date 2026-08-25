# ZLoop Integration with zWorkforce

## Purpose

ZLoop is integrated as a bounded orchestration pattern inside zWorkforce, not as a second control plane. zWorkforce remains authoritative for tenants, durable state, queue leasing, approvals, policy-as-code, model/provider access, cost accounting, audit, secrets and production evidence.

## Architecture

```text
Goal / Mission
    |
    v
ZLoopCoordinator
    |-- Discover / Plan --------> zWorkforce model/router boundary
    |-- Execute / Repair -------> zWorkforce approval authority -> queue/tool execution
    |-- Verify -----------------> independent zWorkforce verifier/check adapters
    |-- Review -----------------> policy/security/reviewer gates
    |-- Persist ----------------> zWorkforce repository/state authority
    `-- Audit ------------------> zWorkforce tamper-evident audit/OTLP boundary
```

## Non-negotiable bindings

1. `tenant_id` and `actor_id` are mandatory on every loop.
2. ZLoop owns no provider credentials and never exposes provider secrets to clients.
3. `EXECUTE` and `REPAIR` are mutations and must be authorized by the existing zWorkforce approval/policy authority before dispatch.
4. Stable idempotency keys bind loop, tenant, actor, phase, iteration and target.
5. The dispatcher must use existing durable zWorkforce queue/repository paths; the bridge must not create an alternate queue.
6. Verification is independent from the mutating dispatcher. `INCONCLUSIVE` fails closed to `HANDOFF`.
7. Budget exhaustion fails to `HANDOFF`; the loop cannot increase its own budget.
8. All transitions are persisted and audited through injected zWorkforce authorities.
9. Existing four-eyes approvals, per-agent grants, tenant isolation and production evidence rules remain stronger than ZLoop defaults and must not be weakened.
10. The integration is forward-roadmap scope and must not be represented as a `v3.0.3` release blocker unless release authority explicitly binds it.

## Adapter map

| ZLoop port | zWorkforce authority |
|---|---|
| `StateAuthority` | durable repository / PostgreSQL or SQLite state methods |
| `ApprovalAuthority` | existing operator/four-eyes/policy-as-code mutation authorization |
| `WorkDispatcher` | transactional task queue + bounded tool execution |
| `IndependentVerifier` | test/security/policy/outcome evaluator adapters |
| `AuditAuthority` | tamper-evident audit + OTLP/event pipeline |
| loop budget | existing cost ledger and provider/model routing limits |

## Initial integration slice

`zworkforce/zloop_bridge.py` provides a provider-neutral coordinator and explicit ports. It deliberately avoids importing or duplicating zWorkforce database, queue, approval or provider implementations. This allows the next vertical slice to bind each port to the existing concrete subsystem while keeping dependency direction clean.

## Next implementation slices

1. Repository adapter: persist `ZLoopState` using existing tenant-scoped repository methods and PostgreSQL transaction semantics.
2. Approval adapter: bind mutation requests to the durable zWorkforce approval record, actor, tenant, action, target, expiration and idempotency key.
3. Queue adapter: submit approved loop steps to the existing transactional queue and recover from lease expiry without duplicate side effects.
4. Model/cost adapter: debit the existing cost ledger and apply role-specific model routing/failover.
5. Verification adapter registry: map unit/integration/security/policy/outcome checks into a normalized PASS/FAIL/INCONCLUSIVE result.
6. API surface: read-only loop status endpoints first; mutating endpoints only after authorization tests prove fail-closed behavior.
7. UI: mission/loop progress card using server-provided state only; no credentials or local bypass controls.
8. HA/recovery evidence: PostgreSQL restart, worker lease expiry, duplicate delivery and approval replay tests.

## Definition of complete

The ZLoop integration is production-ready only when all concrete adapters use existing zWorkforce authorities, PostgreSQL recovery and idempotency tests pass, mutation approvals are replay-safe and fail closed, tenant boundaries are verified, budgets debit the canonical cost ledger, independent verification cannot be bypassed, full required CI/security checks are green, and external HA/observability evidence is recorded when required by the release policy.
