---
name: zworkforce-zarvis-runtime-orchestration
description: Implement and review Z.A.R.V.I.S. runtime skills, agent manifests, scheduled/continuous execution, handoffs, capability policy, supervision, and trace-driven improvements using existing zWorkforce durable execution and approval boundaries.
---

# zWorkforce Z.A.R.V.I.S. runtime orchestration

Use this skill when changing runtime skill catalogs, agent definitions, orchestrator routing, scheduled or continuous agents, agent handoffs, capability policy, operator supervision, or trace-driven optimization.

## Required reading

- `AGENTS.md`
- `packages/zarvis/AGENTS.md`
- `ROADMAPS.md`
- `exec-planning-zarvis.md`
- `packages/zarvis/docs/architecture/openjarvis-upgrade-map.md`
- `packages/zarvis/docs/architecture/skills-agents.md`
- `packages/zarvis/docs/requirements/master-requirements.md`
- relevant `services/zarvis-*` contracts/tests
- relevant existing agent files under `packages/zarvis/agents/`

## Core rule

Do not port a parallel OpenJarvis runtime into zWorkforce. Adapt useful registry, skill and agent-mode concepts to the existing zWorkforce task, scheduler, policy, approval, audit and tenant model.

## Runtime skill rules

Every product/runtime skill requires:

- stable ID and semantic version;
- input/output schemas;
- declared capabilities and allowed tools;
- mutability classification;
- approval policy;
- bounded timeout/concurrency;
- retry and idempotency semantics;
- audit mapping;
- owner and rollback/version policy.

Discovery does not imply authorization. Invalid or duplicate manifests fail closed. Generated/trace-mined skills are review candidates and must not auto-enable in production.

## Agent-mode rules

Supported modes:

- `on_demand`
- `scheduled`
- `continuous`

Use the existing durable zWorkforce scheduler/event infrastructure for scheduled work. Do not introduce a second scheduler.

Continuous mode must be implemented as bounded, supervised work with:

- lease/heartbeat;
- stale-run detection;
- max concurrency;
- rate limits;
- backoff/failure budget;
- pause/resume/disable;
- version pinning and rollback;
- bounded memory/session growth.

A continuous agent never receives unrestricted mutation rights merely because it is long-lived.

## Handoff rules

- Handoffs are structured/versioned.
- The receiving agent cannot expand capabilities, tool scope or mutation scope.
- Prefer existing specialists instead of duplicating agents.
- Voice routing should hand off to existing code, memory, architecture, review and operations specialists when appropriate.
- The handoff preserves request/session/tenant correlation and deadline/budget.

## Approval and mutation

- A model prediction, user speech transcript, scheduled trigger or continuous-agent decision is not by itself mutation approval.
- Mutating work remains behind the existing approval/action gateway.
- External side effects remain at-least-once where the platform documents that boundary; tools must use idempotency/fencing where applicable.
- Never turn retries into duplicate external mutations.

## Registry rules

When adding registry/discovery abstractions:

- typed/scope-specific registries;
- deterministic discovery;
- duplicate rejection;
- explicit health/capability metadata where applicable;
- no silent cloud/provider enablement;
- explicit pinned-provider failures should be visible rather than silently substituted when correctness depends on the pin.

## Trace-driven improvement

Traces may suggest routing or skill improvements, but automation must not self-promote unreviewed behavior into production.

Required promotion sequence:

1. collect redacted evidence;
2. generate candidate change;
3. test offline/replay;
4. policy/security review;
5. bounded canary/versioned rollout;
6. compare outcome, latency, cost and failure metrics;
7. promote or rollback explicitly.

## Tests

Add success and denial/failure coverage for:

- manifest validation;
- duplicate/cyclic skill dependencies;
- unknown capabilities/tools;
- mutating skill with missing approval policy;
- tenant isolation;
- scheduled occurrence idempotency;
- continuous lease/heartbeat/stale detection;
- rate/concurrency limits;
- pause/resume/disable;
- agent handoff scope narrowing;
- retries/idempotency;
- trace redaction;
- version rollback.

## Validation

```bash
python3 -m compileall -q zworkforce tests scripts
PYTHONPATH=. python3 -m unittest discover -s tests -v
pnpm --dir packages/zarvis install --frozen-lockfile
pnpm --dir packages/zarvis peers check
pnpm --dir packages/zarvis test
pnpm --dir packages/zarvis audit --audit-level high
```

Run PostgreSQL-specific tests against a real PostgreSQL service whenever durable schema/lease/scheduler behavior changes. GitHub Actions remains the release gate.