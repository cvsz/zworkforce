# zWorkforce Dashboard Realtime Control Packages Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add a tenant-safe live-update channel to the Python-served zWorkforce web dashboard and wire its control surface to live invalidation, reconnect, replay, and honest fallback states.

**Architecture:** The repository appends compact, allowlisted dashboard events to a durable SQLite/PostgreSQL table whenever existing durable task, audit, provider, usage, workflow, and automation transitions occur. The Python API exposes a bounded authenticated SSE stream whose cursor is durable and tenant-scoped. Dependency-free browser modules consume that stream with fetch, coalesce invalidations, refresh the existing dashboard through one API boundary, and show LIVE, RECONNECTING, POLLING, or STALE.

**Tech Stack:** Python 3.12+ standard-library HTTP server, the existing SQLite/PostgreSQL repository abstraction, dependency-free browser ES modules, Node 22 node:test for pure browser-module tests, and the existing Python unittest suite.

## Global Constraints

- Preserve tenant isolation, server-side secrets, bounded execution, explicit mutation authorization, and durable state transitions.
- Browser/static code never receives provider, storage, database, voice, or proxy credentials.
- Durable state changes go through repository methods; the realtime stream is read-only and invalidation-only.
- Preserve SQLite compatibility and PostgreSQL placeholder/schema translation.
- Do not put API keys or cursor-bearing credentials in URLs; the browser stream sends Authorization and X-Tenant-ID request headers.
- Event payloads contain only allowlisted status metadata; never send prompts, results, secrets, raw provider errors, storage URIs, or unredacted tool arguments.
- Existing REST routes and mutation idempotency behavior remain compatible.
- Every implementation change gets a failing test first, then the smallest passing implementation.
- Validate with python -m compileall -q zworkforce tests, PYTHONPATH=. python -m unittest discover -s tests -v, and zworkforce doctor; run tests/test_v3_postgres.py against a real PostgreSQL service when its URL is available.

---

### Task 1: Add durable dashboard event storage and safe repository emission

**Files:**

- Create: zworkforce/db_schema_realtime.py
- Create: zworkforce/db_realtime.py
- Modify: zworkforce/db.py
- Modify: zworkforce/db_tasks.py
- Modify: zworkforce/db_governance.py
- Modify: zworkforce/db_finops.py
- Modify: zworkforce/db_automation.py
- Test: tests/test_v3_realtime.py
- Test: tests/test_v3_postgres.py

**Interfaces:**

- DashboardEventMixin.append_dashboard_event(tenant_id: str, event_type: str, resource_type: str, resource_id: str, payload: dict[str, Any] | None = None) -> int
- DashboardEventMixin.list_dashboard_events(tenant_id: str, after_id: int = 0, limit: int = 100) -> list[dict[str, Any]]
- DashboardEventMixin.dashboard_event_bounds(tenant_id: str) -> dict[str, int | None]
- DashboardEventMixin.dashboard_event_cursor(tenant_id: str) -> int
- DashboardEventMixin.prune_dashboard_events(older_than: str, tenant_id: str | None = None) -> int
- DashboardEventMixin._append_dashboard_event_cursor(connection: Any, tenant_id: str, event_type: str, resource_type: str, resource_id: str, payload: dict[str, Any] | None = None) -> int for same-transaction repository callers.

- [ ] Step 1: Write failing repository tests.

Create two tenants, append events for both, and assert:

    event_id = db.append_dashboard_event(
        "default", "task.changed", "task", "task-1",
        {"summary": {"status": "running", "attempt": 1, "secret": "must-drop"}},
    )
    assert event_id > 0
    assert db.dashboard_event_cursor("default") == event_id
    assert db.list_dashboard_events("default")[0]["payload"] == {
        "summary": {"status": "running", "attempt": 1}
    }
    assert db.list_dashboard_events("other") == []

Also test bounded limits, negative cursor rejection, stale bounds after pruning, and that task_event() and audit() create events without persisting raw prompt, result, token, password, or error fields.

- [ ] Step 2: Run the focused tests and verify the expected red failure.

Run:

    PYTHONPATH=.:tests python -m unittest tests.test_v3_realtime -v

Expected: FAIL because DashboardEventMixin and dashboard_events2 do not exist.

- [ ] Step 3: Implement the schema and repository mixin.

Create dashboard_events2 with id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id, event_type, resource_type, resource_id, payload_json, and created_at, plus an index on tenant_id,id. Keep the SQL compatible with the existing PostgreSQL schema translator.

Implement allowlisted payload sanitization. Store and return decoded payload data, bound event types and resource fields to 128 characters, reject empty tenant/resource identifiers, clamp list limits to 1–100, and reject negative or unsafe cursor values. Implement dashboard_event_bounds() using MIN(id) and MAX(id) for the tenant. prune_dashboard_events() must use a static query and only delete by timestamp, optionally scoped to one tenant.

Add DashboardEventMixin to the Database inheritance list and execute its schema in Database._initialize_schema() after the existing common schema. Update only the repository schema version constant required by the new table.

- [ ] Step 4: Make task and audit emission use the same repository transaction.

In task_event(), insert the task event and then call _append_dashboard_event_cursor() on the same connection with a safe task.changed summary containing only status, attempt, outcome_status, and outcome_score when present.

In audit(), insert the tamper-evident audit row and then append one mapped dashboard event on the same connection. The event summary may contain only the action name; never copy the audit details object wholesale.

Add direct usage.changed, workflow.changed, schedule.changed, event.changed, evaluation.changed, budget.changed, slo.changed, memory.changed, skill.changed, and artifact.changed emission to repository transitions that can run outside API audit wrappers. Pass an optional tenant ID through provider calls so provider health changes emit tenant-scoped provider.changed events without a global tenant escape hatch. Provider event payloads contain only provider name, availability, and latency.

- [ ] Step 5: Run focused tests and the PostgreSQL contract test.

Run:

    PYTHONPATH=.:tests python -m unittest tests.test_v3_realtime -v
    PYTHONPATH=.:tests python -m unittest tests.test_v3_postgres -v

Expected: focused SQLite tests pass; PostgreSQL tests pass when ZWORKFORCE_TEST_POSTGRES_URL is configured or are explicitly skipped by the existing decorator when it is not.

- [ ] Step 6: Commit the repository event slice.

    git add zworkforce/db_schema_realtime.py zworkforce/db_realtime.py zworkforce/db.py zworkforce/db_tasks.py zworkforce/db_governance.py zworkforce/db_finops.py zworkforce/db_automation.py tests/test_v3_realtime.py tests/test_v3_postgres.py
    git commit -m "feat: add durable dashboard events"

### Task 2: Add the authenticated bounded SSE endpoint and safe static module serving

**Files:**

- Create: zworkforce/realtime.py
- Modify: zworkforce/api.py
- Modify: tests/test_api_v2.py
- Create: tests/test_v3_realtime_api.py
- Modify: tests/test_static_assets.py
- Modify: pyproject.toml

**Interfaces:**

- parse_event_cursor(value: str | None) -> int
- format_dashboard_event(event: dict[str, Any]) -> bytes
- format_dashboard_heartbeat(cursor: int, created_at: str) -> bytes
- stream_dashboard_events(db, tenant_id: str, after_id: int, write: Callable[[bytes], None], is_closed: Callable[[], bool] | None = None, *, max_seconds: float = 20.0, poll_seconds: float = 0.5, heartbeat_seconds: float = 5.0) -> int

- [ ] Step 1: Write failing protocol and endpoint tests.

Test cursor parsing, SSE output, heartbeat output, malformed cursor rejection, unauthorized access, tenant isolation, replay after a cursor, and the endpoint Content-Type and Cache-Control headers. Use the existing App plus ThreadingHTTPServer pattern. For the bounded stream test, pass a short test-only duration or call the pure formatter/stream helper with injected timing.

Test static module requests for /dashboard/core/realtime.js and /dashboard/packages/realtime/index.js, plus an encoded traversal path such as /dashboard/%2e%2e/api.py.

- [ ] Step 2: Run the focused API tests and verify the expected red failure.

    PYTHONPATH=.:tests python -m unittest tests.test_v3_realtime_api -v

Expected: FAIL because the endpoint, protocol helpers, and nested static files do not exist.

- [ ] Step 3: Implement pure SSE helpers and bounded stream behavior.

Implement parse_event_cursor() with a safe integer range and clear ValueError messages. Implement format_dashboard_event() with an integer id, event name, and one compact JSON data line. Implement format_dashboard_heartbeat() as a named heartbeat event with only cursor and server timestamp.

Implement stream_dashboard_events() as a bounded polling loop: inspect tenant-scoped event bounds, emit resync.required for a cursor older than the retained minimum, replay up to 100 events, emit an immediate heartbeat, poll at a bounded interval, emit heartbeats when idle, flush through the supplied writer, and return the final cursor. Catch broken-pipe/reset errors at the handler boundary so disconnected browsers do not produce 500 responses or noisy tracebacks.

- [ ] Step 4: Add the protected API route.

In _get_api(), handle /api/v1/dashboard/events before normal JSON dashboard routes. Reuse _principal("viewer", "workforce:read"), read X-ZWorkforce-Event-Cursor, send text/event-stream; charset=utf-8, Cache-Control: no-store, X-Accel-Buffering: no, and Connection: close, then invoke the bounded stream helper. Never accept a cursor or credential from a query string. A stale cursor response remains a valid SSE stream and closes after resync.required.

- [ ] Step 5: Harden nested static asset serving.

Add a narrowly scoped /dashboard/ static route and extend the existing allowlist for the already referenced Z.A.R.V.I.S. HUD assets. Resolve URL-encoded paths beneath app.static, reject absolute paths and any .. component after URL decoding, serve only regular files, and select MIME types by a fixed extension map. Do not turn the handler into an unrestricted filesystem server.

Update pyproject.toml package data to include nested dashboard JavaScript/CSS files. Add static tests asserting no server-secret configuration names appear in the new modules.

- [ ] Step 6: Run focused API/static tests and commit.

    PYTHONPATH=.:tests python -m unittest tests.test_v3_realtime_api tests.test_api_v2 tests.test_static_assets -v
    git add zworkforce/realtime.py zworkforce/api.py tests/test_v3_realtime_api.py tests/test_api_v2.py tests/test_static_assets.py pyproject.toml
    git commit -m "feat: expose authenticated dashboard event stream"

### Task 3: Implement the dependency-free browser realtime core and package

**Files:**

- Create: zworkforce/static/dashboard/core/realtime.js
- Create: zworkforce/static/dashboard/core/registry.js
- Create: zworkforce/static/dashboard/packages/realtime/index.js
- Create: zworkforce/static/dashboard/bootstrap.js
- Create: tests/dashboard_realtime.test.mjs

**Interfaces:**

- createRealtimeClient(options) -> { start(), stop(), restart(), subscribeStatus(listener), subscribeEvents(listener), getState(), getCursor() }
- parseSseBlock(block: string) -> object | null
- createPackageRegistry(definitions, onInvalidate) -> { dispatch(event), list(), destroy() }
- mountRealtimePackage({ root, client }) -> { destroy() }
- createDashboardRealtime(options) -> { start(), stop(), restart(), destroy() }

- [ ] Step 1: Write failing Node tests for parsing and state behavior.

Use node:test with injected fetch, response bodies, clock/sleep, and random functions. Add these six test cases with real assertions: auth and tenant headers are present while the URL query is empty; a valid heartbeat changes state to LIVE and updates the cursor; duplicate task events result in one registry invalidation; resync.required is delivered and its cursor is used for the next request; stop aborts the active request and emits offline; and repeated fetch failures emit RECONNECTING followed by POLLING.

- [ ] Step 2: Run the browser tests and verify the expected red failure.

    node --experimental-default-type=module --test tests/dashboard_realtime.test.mjs

Expected: FAIL because the browser modules do not exist.

- [ ] Step 3: Implement the SSE parser and transport state machine.

Implement line-based SSE parsing with id, event, and multiple data lines. Use fetch with Authorization, X-Tenant-ID, X-ZWorkforce-Event-Cursor, and Accept: text/event-stream headers. Reject non-2xx responses, never append credentials to the endpoint URL, update the cursor only from validated event IDs, and ignore malformed JSON event blocks safely.

Use capped exponential backoff with jitter. Set LIVE only after a valid heartbeat or event arrives. After three consecutive transport failures, expose POLLING while continuing slow reconnect attempts. Reset backoff after a live heartbeat. restart() aborts the previous request, resets the cursor for a changed tenant/session, and avoids duplicate loops.

- [ ] Step 4: Implement package registry and realtime status package.

The registry maps event types to package IDs overview, workforce, governance, automation, finops, knowledge, and zarvis and invokes one debounced invalidation callback. Unknown events are ignored. The realtime package updates #realtimeDot, #realtimeText, and an accessible status region using LIVE, RECONNECTING, POLLING, and STALE copy. It renders the word Realtime only for LIVE.

- [ ] Step 5: Run browser tests and commit.

    node --experimental-default-type=module --test tests/dashboard_realtime.test.mjs
    git add zworkforce/static/dashboard tests/dashboard_realtime.test.mjs
    git commit -m "feat: add dashboard realtime browser package"

### Task 4: Wire the realtime package into the existing dashboard and validate live behavior

**Files:**

- Modify: zworkforce/static/index.html
- Modify: zworkforce/static/app.js
- Modify: zworkforce/static/styles.css
- Modify: tests/test_static_assets.py
- Modify: tests/test_api_v2.py
- Modify: docs/ARCHITECTURE.md

**Interfaces:**

- app.js creates the dashboard realtime runtime after existing DOM handlers are ready.
- refresh() remains the authoritative full snapshot path during migration; realtime events schedule one debounced refresh and carry package IDs for later per-package extraction.
- Connection changes close the current stream, clear the cursor, refresh the snapshot, and start a new tenant-scoped stream.

- [ ] Step 1: Write failing static integration assertions.

Extend static tests to require the realtime status element, dashboard bootstrap module reference, stream endpoint string, state labels, and a sessionStorage-only connection boundary. Assert that the dashboard no longer contains presentation-only Realtime or Active claims for services that have no API-backed evidence.

- [ ] Step 2: Run static tests and verify the expected red failure.

    PYTHONPATH=.:tests python -m unittest tests.test_static_assets -v

Expected: FAIL because the status markup, bootstrap wiring, and CSS do not exist.

- [ ] Step 3: Add the live status UI and bootstrap integration.

Add a topbar live-update indicator with role=status and aria-live=polite. Load the compatibility bootstrap after the existing voice/HUD scripts or use a dynamic import from app.js so the current classic script remains compatible during migration. On authenticated connect, instantiate createDashboardRealtime() with the current session getter and a debounced refresh callback. On disconnect or tenant change, stop and restart the client with a fresh cursor.

Use a single timer for event-triggered refreshes. Do not start an event stream without a nonempty API key. If the stream reports POLLING, use the existing refresh path at a bounded interval and stop that interval when LIVE returns. If a refresh fails, show STALE with the existing error banner rather than claiming the dashboard is current.

- [ ] Step 4: Make status styling accessible and truthful.

Add compact status styles for all four states, preserve keyboard focus outlines, and honor prefers-reduced-motion. Do not animate a state that has not been confirmed by a heartbeat. Keep status text safe for untrusted event values; event descriptions come from fixed client-side labels.

- [ ] Step 5: Remove hardcoded infrastructure claims from the live path.

Change the telemetry sidebar and integration cards so they are either backed by existing API data or explicitly labeled unavailable/not configured. The realtime indicator must not be used as a proxy for provider, voice, storage, queue, or external integration provisioning.

- [ ] Step 6: Run focused integration tests and commit.

    PYTHONPATH=.:tests python -m unittest tests.test_static_assets tests.test_api_v2 tests.test_v3_realtime_api -v
    git diff --check
    git add zworkforce/static/index.html zworkforce/static/app.js zworkforce/static/styles.css tests/test_static_assets.py tests/test_api_v2.py docs/ARCHITECTURE.md
    git commit -m "feat: wire live dashboard status and refreshes"

### Task 5: Full validation and live local smoke test

**Files:**

- No additional files are expected; if a validation failure identifies a regression, change only the smallest file needed to correct that failure.
- Test: existing repository suite and the new realtime tests.

- [ ] Step 1: Run the complete local gates.

    python -m compileall -q zworkforce tests
    PYTHONPATH=. python -m unittest discover -s tests -v
    zworkforce doctor

- [ ] Step 2: Run PostgreSQL integration against the operator-provided service.

When ZWORKFORCE_TEST_POSTGRES_URL is configured, run:

    PYTHONPATH=.:tests python -m unittest tests.test_v3_postgres -v

Retain the output without secrets. If the URL is absent, record that PostgreSQL runtime evidence is unavailable; do not claim PostgreSQL realtime completion from SQLite tests.

- [ ] Step 3: Run a local live smoke test.

Start the local server with a development key, connect the dashboard, dispatch a task, and observe the status transition from LIVE without clicking Refresh. Stop the stream or make the endpoint unavailable and verify RECONNECTING, POLLING, and STALE; restore it and verify LIVE. Repeat with two tenants and confirm the browser receives no event from the other tenant.

- [ ] Step 4: Inspect the shipped artifact boundary.

Verify nested dashboard modules are included in the built package, no static module contains forbidden secret configuration names, no runtime path contains shell=True, and the current unrelated worktree changes remain untouched.

- [ ] Step 5: Commit only final fixes and report evidence boundaries.

Use a Conventional Commit only for final realtime fixes. Report separately:

- repository files and commits changed;
- focused and full local checks;
- PostgreSQL result or unavailable external prerequisite;
- live local browser evidence;
- remaining production ingress, provider, storage, observability, signing, and release-governance evidence that this work does not prove.
