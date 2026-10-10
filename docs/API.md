# API v3

All `/api/v1/*` endpoints require authentication. Tenant scope comes from the credential; superadmin may set `X-Tenant-ID`. JSON errors use `{"error":{"code","message"},"request_id"}`.

## Core

```text
GET  /health
GET  /ready
GET  /metrics
GET  /api/v1/overview
GET  /api/v1/providers
GET  /api/v1/models
GET  /api/v1/recommendations
GET  /api/v1/tools
```

## Agents / policy

```text
GET/POST /api/v1/agents
GET      /api/v1/agents/{id}/versions
GET/POST /api/v1/agent-templates
POST     /api/v1/agent-templates/{id}/instantiate
GET/POST /api/v1/policies
POST     /api/v1/prometa/install
```

Agent and skill operating conventions are defined in
[PROMETA-MASTER.md](PROMETA-MASTER.md).
`POST /api/v1/prometa/install` idempotently installs the built-in ProMeta
agents, skills, agent templates and workflows for the authenticated tenant.

Policy document:

```json
{"default":"allow","rules":[{"id":"deny-shell","effect":"deny","action":"tool.shell_exec","when":{"department":"finance"}}]}
```

## Tasks

```text
GET/POST /api/v1/tasks
GET      /api/v1/tasks/{id}
GET      /api/v1/tasks/{id}/events
GET      /api/v1/tasks/{id}/approvals
POST     /api/v1/tasks/{id}/approve
POST     /api/v1/tasks/{id}/reject
POST     /api/v1/tasks/{id}/cancel
POST     /api/v1/tasks/{id}/retry
```

`POST /tasks` accepts `agent_id`, `prompt`, `mutating`, `tier_override`, `priority`, `success_criteria`, `max_attempts`. Use `Idempotency-Key` for safe retries.

## Workflow automation

```text
GET/POST /api/v1/workflows
GET/POST /api/v1/workflow-runs
GET      /api/v1/workflow-runs/{id}
POST     /api/v1/workflow-tick
GET/POST /api/v1/schedules
GET/POST /api/v1/event-rules
POST     /api/v1/events
POST     /api/v1/scheduler-tick
```

Use `Idempotency-Key` on `POST /api/v1/workflow-runs` when retrying a scheduled
or operator-triggered occurrence. Schedule and event dispatches derive a stable
occurrence key automatically. Task and workflow execution remain at-least-once
after lease expiry; external mutating consumers must deduplicate their own
side effects.

## Workspace projects / conversations

Workspace state is durable, tenant-scoped and shared by the Web/CLI/Windows
operator surfaces. A project groups conversations. A conversation stores ordered
messages and can reference existing task/workflow provenance without becoming a
second task scheduler or memory system.

Read endpoints require `workspace:read` and at least the `viewer` role:

```text
GET  /api/v1/workspaces/projects
GET  /api/v1/workspaces/projects/{id}
GET  /api/v1/workspaces/conversations
GET  /api/v1/workspaces/conversations/{id}
GET  /api/v1/workspaces/conversations/{id}/messages
```

List endpoints accept bounded query parameters. Projects support `q`, `status`,
`limit`, `offset`; conversations support `q`, `project_id`, `status`, `limit`,
`offset`. Search is literal substring matching rather than a SQL wildcard API.

Mutation endpoints require `workspace:write` and at least the `operator` role:

```text
POST /api/v1/workspaces/projects
POST /api/v1/workspaces/projects/{id}/rename
POST /api/v1/workspaces/projects/{id}/pin
POST /api/v1/workspaces/projects/{id}/archive
POST /api/v1/workspaces/conversations
POST /api/v1/workspaces/conversations/{id}/rename
POST /api/v1/workspaces/conversations/{id}/pin
POST /api/v1/workspaces/conversations/{id}/archive
POST /api/v1/workspaces/conversations/{id}/move
POST /api/v1/workspaces/conversations/{id}/messages
```

The external message endpoint accepts only `role=user`; assistant/system/tool
messages remain internal runtime outputs so a client cannot forge model/tool
history. Message ordering uses a durable per-conversation ordinal, not wall-clock
time alone. Artifact references are IDs, not host filesystem paths.

Conversation deletion uses the existing action-endpoint convention instead of a
new HTTP method and requires `workspace:delete` plus the `admin` role:

```text
POST /api/v1/workspaces/conversations/{id}/delete
```

Deletion is refused when `retention_policy=compliance_hold`. Project,
conversation and message ownership is constrained by `(tenant_id, id)` at both
the repository and database foreign-key layers, preventing cross-tenant project
or conversation attachment.

## Workspace context snapshots / compaction

Context snapshots are durable, tenant-scoped checkpoints over an existing
conversation. Source messages are never rewritten or deleted by snapshot or
compaction operations. Snapshot membership is ordered by durable conversation
ordinal and stores deterministic estimated-token accounting until provider-
reported usage is available at the execution boundary.

Context reads require `workspace:read` and at least the `viewer` role:

```text
GET /api/v1/workspaces/conversations/{id}/context-snapshots
GET /api/v1/workspaces/context-snapshots/{snapshot_id}
```

Creating a normal checkpoint requires `workspace:write` and at least the
`operator` role:

```text
POST /api/v1/workspaces/conversations/{id}/context-snapshots
```

Request fields are `model_id`, `context_ceiling_tokens`,
`compaction_threshold_tokens`, optional `message_ids`, optional `reason`, and
optional snapshot `id`. A normal checkpoint **does not accept `summary`**;
summary-bearing snapshots are reserved for the separately authorized `/compact`
operation. Message IDs must belong to the same tenant-scoped conversation.
Context ceilings and thresholds are bounded, and the threshold cannot exceed the
ceiling.

Explicit compaction is a separately authorized durable/cost-relevant operation
and requires `workspace:compact` plus at least the `operator` role:

```text
POST /api/v1/workspaces/conversations/{id}/compact
```

Compaction requires a non-empty `summary` and creates a new snapshot rather than
replacing history. Audit events record conversation/model/token/member metadata
and the summary SHA-256 digest, but not the raw summary text. This endpoint does
not grant provider/model authority by itself; provider-backed automatic
summarization remains subject to normal model policy and budget controls.

## Workspace commands

Server-authorized slash-command discovery and resolution for workspace
surfaces. Both endpoints require `workspace:read` and at least the `viewer`
role; the resolved payload reports whether the authenticated principal also
passes the command's own role/scope requirement:

```text
GET  /api/v1/workspaces/commands
POST /api/v1/workspaces/commands/resolve
```

`POST /commands/resolve` accepts `{"text": "<command>[ <argument>]"}` and
returns the matched command, its argument (when present), `available`,
`tenant_id` and `resolved: true`. An unrecognized command, or a command whose
role/scope requirement the principal does not satisfy, is rejected with 400/403
rather than executed. Command definitions live server-side; clients never
submit an executable body.

## Workspace grants

Operator-managed local filesystem grants bound worktree/tool execution to an
approved host root. Grant endpoints require `workspace:grant` and the `admin`
role:

```text
GET  /api/v1/workspaces/grants
POST /api/v1/workspaces/grants
POST /api/v1/workspaces/grants/{id}/disable
```

`POST /grants` accepts a grant definition (`root`, `read`, `write`, `commands`,
`network_policy`, `expires_at`); the server normalizes and validates the root
before persisting, and every upsert/disable is audited. `disable` refuses to
mutate an unknown grant (404) and is a durable, audited state transition. Grant
roots are canonicalized at grant time and revalidated at every worktree/tool
operation, so a later reconfiguration cannot widen an approved root.

## Task evidence sidecar

Read-only durable evidence projection for a completed task, used by
workspace/review surfaces. Requires `workforce:read` and at least the `viewer`
role:

```text
GET /api/v1/tasks/{id}/sidecar
```

Returns the tenant-scoped evidence bundle or `404 task_not_found`. The
projection is derived from the durable task record; it does not accept client
input and never exposes provider or storage credentials.

## Evaluation

```text
GET/POST /api/v1/evaluation-suites
POST     /api/v1/evaluation-runs
GET      /api/v1/evaluation-runs/{id}
POST     /api/v1/evaluation-tick
```

## Memory / artifacts

```text
GET/POST /api/v1/memories
GET      /api/v1/rag?q=...
POST     /api/v1/rag/reindex
GET/POST /api/v1/artifacts
GET/POST /api/v1/skills
```

Artifact POST body uses base64 payload because this API intentionally stays JSON-only in v3.

## FinOps / SLO

```text
GET/POST /api/v1/budgets
GET      /api/v1/chargeback?hours=24
GET      /api/v1/capacity?hours=24
GET      /api/v1/slo
POST     /api/v1/slo
POST     /api/v1/economics
```

## Identity / audit

```text
GET/POST /api/v1/tenants
GET/POST /api/v1/api-keys
POST     /api/v1/api-keys/{id}/revoke
GET      /api/v1/audit
GET      /api/v1/audit/verify
GET      /api/v1/tool-events
```

## MCP

`POST /mcp` accepts authenticated, tenant-scoped JSON-RPC 2.0 requests. Modern
`2026-07-28` messages require the following headers:

- `MCP-Protocol-Version: 2026-07-28`
- `Mcp-Method` exactly matching the JSON-RPC `method`
- `Mcp-Name` exactly matching `params.name` for `tools/call`
  (for `resources/read`, it mirrors `params.uri`)

Modern `params._meta` must contain matching
`io.modelcontextprotocol/protocolVersion` and an object-valued
`io.modelcontextprotocol/clientCapabilities`. Invalid protocol versions or
mismatched version metadata return HTTP 400 with a JSON-RPC `error` retaining
the original request `id`. A mismatched method/name header also fails closed.

`initialize` is a **legacy handshake** only; supported legacy versions are
`2025-11-25`, `2025-06-18`, and `2025-03-26`. For an unknown or modern
handshake proposal the server counter-offers `2025-11-25`. The older
`2024-11-05` HTTP+SSE transport is not implemented and is not advertised.
Modern clients should call `server/discover`.

Example:

```bash
curl --fail-with-body -sS https://workforce.example.com/mcp \
  -H "Authorization: Bearer $ZWORKFORCE_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2026-07-28" \
  -H "Mcp-Method: tools/call" \
  -H "Mcp-Name: cloudflare.references" \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"cloudflare.references","arguments":{},"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}}}}'
```

See [MCP.md](MCP.md) for discovery, initialize, complete examples and tool permissions.
