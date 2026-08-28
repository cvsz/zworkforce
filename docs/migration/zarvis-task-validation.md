# Z.A.R.V.I.S. Durable Task Validation

Date: 2026-08-06
Epic: #148
Issue: #151
Branch: `feat/zarvis-durable-task-approval`

## Scope

Validate the first owner-only durable multi-step task lifecycle:

```text
create exact read-only plan
  -> pending approval
  -> digest + nonce approval
  -> durable queue
  -> dependency-ordered worker
  -> checkpoint/results/audit
```

## Focused coverage

The branch includes tests for:

1. mutating-step and invalid-dependency rejection;
2. immutable owner/tenant task identity;
3. exact-plan idempotency replay and conflict;
4. digest mismatch and one-time nonce rejection;
5. pause/resume of pending and approved work;
6. two-step repository status and deterministic summary execution;
7. approval expiry before any tool call;
8. process reconstruction of job, queue, and audit adapters;
9. owner-route and independent worker-route authentication;
10. server startup failure without both required secrets;
11. all existing generic `agent-orchestrator` lifecycle tests;
12. all command/session/task JSON Schema checks.

## Required gates

- [ ] `services/agent-orchestrator` existing tests pass.
- [ ] `services/zarvis-task-gateway` focused tests pass.
- [ ] `packages/contracts` schema tests pass.
- [ ] Full repository CI passes.
- [ ] Validate workflow passes.
- [ ] CodeQL Advanced passes with no unresolved review thread.
- [ ] Operations workflow passes.

## Deployment gates retained for #156

- exact identity-edge allow policy;
- direct-origin denial;
- persistent-volume backup/restore drill;
- edge and worker secret rotation drill;
- production database/queue/identity/sandbox provider evidence;
- live worker smoke in the authorized environment.
