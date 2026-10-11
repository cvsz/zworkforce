# ZEAZ AGI Reasoning Layer — zWorkforce Integration Blueprint

**Status:** Forward roadmap / design-only candidate  
**Release impact:** None for v3.0.4 unless explicitly approved by release authority  
**Existing source of truth:** [ZLoop integration](ZLOOP-INTEGRATION.md) and [execution plan](../planning/exec-planning-zloop.md)

## Decision

Integrate AGI-inspired goal reasoning into existing zWorkforce **ZLoop**; do **not** deploy the standalone prototype as a second API, identity gateway, queue, SQLite store, model router, or approval service. This is a bounded autonomous-agent platform, not a verified human-level AGI system.

## Capability ownership

| Capability | Canonical zWorkforce boundary | Work needed |
| --- | --- | --- |
| Goal decomposition and planning | ZLoop coordinator + existing model/router | Typed planning output and plan validation |
| Multi-agent collaboration | Existing orchestrator, transactional queue, agents/versions | Child-task delegation with max depth/fan-out |
| Self-review and replanning | ZLoop independent verifier/review/repair | Evidence-driven bounded retry, no-progress detection |
| Memory | Existing tenant-scoped semantic memory and repository | Least-privilege retrieval, provenance, retention |
| Tool execution | Existing approved/scoped worker and MCP policies | Explicit capability allowlists and approval binding |
| LLM routing and costs | Existing AI Gateway and canonical cost ledger | Per-stage budget enforcement and evaluation |
| Monitoring | Existing audit, tracing, Prometheus, dashboard | Correlated mission/phase/attempt identifiers |

## Proposed contracts (design only)

- **Mission:** `mission_id`, `tenant_id`, `actor_id`, `goal`, `policy_ref`, `budget_limit`, `status`, `created_at`.
- **Plan:** validated, versioned DAG of tasks with bounded dependencies, typed inputs/outputs, nonnegative estimated cost, allowed tool capabilities, approval classification, and acceptance criteria.
- **Attempt:** `mission_id`, `plan_version`, `step_id`, `attempt`, `idempotency_key`, `lease_id`, `evidence_refs`.
- **Verification:** independent `PASS | FAIL | INCONCLUSIVE`; INCONCLUSIVE fails closed to HANDOFF, and execution alone cannot mark a mission successful.
- **Authorization:** any mutation uses existing durable policy and approval services; bind approval to exact tenant, actor, action, target, plan digest, expiry and idempotency key.

## Trust boundaries and invariants

1. Server-side only provider credentials and tool tokens. Never send secrets or mutation grants to browser clients.
2. Treat model output, retrieved memory, MCP responses, and repository content as untrusted data; enforce schema validation and prompt-injection-resistant tool selection.
3. A plan is **not** authorization. Execute/repair steps require the canonical authorization authority and four-eyes approval where applicable.
4. No production infrastructure or cross-repository mutation without resource ownership, dry-run preview, exact approval, and post-action evidence.
5. All durable writes go through existing tenant-scoped repositories; preserve PostgreSQL transactional leasing and SQLite local compatibility.
6. Enforce global and inherited child budgets for iterations, runtime, tokens, cost, fan-out and concurrency; no agent can raise its own limits.
7. Support crash/resume, cancellation, retries, deduplication, versioned state transitions and replay-safe approvals.
8. Protect data provenance, retention, PII minimization and cross-tenant retrieval boundaries.
9. Record model version, decision inputs, policy verdict, tool grants, cost, evidence, and trace correlation with redaction.
10. Fail closed on verifier uncertainty, missing audit persistence, expired approval, policy denial, or exhausted budget.

## Incremental implementation sequence

1. **Baseline and tests:** inspect `zworkforce/zloop_bridge.py`, current task/workflow/repository contracts, existing APIs and nested `AGENTS.md`. Record current regression evidence.
2. **ZL-1 + AGI schema:** integrate typed `Mission`/`Plan` state with canonical PostgreSQL/SQLite repository and tenant/actor checks. Add migration and rollback tests.
3. **ZL-2/3:** attach approval and queue adapters to existing authorities; test replay, denial, expiry, retries, lease takeover, duplicate delivery and cancellation.
4. **ZL-4/5:** add structured goal decomposition and independent critic/verifier through existing model routing, cost accounting and bounded replan workflow.
5. **ZL-6:** add read-only mission progress/evidence API first; enable mutation endpoints only after negative authorization tests. Add operator dashboard without client secrets.
6. **ZL-7/8:** multi-agent child missions with inherited grants/budgets, concurrency limits, recovery and real external evidence.

## Acceptance criteria

- No second identity system, production DB, queue, provider-secret store, policy engine or cost ledger.
- Tests cover allowed/denied/missing/replayed/expired approval and cross-tenant attempts.
- All mutation steps remain denied unless canonical grants are present.
- Durable recovery does not duplicate completed external side effects.
- Existing Python tests, security scans and PostgreSQL integration tests pass on the exact candidate SHA.
- Real provider/HA/deployment claims require external operator evidence per `AGENTS.md` and `docs/PRODUCTION-EVIDENCE.md`.

## Rollout and rollback

Keep runtime behavior unchanged until independently reviewed adapters and tests exist. Introduce disabled-by-default feature flags, start with read-only mission inspection and staging, use a canary rollout with circuit breaker and a kill switch, and retain the existing ZLoop / task paths as rollback. No automated merge, release tag or production deployment from this design PR.

## Explicit non-goals

- Claiming true AGI, sentience, or human-level general intelligence.
- Replacing existing ZLoop architecture with the standalone prototype.
- Circumventing four-eyes authorization, IAM, branch protection, CI or deployment approval.
