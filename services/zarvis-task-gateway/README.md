# Z.A.R.V.I.S. Task Gateway

Owner-only durable multi-step task and approval surface for Epic #148 / Issue #151.

The gateway reuses `services/agent-orchestrator` as the single task lifecycle engine. It adds Z.A.R.V.I.S.-specific plan validation, immutable owner identity, exact-plan approval proof, pause/resume, fixed-path durable adapters, and a constrained two-step read-only worker fixture.

## Security model

The owner is permanently bound to:

```text
GitHub ID: 4076926
user_id:   github:4076926
tenant_id: owner-4076926
```

There is no owner override, registration, invitation, guest, or multi-user mode.

Owner routes require the trusted edge to inject:

```text
x-zarvis-owner-id: 4076926
x-zarvis-edge-secret: <ZARVIS_EDGE_SHARED_SECRET>
```

The internal worker route requires an independent bearer token:

```text
Authorization: Bearer <ZARVIS_TASK_WORKER_TOKEN>
```

Both secrets must contain at least 32 bytes. The browser must never receive either secret.

## Exact-plan approval

Submitting a task returns:

- SHA-256 `approval_digest` over the canonical objective and ordered DAG steps;
- one-time `approval_nonce`;
- `approval_expires_at`, 15 minutes after task creation.

Approval succeeds only when digest and nonce match the stored task exactly and have not expired or been consumed. The worker checks expiry again immediately before executing any tool.

## First plan fixture

```json
{
  "schema_version": "zarvis.task.requested.v1",
  "idempotency_key": "repo-review-1",
  "objective": "Inspect and summarize cvsz/z-platform",
  "steps": [
    {
      "id": "repository-status",
      "tool": "github.repository.status",
      "scope": "cvsz/z-platform",
      "mutating": false,
      "depends_on": [],
      "arguments": {}
    },
    {
      "id": "repository-summary",
      "tool": "zarvis.repository.summary",
      "scope": "cvsz/z-platform",
      "mutating": false,
      "depends_on": ["repository-status"],
      "arguments": {}
    }
  ]
}
```

Only registered read-only tools are accepted. Mutating steps fail closed.

## API

- `GET /healthz`
- `GET /v1/tasks`
- `POST /v1/tasks`
- `GET /v1/tasks/{id}`
- `POST /v1/tasks/{id}/approve`
- `POST /v1/tasks/{id}/pause`
- `POST /v1/tasks/{id}/resume`
- `POST /v1/tasks/{id}/cancel`
- `POST /v1/tasks/{id}/retry`
- `POST /v1/internal/worker/run-next`

## Durable state

The single-owner runtime stores fixed-path files under `AGENT_DATA_DIR`:

- `jobs.jsonl`: append-only job snapshots;
- `queue.json`: atomically replaced pending queue;
- `audit-events.jsonl`: append-only lifecycle audit.

Request values never influence filesystem paths. This mode is intended for one process. Existing production HTTP adapters remain the scale-out boundary for operator-approved database, queue, audit, identity, and sandbox providers.

## Run

```bash
export ZARVIS_EDGE_SHARED_SECRET='<at-least-32-random-bytes>'
export ZARVIS_TASK_WORKER_TOKEN='<independent-32-byte-token>'
export AGENT_DATA_DIR='/var/lib/zarvis-tasks'
pnpm --filter @z-platform/zarvis-task-gateway start
```
