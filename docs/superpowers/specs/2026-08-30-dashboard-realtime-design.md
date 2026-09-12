# zWorkforce Dashboard Realtime Control Packages

**Status:** Approved for implementation by the explicit request to “do all for live”.

## Goal

Make the Python-served zWorkforce web dashboard live across its control packages.
Operators should see tenant-scoped task, approval, automation, provider, FinOps,
governance, knowledge, and voice-related state changes without manual refresh,
while the UI remains honest when the live channel is unavailable.

## Context

The current dashboard is a large dependency-free static surface under
`zworkforce/static/`, served by the Python control plane. `app.js` owns the API
client, rendering, task mutations, ProMeta installation, slash commands, and
Z.A.R.V.I.S. voice behavior. The API already authenticates every protected
request, resolves the tenant from the authenticated principal and
`X-Tenant-ID`, and exposes read and mutation endpoints for the dashboard
domains.

The current surface refreshes by issuing a batch of HTTP requests and contains
several presentation-only service/integration cards. Those cards must not be
used as evidence of live infrastructure. The realtime design therefore treats
the server-side repository and API as authoritative and uses the browser live
channel only as a low-latency invalidation mechanism.

## Scope

### In scope

- A tenant-scoped durable dashboard event feed compatible with SQLite and
  PostgreSQL.
- An authenticated streaming HTTP endpoint for browser consumers.
- Cursor-based reconnect, replay, stale-cursor resynchronization, heartbeat,
  bounded backoff, and bounded polling fallback.
- A dependency-free browser module layout under `zworkforce/static/dashboard/`.
- A first-class `realtime` dashboard package that exposes connection state and
  activity while supplying events to domain packages.
- Live invalidation and refresh wiring for overview, workforce, governance,
  automation, FinOps, knowledge, and Z.A.R.V.I.S. packages.
- Safe event payloads, UI capability gating, accessibility, and regression
  tests.

### Out of scope

- A new frontend framework or Node build pipeline.
- Browser-side provider, database, storage, voice, or proxy credentials.
- A second mutation API or client-side authorization authority.
- WebSocket transport for dashboard updates. Z.A.R.V.I.S. voice retains its
  existing short-lived ticket and WebSocket contract.
- Claims that external queues, observability systems, providers, or integration
  services are provisioned merely because a dashboard package exists.

## Package architecture

The current `/` route and `app.js` URL remain compatibility entry points. The
static surface is split into explicit browser modules:

```text
zworkforce/static/
├── index.html
├── app.js                         # compatibility bootstrap during migration
└── dashboard/
    ├── bootstrap.js               # package registration and startup
    ├── core/
    │   ├── api.js                 # authenticated API client
    │   ├── session.js             # sessionStorage connection state
    │   ├── permissions.js         # UI affordance metadata only
    │   ├── registry.js            # package lifecycle
    │   ├── refresh.js             # refresh/invalidation scheduling
    │   └── realtime.js             # authenticated event transport
    ├── ui/
    │   ├── status.js
    │   ├── metrics.js
    │   ├── table.js
    │   ├── drawer.js
    │   ├── dialog.js
    │   └── empty-state.js
    └── packages/
        ├── overview/
        ├── realtime/
        ├── workforce/
        ├── governance/
        ├── automation/
        ├── finops/
        ├── knowledge/
        └── zarvis/
```

### Shell responsibilities

The shell owns the page frame, connection form, tenant context, top-level
health, global notification region, package registration, navigation/focus
management, and package lifecycle. It stores the API key and tenant only in
`sessionStorage`, attaches `Authorization` and `X-Tenant-ID` through the shared
API client, and clears/restarts all package state when the connection changes.

The shell never infers authorization from a hidden UI control. The server
remains authoritative. A future read-only session descriptor may improve
affordance rendering, but a missing or stale descriptor must not grant access.

### Domain package responsibilities

Each package exports a manifest and lifecycle methods with this shape:

```js
{
  id: "workforce",
  label: "Workforce",
  required: { role: "viewer", scope: "workforce:read" },
  mount(root, context),
  refresh(reason),
  unmount()
}
```

`context` contains only shared browser services: `api`, `session`, `realtime`,
`refresh`, `permissions`, `ui`, and `notify`. Packages do not call `fetch`, read
credentials, or mutate another package's DOM. Cross-package coordination uses
named invalidation events and explicit refresh requests.

The package map is:

| Package | Authoritative surfaces | Live invalidation topics |
| --- | --- | --- |
| `overview` | `/health`, `/ready`, `/api/v1/overview`, providers, recommendations, SLO status | `task.changed`, `provider.changed`, `finops.changed`, `slo.changed` |
| `realtime` | authenticated stream connection and activity feed | all safe dashboard events and `heartbeat` |
| `workforce` | tasks, task events, approvals, dispatch and bounded actions | `task.changed`, `approval.required` |
| `governance` | policies, audit, API keys, tools, tenant context | `audit.appended`, `policy.changed`, `key.changed`, `tenant.changed` |
| `automation` | workflows, workflow runs, schedules, event rules, evaluations | `workflow.changed`, `schedule.changed`, `event.changed`, `evaluation.changed` |
| `finops` | models, budgets, chargeback, capacity, SLOs, recommendations | `provider.changed`, `usage.changed`, `budget.changed`, `slo.changed` |
| `knowledge` | memories, RAG, skills, artifacts | `memory.changed`, `skill.changed`, `artifact.changed` |
| `zarvis` | voice availability/session and existing HUD | `voice.changed`, plus the existing voice WebSocket events |

Integration-specific cards are rendered only when a server-backed capability
descriptor exists. A static label such as `Realtime`, `Active`, or `Protected`
is not evidence and must not be emitted by the shell.

## Realtime server contract

### Durable event table

Add a repository-owned `dashboard_events2` table to the common schema. It has:

- an auto-incrementing/big-serial `id` used as the opaque reconnect cursor;
- `tenant_id` with tenant isolation;
- `event_type`, `resource_type`, and `resource_id`;
- a small `payload_json` containing only allowlisted status metadata;
- `created_at`.

The table is append-only from application code and has a tenant/cursor index.
Retention is bounded by a repository method that removes only events older than
the configured retention horizon; an old cursor produces `resync.required`
instead of silently losing changes.

The repository exposes focused methods:

```python
append_dashboard_event(
    tenant_id: str,
    event_type: str,
    resource_type: str,
    resource_id: str,
    payload: dict[str, Any] | None = None,
) -> int

list_dashboard_events(
    tenant_id: str,
    after_id: int = 0,
    limit: int = 100,
) -> list[dict[str, Any]]

dashboard_event_cursor(tenant_id: str) -> int
```

Event creation is wired to existing durable transitions, not browser actions:

- `task_event()` emits `task.changed` with status, attempt, outcome status and
  score only.
- `audit()` emits a mapped resource event using action/target identifiers and
  allowlisted detail keys only.
- workflow, schedule, event-rule, evaluation, budget, SLO, memory, skill,
  artifact, and provider repository transitions emit their domain event when
  they do not already pass through `audit()`.
- high-frequency task heartbeats do not create an unbounded browser event
  stream; the task detail view refreshes them on a bounded cadence.

Event insertion is part of the same repository transaction as the state change
where practical. If an event is advisory and emitted after a successful state
transition, a subsequent package refresh remains authoritative and no mutation
depends on event delivery.

### Event payload

The wire format is SSE-compatible:

```text
id: 1842
event: task.changed
data: {"resource_type":"task","resource_id":"…","summary":{"status":"running","attempt":1}}

```

The server never sends prompts, task results, raw provider errors, API-key
metadata, storage URIs, database details, credentials, or unredacted tool
arguments in the event payload. The client uses the identifiers to re-fetch
authorized records through the normal API.

### Streaming endpoint

Add an authenticated `GET /api/v1/dashboard/events` endpoint. It requires the
same viewer/workforce read authorization as the read-only dashboard APIs and
resolves the tenant through the existing principal path. The client supplies a
cursor in `X-ZWorkforce-Event-Cursor`; no credential is placed in a URL.

The response uses `text/event-stream`, `Cache-Control: no-store`, a bounded
heartbeat interval, and a server-side maximum connection duration. The server
replays events after the cursor, emits `resync.required` when the cursor is no
longer retained, and then closes cleanly. A database notification mechanism may
wake a waiting connection, but durable cursor queries remain the correctness
source for both SQLite and PostgreSQL.

### Client transport states

The transport exposes:

```text
LIVE          heartbeat received and cursor current
RECONNECTING  connection lost; bounded backoff in progress
POLLING       streaming unavailable; bounded HTTP refresh active
STALE         refresh could not establish a current view
```

The UI shows `Realtime` only in `LIVE`. Reconnect uses capped exponential
backoff with jitter and resets after a successful heartbeat. A full refresh is
debounced so a burst of task events does not create a request storm. A stream
cursor is scoped to the current tenant/session and discarded when either
changes.

## Data flow

```text
Durable repository transition
        |
        +--> state table / audit or task event
        +--> dashboard_events2 (safe summary + cursor)
                              |
                 authenticated streaming GET
                              |
                     dashboard/core/realtime.js
                              |
             coalesced invalidation by domain/resource
                              |
       package refresh through dashboard/core/api.js
                              |
                    authoritative tenant data
```

The stream is an invalidation channel, not a cache and not a command channel.
If a package receives an unknown event, it ignores the event safely and keeps
its current data. If it receives `resync.required`, it clears stale markers,
fetches a complete package snapshot, and resumes from the returned cursor.

## Security and failure behavior

- Authentication, role checks, scopes, tenant resolution, rate limits, and
  request IDs use the existing API path.
- The event endpoint cannot be accessed without a valid viewer/workforce
  principal and cannot select another tenant outside the existing
  `resolve_tenant` rules.
- Cursor values are parsed as bounded integers; malformed, negative, or
  cross-session cursors do not disclose event data.
- Event payloads are allowlisted and redacted at the repository boundary.
- Browser code has no provider/storage/database credentials and no secret-bearing
  event subscription URL.
- Mutations remain deny-by-default, server-authorized, durable, and idempotent.
- Stream disconnects never roll back or replay a mutation. Re-fetching is safe.
- A failing stream must not mask an API failure; packages show the last-known
  timestamp and an actionable stale/degraded message.
- Reduced-motion users receive the same state information without animated
  effects.

## Testing and acceptance criteria

### Backend

- SQLite schema initialization creates the event table and remains compatible
  with existing databases.
- PostgreSQL schema initialization creates the equivalent table and index.
- Events are tenant-filtered; a tenant cannot observe another tenant's event,
  even when cursors overlap.
- `task_event()` and `audit()` produce safe events with no secret or raw content.
- Cursor replay, bounded limits, stale-cursor resync, malformed cursor, and
  retention behavior are covered.
- The stream endpoint enforces authentication, scope, tenant selection, content
  type, heartbeat, and clean disconnect behavior.
- Existing required compile, unit, doctor, and PostgreSQL checks remain green.

### Browser

- A live event refreshes only the owning package after debounce.
- Duplicate/burst events coalesce into one refresh.
- Tenant or credential changes close the old stream and discard its cursor.
- Reconnect transitions through `RECONNECTING`; failed transport enters
  `POLLING`; inability to refresh enters `STALE`.
- `Realtime` is rendered only for a confirmed live state.
- Keyboard, focus, screen-reader status, and reduced-motion behavior are
  covered by static/browser tests.
- Static asset checks continue to reject server-secret configuration names.

## Migration and release boundaries

1. Add repository event storage and focused backend tests.
2. Add the authenticated endpoint and stream tests.
3. Add the core browser modules and realtime status surface.
4. Move current dashboard reads/mutations behind the shared API client and
   package lifecycle without changing public API routes.
5. Remove or replace presentation-only “live” integration claims.
6. Run the repository validation commands and inspect the rendered dashboard at
   desktop and narrow mobile widths.

This is repository functionality only. It does not prove live production
ingress, provider availability, PostgreSQL operations, external storage,
observability delivery, or release-governance completion.
