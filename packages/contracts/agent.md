# Agent Contracts v1

Agent orchestration events describe the lifecycle of a platform agent job without granting the agent direct access to production infrastructure, wallet signing, payment data, provider credentials, or unapproved tools.

All events are immutable audit records. Services may project them into durable job state, queues, metrics, and traces, but the source event payload must not be mutated after emission.

## Common envelope

Every agent event uses the same envelope fields:

| Field | Type | Required | Notes |
|---|---|---|---|
| `event_id` | string | yes | Globally unique event identifier. |
| `event_type` | string | yes | One of the versioned event names below. |
| `event_version` | string | yes | Must match `v1`. |
| `occurred_at` | string | yes | ISO 8601 UTC timestamp. |
| `tenant_id` | string | yes | Platform tenant boundary. |
| `job_id` | string | yes | Stable job identifier across lifecycle events. |
| `correlation_id` | string | no | Request, conversation, workflow, or trace correlation identifier. |

## agent.job.requested.v1

Created when a user or trusted platform service asks the orchestrator to create a job.

```json
{
  "event_id": "evt_01J00000000000000000000000",
  "event_type": "agent.job.requested.v1",
  "event_version": "v1",
  "occurred_at": "2026-07-13T00:00:00.000Z",
  "tenant_id": "tenant-1",
  "job_id": "job_01J00000000000000000000000",
  "requested_by": {
    "type": "user",
    "id": "user-1"
  },
  "objective": "Summarize the repository migration status.",
  "input_refs": [
    {
      "type": "workspace",
      "id": "workspace-1"
    }
  ],
  "tool_grants_requested": [
    {
      "tool": "repo.read",
      "scope": "cvsz/z-platform",
      "mutating": false
    }
  ],
  "execution_policy": {
    "requires_approval": true,
    "timeout_seconds": 900,
    "max_retries": 1
  },
  "correlation_id": "chat-1"
}
```

Requested jobs are not executable until policy evaluation and approval state allow execution. Mutating tools must stay blocked unless explicitly granted in an approval event.

## agent.job.approved.v1

Created when an authorized approver grants a job permission to execute with a bounded set of tools.

```json
{
  "event_id": "evt_01J00000000000000000000001",
  "event_type": "agent.job.approved.v1",
  "event_version": "v1",
  "occurred_at": "2026-07-13T00:01:00.000Z",
  "tenant_id": "tenant-1",
  "job_id": "job_01J00000000000000000000000",
  "approved_by": {
    "type": "user",
    "id": "operator-1"
  },
  "approval_state": "approved",
  "tool_grants": [
    {
      "tool": "repo.read",
      "scope": "cvsz/z-platform",
      "mutating": false,
      "expires_at": "2026-07-13T01:01:00.000Z"
    }
  ],
  "constraints": {
    "sandbox": "restricted",
    "network": "deny-by-default",
    "timeout_seconds": 900,
    "max_retries": 1
  },
  "correlation_id": "chat-1"
}
```

Approval events are the only source of execution authority. A worker must reject any tool call outside the granted tool, scope, mutability, expiry, and sandbox constraints.

## agent.job.completed.v1

Created when a job reaches a terminal state.

```json
{
  "event_id": "evt_01J00000000000000000000002",
  "event_type": "agent.job.completed.v1",
  "event_version": "v1",
  "occurred_at": "2026-07-13T00:03:00.000Z",
  "tenant_id": "tenant-1",
  "job_id": "job_01J00000000000000000000000",
  "status": "succeeded",
  "result_refs": [
    {
      "type": "artifact",
      "id": "artifact-1"
    }
  ],
  "usage": {
    "input_tokens": 1200,
    "output_tokens": 320,
    "runtime_ms": 42000
  },
  "audit": {
    "worker_id": "worker-1",
    "attempt": 1,
    "tool_calls": [
      {
        "tool": "repo.read",
        "scope": "cvsz/z-platform",
        "mutating": false,
        "status": "succeeded"
      }
    ]
  },
  "correlation_id": "chat-1"
}
```

Terminal statuses are `succeeded`, `failed`, `cancelled`, and `expired`. Completion events must include enough audit detail to reconcile attempts, retries, tool use, and worker identity.

## Schema files

- `schemas/agent.job.requested.v1.schema.json`
- `schemas/agent.job.approved.v1.schema.json`
- `schemas/agent.job.completed.v1.schema.json`
