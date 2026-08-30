# Architecture

## Design goals

zWorkforce is a control plane and runtime for governed AI work. The architecture separates durable state, orchestration, execution, model-provider routing and external integrations so each can scale without giving browser clients provider credentials.

## Runtime components

```text
Ingress / Identity
       |
       v
API replicas -------------------------- MCP clients
       |
       +---- PostgreSQL / SQLite ----+
       |                             |
       v                             v
Worker replicas                 Scheduler replicas
       |                         active/passive lease
       v                             |
PolicyEngine                         +--> workflows/events
       |
       v
Model Router -> Provider Pool -> LLMs
       |
       +--> Tool Gateway
       +--> Semantic Memory
       +--> Artifact Store
       +--> Sub-agents

Outbox replicas -- active/passive lease --> approved webhooks
Telemetry -----------------------------> OTLP / Prometheus
```

## Database backends

### SQLite
Used for zero-config development and single-host deployments. WAL, busy timeout and transactional leases are retained from v2.

### PostgreSQL
The compatibility layer maps the repository's parameterized SQL onto psycopg and preserves the same repository API. Worker claims use `SELECT ... FOR UPDATE SKIP LOCKED` so separate hosts can claim independent tasks safely. Task state remains the source of truth; worker processes are disposable.

## Durable task state

```text
waiting_approval -> queued -> running -> succeeded
        |             |         |       failed
        |             |         +-----> queued retry
        +-> canceled  |                  |
                      +-----------------> dead_letter
```

A claim increments `attempt`, assigns `lease_owner`, `lease_expires_at` and heartbeat. Stale running tasks are recovered according to attempt budget.

## Policy model

The production engine is `PolicyEngine`, a compatible subclass of the bounded v2 engine. Tenant policies are JSON documents with glob-style action matching and deterministic conditions. Policy checks occur before task creation and immediately before tool execution. Explicit deny wins.

## Workflow engine

Workflow definitions are versioned DAGs. Each run snapshots the workflow version and each step stores durable status and the task ID it created. A step becomes runnable only after all dependencies succeed. Template rendering supports `{{input.*}}` and `{{steps.<id>.result}}`.

## Scheduler and events

Cron/interval schedules and durable events live in the database. Scheduler replicas compete for a renewable service lease. The leader dispatches due schedules, processes event rules and advances workflow runs. Idempotency keys include schedule timestamp or event/rule identity.

## Evaluation engine

Evaluation suites contain cases and tier variants. A run creates real workforce tasks for each case/variant pair. Final summaries prioritize pass rate/outcome score before cost and duration, avoiding cost optimization that silently degrades quality.

## Identity

- persistent hashed API keys with roles/scopes;
- OIDC discovery/JWKS verification with issuer/audience checks;
- group-to-role mapping;
- optional HMAC-signed identity-aware proxy boundary for SAML/brokered identity.

## Knowledge and artifacts

Local semantic memory uses deterministic feature hashing. A runtime-selectable Qdrant adapter uses an OpenAI-compatible embeddings endpoint. Artifacts are content-addressed by SHA-256 and can be stored locally or in S3-compatible storage.

## Observability

Metrics are Prometheus-compatible. Optional OTLP/HTTP JSON tracing wraps provider calls. Provider health, queue state, outcomes, cost, workflows, evaluations, outbox and SLO status are visible to operations.

## Dashboard realtime control packages

The browser dashboard uses an authenticated, bounded Server-Sent Events stream at
`GET /api/v1/dashboard/events`. The stream accepts its replay cursor through
`X-ZWorkforce-Event-Cursor` and its tenant through `X-Tenant-ID`; credentials and
cursors are never placed in the URL. The viewer still uses the existing REST
snapshot endpoints as the authoritative render path.

Durable repository transitions append compact, allowlisted invalidations to
`dashboard_events2` in tenant scope. Event payloads contain status metadata only;
prompts, results, provider errors, secrets, storage URIs and raw tool arguments
are deliberately excluded. A retained-cursor gap emits `resync.required`, after
which the browser refreshes its snapshot and resumes from the returned cursor.
The scheduler prunes events older than the configured
`ZWORKFORCE_DASHBOARD_EVENT_RETENTION_SECONDS` horizon on its durable maintenance
path; the default retention is seven days and the setting is capped at one year.
Audit events remain durable for audit readers but are omitted from the ordinary
viewer workforce stream unless the principal has both an admin role and
`audit:read`.

The dependency-free browser package coalesces event notifications across the
overview, workforce, governance, automation, FinOps, knowledge and Z.A.R.V.I.S.
surfaces. It exposes `LIVE`, `RECONNECTING`, `POLLING`, `STALE` and `OFFLINE`
states. `POLLING` is a bounded recovery path, not evidence that any provider,
voice gateway, queue, storage adapter or external integration is provisioned.

## Scaling

- API: stateless except durable DB/storage; horizontally scalable.
- Workers: horizontally scalable through PostgreSQL claim locking.
- Scheduler/outbox: multiple replicas safe through service-leader leases.
- Memory/artifacts: replace local adapters with Qdrant/S3.
- Database: deploy PostgreSQL using the operator's HA/PITR topology.
