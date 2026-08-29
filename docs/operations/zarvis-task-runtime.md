# Z.A.R.V.I.S. Task Runtime Runbook

## Preconditions

- Identity edge allows only GitHub user ID `4076926`.
- Direct origin access is blocked.
- `ZARVIS_EDGE_SHARED_SECRET` and `ZARVIS_TASK_WORKER_TOKEN` are independent values of at least 32 random bytes.
- `AGENT_DATA_DIR` is persistent, encrypted at rest, and writable only by the task service account.
- GitHub credentials, when required, are read-only and server-side.

## Start

```bash
export ZARVIS_EDGE_SHARED_SECRET='<edge-secret>'
export ZARVIS_TASK_WORKER_TOKEN='<worker-token>'
export AGENT_DATA_DIR='/var/lib/zarvis-tasks'
pnpm --filter @z-platform/zarvis-task-gateway start
```

Verify `GET /healthz` reports:

- `owner_only: true`;
- `durable_tasks: true`;
- `mutating_tools_enabled: false`.

## Owner smoke test

1. Submit the two-step repository status and summary plan.
2. Confirm status is `pending_approval`.
3. Review objective, steps, tool scopes, digest, and expiry.
4. Approve using the returned digest and nonce.
5. Trigger the internal worker using the worker token.
6. Confirm both steps are `succeeded` and checkpoint contains both IDs.
7. Verify audit journal includes request, plan creation, approval, and completion events.

## Pause and resume

- Pause is supported while `pending_approval` or `approved`.
- A paused queued task will not execute.
- Resume returns to its prior state; approved tasks are re-enqueued idempotently.
- Running tasks are not paused mid-tool in this slice; use cancel and retry instead.

## Retry and cancellation

- Retry is allowed only after `failed` and within `max_retries`.
- Cancellation is allowed for non-terminal tasks.
- Expired approval produces terminal `expired` without a tool call.

## Backup and recovery

Back up these fixed files together:

- `jobs.jsonl`;
- `queue.json`;
- `audit-events.jsonl`.

Use a filesystem-consistent snapshot or stop the service. Restore into an empty `AGENT_DATA_DIR`, start the gateway, list tasks, then run one previously queued approved task to validate recovery.

## Rotation

1. Stop owner traffic and workers.
2. Rotate edge and worker secrets independently.
3. Restart the gateway and worker.
4. Confirm old secrets return `403`.
5. Submit and complete a new read-only task.

## Incident containment

Disable edge access, stop workers, rotate secrets, cancel tasks, revoke downstream credentials, and retain audit evidence. Do not delete journals until the incident review is complete.
