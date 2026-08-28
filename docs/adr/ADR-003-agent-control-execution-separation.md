# ADR-003: Agent Control / Execution Separation

## Status

Accepted

## Context

Agent jobs require durable state, approval workflows, queue management, retries, cancellation, and audit trails. Execution requires sandboxing, tool grants, and resource limits. Mixing control plane and execution plane creates implicit authority and security risks.

## Decision

Explicitly separate:

```text
control plane: services/agent-orchestrator
  - Job submission, approval, cancellation, retry
  - Queue management
  - Audit event emission
  - Approval state machine

execution plane: services/agent-provider
  - Durable job store (file-based JSON)
  - Queue persistence
  - Worker dispatch
  - Sandbox request validation
  - Workspace metadata
  - Backup/restore
```

Agents must not gain implicit infrastructure authority. Tool grants are scoped and explicit. Mutating jobs require approval and restricted sandbox constraints.

## Consequences

- Agent orchestrator never directly mutates persistent state; it delegates to agent-provider.
- Agent provider enforces approval state before execution.
- Audit events are emitted for every state transition.
- Backup/restore is namespace-isolated.
- The split allows independent scaling and security auditing of control vs execution.
