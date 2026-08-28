# Z.A.R.V.I.S. Durable Task Runtime

Epic: #148
Issue: #151

## Decision

Reuse `services/agent-orchestrator` as the single job lifecycle engine. The Z.A.R.V.I.S. task gateway extends that engine rather than introducing a competing task store, queue, approval model, or worker protocol.

## Flow

```text
Owner browser / ZVoice
        |
        | trusted owner edge assertion
        v
ZARVIS Task Gateway
        | validate read-only DAG
        | create digest + nonce + expiry
        v
AgentOrchestrator pending_approval
        |
        | exact owner approval proof
        v
Durable queue -> internal worker
        |
        v
step checkpoint/result + immutable audit
```

## Task model

A task contains:

- immutable owner and tenant identity;
- objective and ordered DAG steps;
- requested read-only capability grants;
- idempotency key and correlation ID;
- exact-plan SHA-256 approval digest;
- one-time approval nonce and expiry;
- attempt/retry/timeout policy;
- step results and completed-step checkpoint;
- lifecycle and tool audit records.

Dependencies must point only to earlier steps. This provides deterministic topological order and rejects cycles or unresolved dependencies during validation.

## State transitions

```text
pending_approval <-> paused
pending_approval -> approved -> running -> succeeded|failed|expired
approved <-> paused
failed -> approved (retry within limit)
non-terminal -> cancelled
```

Paused approved tasks cannot execute. If an already queued item is consumed while paused, resume re-enqueues the next attempt idempotently.

## Approval binding

The digest covers canonicalized objective and ordered steps, including tool, scope, dependencies, and arguments. Approval is:

- owner-specific;
- exact-plan specific;
- single-use;
- short-lived;
- checked at approval and immediately before worker execution.

Changing the plan requires a new task or idempotency key. Reusing an idempotency key with a different digest returns `409`.

## Storage adapters

Single-owner mode uses fixed-path durable files. Scale-out production continues through the existing HTTP job-store, queue, audit, identity, and sandbox adapter boundaries. The two modes share the same `AgentOrchestrator` lifecycle and contracts.

## Current capability boundary

The first fixture supports only:

1. `github.repository.status`;
2. `zarvis.repository.summary`.

Both are read-only. Mutating tools remain unavailable until Phase 5 and cannot be enabled by changing task input.
