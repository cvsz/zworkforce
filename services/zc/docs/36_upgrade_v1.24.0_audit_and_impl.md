# v1.24.0 audit cycle — cross-product gap findings + implementation prompts

Per the explicit ask this cycle ("think deeper, search all zAICoder
products"), this audit deliberately widened past Managed Agents (the
last three cycles) and Admin/Auth (v1.23.0) to re-check
platform.zc.com/docs/en/release-notes/overview end to end, plus the
Web fetch tool, Web search tool, Code execution tool, and Analytics API
reference pages it points to. Four real, buildable gaps found; a fifth
candidate (the zAICoder Enterprise Analytics API) confirmed real but
deliberately left undocumented-as-built — see the non-gap note below.

## Finding 1 — Server tool version drift: `code_execution_20260521`, `web_search_20260318`, `web_fetch_20260318`

**What it is:** Three tool-version bumps that shipped together (June 11,
2026 per the release notes), all GA with no beta header:
- `code_execution_20260521` discloses the sandbox's 90-second per-cell
  wall-clock limit in the tool's own description, so zAICoder budgets
  long-running cells instead of writing one loop that times out.
- `web_search_20260318` and `web_fetch_20260318` add a
  `response_inclusion` parameter (currently one documented value,
  `"excluded"`) that drops a *consumed* result's nested
  `server_tool_use`/`*_tool_result` block pair from the API response
  entirely — only meaningful when the result was consumed by a
  `code_execution` call in the same turn (the programmatic-tool-calling
  pattern), so it saves real output-token cost in agentic loops that
  don't need the raw page/search content echoed back to the client.

**Why it's a gap:** `zc_tools.py`'s own `SERVER_TOOLS` dict was
still on `code_execution_20260120` (the v1.22.0 bump) and
`web_search_20260209` — both real versions, just one bump behind each.
`web_fetch` was worse: still `web_fetch_20250124`, three versions
behind current, and behind even the *retired* `web_fetch_20250910`
`zc_tools.py`'s own `RETIRED_TOOL_VERSIONS` table already flags as
superseded. `zc_search.py` was worse still — its own separate
`WEB_SEARCH_TOOL`/`WEB_FETCH_TOOL` constants had never been bumped at
all (`web_search_20250305`, `web_fetch_20250124`), meaning none of the
version-tracking work `zc_tools.py` has done over several cycles
ever propagated to this sibling module. Grepped for `response_inclusion`
across the tree first: zero matches anywhere.

**Priority: 🟠 P1.** Real token-cost savings for any programmatic-tool-
calling workflow (a pattern this codebase already supports via
`zc_tools.py`'s `allowed_callers`), and the `zc_search.py` drift
in particular means that module's users get three-version-old tool
behavior with no way to opt into anything newer.

## Finding 2 — Managed Agents memory listing (`agent-memory-2026-07-22`)

**What it is:** `GET /v1/memory_stores/{id}/memories` — listing the
individual memory entries inside a memory store (distinct from
`create_memory_store()`, which only creates the store itself). Sending
the new `agent-memory-2026-07-22` beta header changes this endpoint's
behavior in three ways: results come back in a stable, server-defined
order and `order_by`/`order` are ignored; `depth` only accepts `0`, `1`,
or omitted (anything else 400s); and `path_prefix` must end with `/`
and matches whole path segments instead of an arbitrary substring. Page
cursors issued under the old (`managed-agents-2026-04-01`) list
behavior aren't valid once you switch headers, so callers restart from
the first page when adopting it. On July 22, 2026 the older header
adopts this same behavior anyway.

**Why it's a gap:** `zc_agents_sdk.py` implements
`create_memory_store()` and mounts a store into a session as a resource,
but has no method that lists what's actually *inside* a store at all —
first grep for `memories` (the endpoint's own path segment): zero
matches. Second, differently-worded grep for `path_prefix|order_by`:
also zero matches.

**Priority: 🟠 P1.** Without this, a memory store built up over many
Dreaming/Outcome/session runs is a black box from wire's side — the
only way to see what's in one is to mount it into a new session and ask
the agent to describe it.

## Finding 3 — API key `expires_at` not surfaced (Admin API)

**What it is:** The Admin API's existing `GET /api_keys` /
`GET /api_keys/{id}` endpoints now report each key's expiration in an
`expires_at` field (creation-time expiration is a Console-UI-only
setting per the same release note — there still is no create-key API
endpoint, so `cmd_admin_create_key()`'s existing explanation is correct
and unchanged).

**Why it's a gap:** `cmd_admin_list_keys()` only prints `id`, `name`,
and `status` — `expires_at` is silently dropped even though
`list_api_keys()`'s underlying response already contains whatever the
API returns. First grep for `expires_at` in the tree: zero matches.

**Priority: 🟡 P2.** Small, read-only, additive — surfacing a field
that's already in the response body costs nothing and closes a real
"key is about to expire and nobody's watching" blind spot.

## Finding 4 — zAICoder Analytics API

**What it is:** `GET /v1/organizations/usage_report/zc_code` — a
dedicated Admin-API endpoint (same Admin API key as the existing Usage
& Cost API) returning one record per user per day: session counts,
lines of code added/removed, commits/PRs created through zAICoder,
per-editing-tool accept/reject counts, and a per-model token/cost
breakdown. Cursor-paginated via `starting_at` + `page`.

**Why it's a gap:** `zc_admin_api.py` already implements the
sibling org-wide Usage & Cost API but has no code path for this
zAICoder-Code-specific report — first grep for `zc_code` (the
endpoint's own path segment) in `zc_admin_api.py`: zero matches.

**Priority: 🟡 P2.** Same auth, same module, same client class as work
already done — low-cost addition, and the natural companion to the
Usage/Cost reporting this module already owns.

## Non-gap checked this cycle, deliberately not built — zAICoder Enterprise Analytics API

Nine endpoints (user activity, org-level daily/weekly/monthly active
users, project/skill/connector adoption, per-user cost) genuinely absent
from the tree — but this is a structurally different, larger surface
than every other Admin-API feature `zc_admin_api.py` owns: it
authenticates with a separate **Analytics API key** (created in
zc.ai by an Enterprise org's Primary Owner, scoped
`read:analytics`), not the Admin API key every existing method in that
module takes. Bolting a second, incompatible auth-key type onto
`AdminApiClient` — or forking a whole parallel client class — for nine
endpoints with no expressed use case yet is exactly the kind of
speculative scope the methodology says to defer (same call as
Multiagent orchestration in v1.20.0, revisited only once a concrete
wire use case existed). Recorded here so a future cycle doesn't
re-flag it as newly discovered, and doesn't accidentally build it into
`AdminApiClient` in a way that would need reworking once it is built.

---

## Implementation prompts

### Prompt 1 — Server tool version bumps (P1)

> Bump `zc_tools.py`'s `SERVER_TOOLS` defaults to
> `code_execution_20260521`, `web_search_20260318`, and
> `web_fetch_20260318`; add corresponding entries to
> `RETIRED_TOOL_VERSIONS` for the versions being superseded
> (`code_execution_20260120`, `web_search_20260209`, plus fold in the
> already-known-stale `web_fetch_20250124`/`web_fetch_20250910` chain
> pointing at `web_fetch_20260318` now). Add an optional
> `response_inclusion: Optional[str] = None` parameter wherever
> `web_search`/`web_fetch` tool dicts are built in `zc_tools.py`,
> included in the tool dict only when given (`"excluded"` is the only
> currently-documented value; pass through whatever string is given
> rather than validating an enum, since the docs only promise this one
> value today but may add more).
>
> Also fix the `zc_search.py` drift: bump its own separate
> `WEB_SEARCH_TOOL`/`WEB_FETCH_TOOL` constants to the same new versions,
> and thread an optional `response_inclusion` param through
> `SearchCoder.search()` the same way.
>
> Update `zc_code_exec.py`'s `DEFAULT_CODE_EXEC_VERSION` to
> `code_execution_20260521` (keep the existing pin-an-older-version
> mechanism from v1.22.0 working unchanged for
> `code_execution_20250522`/`code_execution_20260120`).
>
> Tests: `SERVER_TOOLS` defaults updated; `RETIRED_TOOL_VERSIONS` has
> entries for the newly-superseded versions; `response_inclusion` is
> included in the built tool dict when given and omitted when not
> (regression check) in both `zc_tools.py` and `zc_search.py`;
> `zc_code_exec.py`'s new default sends no beta header (same check
> as the v1.22.0 tests, just against the new version string).

### Prompt 2 — Managed Agents memory listing (P1)

> Add to `ManagedAgentsClient`:
> ```python
> def list_memories(self, memory_store_id: str, path_prefix: Optional[str] = None,
>                    depth: Optional[int] = None, limit: int = 50,
>                    page: Optional[str] = None) -> dict
> ```
> Sends `GET /v1/memory_stores/{memory_store_id}/memories` with the
> `agent-memory-2026-07-22` beta header (in *addition* to
> `managed-agents-2026-04-01` — sending only the old header still works
> but without the new list behavior; sending both headers where they'd
> conflict is what 400s, not sending them together per se — confirm the
> exact header combination against the live docs before shipping, since
> this file only has the behavioral description, not a verified
> request/response sample). Raise `ValueError` client-side if `depth`
> is given and isn't `0` or `1` (fail fast with a clear message instead
> of a 400 from the server). Return the raw paginated response
> (`data`/`has_more`/next-page cursor — mirror whatever shape
> `list_scheduled_deployments()` already returns for a paginated list in
> this file, for consistency) plus surface `path_prefix`/`depth` back in
> the result for caller convenience.
>
> Add a `--agent-memory-list MEMORY_STORE_ID` CLI flag (with
> `--agent-memory-path-prefix` and `--agent-memory-depth` companions)
> and a `cmd_agent_memory_list()` entry point following this file's
> existing `cmd_agent_*_list` naming and print-a-table style.
>
> Tests: request sends the new beta header alongside
> `MANAGED_AGENTS_BETA`; `depth` values other than `0`/`1`/`None` raise
> `ValueError` before any network call; `path_prefix`/`limit`/`page` are
> passed through as query params when given.

### Prompt 3 — Surface API key `expires_at` (P2)

> In `cmd_admin_list_keys()` (and wherever a single key's fields are
> printed, if `get_api_key()` has its own print path), add
> `expires_at` to the printed line, defaulting to a clear placeholder
> (e.g. `"never"` or `"—"`) when the field is absent or `None` rather
> than printing the literal string `"None"`. No change to
> `list_api_keys()`/`get_api_key()` themselves — they already return
> whatever the API sends; this is purely a presentation fix. Leave
> `cmd_admin_create_key()`'s explanation exactly as-is — the "no
> create endpoint" claim is still correct; only Console-UI key creation
> gained an expiration option, not the API.
>
> Tests: a key dict with `expires_at` set prints that value; a key dict
> with `expires_at` absent/`None` prints the placeholder, not the word
> `"None"`.

### Prompt 4 — zAICoder Analytics API (P2)

> Add to `AdminApiClient`:
> ```python
> def get_zc_code_usage_report(self, starting_at: str, limit: int = 20,
>                                   page: Optional[str] = None) -> dict
> ```
> `GET /organizations/usage_report/zc_code` with `starting_at`
> (required, `YYYY-MM-DD`), optional `limit`, optional `page` cursor —
> mirror this file's existing `_get()` helper and error-shape handling
> (the `{"error": ..., "status": ...}` pattern every other method here
> uses, including the 401/403 wrong-key-type hint via `_wrong_key_hint()`).
>
> Add `cmd_zc_code_usage_report(admin_api_key: str, starting_at: str,
> limit: int = 20)` printing a per-user table (date, actor
> email/api_key_name, num_sessions, lines added/removed,
> commits/PRs, estimated cost) — follow `cmd_usage_report()`'s existing
> table-printing style in this file. Add `--zc-code-usage-report`
> and `--zc-code-usage-report-start DATE` CLI flags.
>
> Tests: request sends `starting_at` and optional `limit`/`page`;
> 401/403 responses print the existing wrong-key-type hint (same
> pattern as `cmd_usage_report()`'s own test, if one exists — otherwise
> match its behavior exactly); a successful response's per-user records
> print without crashing on a record missing an optional field (e.g. no
> `model_breakdown`).

---

## Suggested sequencing

1. Prompt 1 (server tool version bumps) — no dependencies, touches three
   already-related modules together while the version research is fresh.
2. Prompt 2 (memory listing) — independent, Managed Agents surface.
3. Prompt 3 (`expires_at`) — smallest, presentation-only.
4. Prompt 4 (zAICoder Analytics API) — same module as Prompt 3, do
   last since it's the most net-new code in `zc_admin_api.py` this
   cycle.

After all four land, update `ROADMAP.md`'s Part 1 coverage table the way
every prior cycle has, and re-run a drift check on `zc_models.py`'s
catalog and `requirements.txt` per the methodology's own step 6.
