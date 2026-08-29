# Event Catalog

## Cross-service events

| Event Name | Version | Producer | Consumer | Schema | Delivery Semantics | Retry | Dead Letter | Idempotency | Ordering | Retention |
|---|---|---|---|---|---|---|---|---|---|---|
| `agent.job.requested.v1` | v1 | agent-orchestrator | agent-provider (queue) | `packages/contracts/schemas/agent.job.requested.v1.schema.json` | At-least-once (queue) | N/A (enqueue) | N/A | Idempotency key deduplication | FIFO per tenant | Until processed |
| `agent.job.approved.v1` | v1 | agent-orchestrator | agent-provider (queue) | `packages/contracts/schemas/agent.job.approved.v1.schema.json` | At-least-once (queue) | N/A (enqueue) | N/A | Idempotency key deduplication | FIFO per tenant | Until processed |
| `agent.job.completed.v1` | v1 | agent-orchestrator | agent-provider (audit) | `packages/contracts/schemas/agent.job.completed.v1.schema.json` | At-least-once (HTTP POST) | N/A | N/A | N/A | Best-effort | Indefinite |
| `zarvis.command.requested.v1` | v1 | zarvis-console | zarvis-orchestrator | `packages/contracts/schemas/zarvis.command.requested.v1.schema.json` | At-least-once (HTTP POST) | N/A | N/A | N/A | N/A | N/A |
| `zarvis.command.completed.v1` | v1 | zarvis-orchestrator | zarvis-console (upstream response) | `packages/contracts/schemas/zarvis.command.completed.v1.schema.json` | At-least-once (HTTP response) | N/A | N/A | N/A | N/A | N/A |
| `zarvis.session.event.v1` | v1 | zarvis-orchestrator | zarvis-orchestrator (session store) | `packages/contracts/schemas/zarvis.session.event.v1.schema.json` | Local (file journal) | N/A | N/A | N/A | Append-only | Until deleted |
| `zarvis.task.requested.v1` | v1 | zarvis-task-gateway | zarvis-task-gateway (runtime) | `packages/contracts/schemas/zarvis.task.requested.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.task.approval.v1` | v1 | zarvis-task-gateway | zarvis-task-gateway (runtime) | `packages/contracts/schemas/zarvis.task.approval.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.task.snapshot.v1` | v1 | zarvis-task-gateway | zarvis-task-gateway (runtime) | `packages/contracts/schemas/zarvis.task.snapshot.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.memory.proposal.v1` | v1 | zarvis-memory | zarvis-memory (store) | `packages/contracts/schemas/zarvis.memory.proposal.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.memory.snapshot.v1` | v1 | zarvis-memory | zarvis-memory (store) | `packages/contracts/schemas/zarvis.memory.snapshot.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.memory.export.v1` | v1 | zarvis-memory | zarvis-memory (store) | `packages/contracts/schemas/zarvis.memory.export.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.perception.session.v1` | v1 | zarvis-perception | zarvis-perception (store) | `packages/contracts/schemas/zarvis.perception.session.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.perception.result.v1` | v1 | zarvis-perception | zarvis-perception (store) | `packages/contracts/schemas/zarvis.perception.result.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.perception.provenance.v1` | v1 | zarvis-perception | zarvis-perception (store) | `packages/contracts/schemas/zarvis.perception.provenance.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.action.preview.v1` | v1 | zarvis-action-gateway | zarvis-action-gateway (store) | `packages/contracts/schemas/zarvis.action.preview.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.action.result.v1` | v1 | zarvis-action-gateway | zarvis-action-gateway (store) | `packages/contracts/schemas/zarvis.action.result.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.action.rollback.v1` | v1 | zarvis-action-gateway | zarvis-action-gateway (store) | `packages/contracts/schemas/zarvis.action.rollback.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.action.approval.v1` | v1 | zarvis-action-gateway | zarvis-action-gateway (store) | `packages/contracts/schemas/zarvis.action.approval.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.proactive.signal.v1` | v1 | zarvis-proactive | zarvis-proactive (runtime) | `packages/contracts/schemas/zarvis.proactive.signal.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.proactive.notification.v1` | v1 | zarvis-proactive | zarvis-proactive (runtime) | `packages/contracts/schemas/zarvis.proactive.notification.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.proactive.feedback.v1` | v1 | zarvis-proactive | zarvis-proactive (runtime) | `packages/contracts/schemas/zarvis.proactive.feedback.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.proactive.action-handoff.v1` | v1 | zarvis-proactive | zarvis-proactive (runtime) | `packages/contracts/schemas/zarvis.proactive.action-handoff.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.proactive.subscription.v1` | v1 | zarvis-proactive | zarvis-proactive (runtime) | `packages/contracts/schemas/zarvis.proactive.subscription.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.proactive.policy.v1` | v1 | zarvis-proactive | zarvis-proactive (runtime) | `packages/contracts/schemas/zarvis.proactive.policy.v1.schema.json` | Local (file) | N/A | N/A | N/A | N/A | Until deleted |
| `zarvis.audit.tool-executed.v1` | v1 | agent-orchestrator (worker) | agent-provider (audit) | `packages/contracts/schemas/zarvis.audit.tool-executed.v1.schema.json` | At-least-once (HTTP POST) | N/A | N/A | N/A | Best-effort | Indefinite |
| `ai.usage.recorded.v1` | v1 | ai-gateway (emitted) | billing-ledger | `packages/contracts/schemas/ai.usage.recorded.v1.schema.json` | At-least-once (HTTP POST) | N/A | N/A | Idempotency key | Best-effort | Indefinite |

## Internal / async communication

| Channel | Producer | Consumer | Mechanism | Schema | Notes |
|---|---|---|---|---|---|
| Agent job queue | agent-orchestrator | agent-provider (`/queue/next`) | HTTP polling | Inline JSON | FIFO per tenant |
| Worker dispatch | agent-provider (`/queue/next`) | agent-orchestrator (`/v1/worker/run-next`) | HTTP polling | Inline JSON | Heartbeat required |
| Local health adapter | zarvis-proactive | zarvis-action-gateway, zarvis-memory, zarvis-perception | HTTP GET `/healthz` | Inline JSON | Loopback only |
| Voice WebSocket | browser | voice-gateway | TCP upgrade with ticket | N/A | Ticket TTL 10-300s |

## Observations

1. **No message queue / event bus** is currently used. All async communication is HTTP polling or direct file append.
2. **No exactly-once delivery** is claimed or implemented. Side-effect consumers must be idempotent.
3. **Dead-letter handling** does not exist. Failed queue items remain in memory/file and are retried indefinitely.
4. **Ordering guarantees** are best-effort (FIFO per tenant in memory/file).
5. **Retention** is indefinite for most stores. No TTL or archival policy is implemented.
