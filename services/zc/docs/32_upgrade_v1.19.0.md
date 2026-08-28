# v1.19.0 upgrade notes — Managed Agents memory stores

This release comes from re-running `ROADMAP.md`'s own gap-audit
methodology against the live docs at platform.zc.com/docs. The
previous audit was dated 2026-07-08; this one is also dated 2026-07-08
(same day, next cycle). One real finding, closed here.

## Finding — Managed Agents memory stores (new, genuinely missing)

**How it was found:** not from a direct grep against the docs' feature
list, but from step 6 of the audit methodology — checking for drift in
the pinned `zc` SDK. `requirements.txt` pins `zc>=0.75.0`,
which is a floor rather than an exact version, so the pin string itself
hadn't drifted. But checking the SDK's *own* changelog turned up
`zc-sdk-python` v0.116.0's release note: "api: add
agent-memory-2026-07-22 beta header." That led to the Managed Agents
memory-store docs pages, which describe a workspace-scoped, persistent,
FUSE-mounted file directory (`memory_store`) that can be attached to a
Managed Agents session via `resources`, with every write recorded as an
immutable version for audit/point-in-time recovery.

A first grep for `memory_store` in the tree found nothing. Per this
cycle's methodology (confirm every apparent miss with a second,
differently-worded grep before writing it into Part 2), a second grep —
`memory.?store|agent-memory|resources.*memory` — also came up empty.
Only then was this written up as a real gap.

**Why this isn't a duplicate of either existing "memory" feature:**
wire already has two things with "memory" in the name, and it mattered
to rule both out before concluding this was new:

- `zc_memory.py`'s `memory_20250818` client-side tool — the caller's
  own application implements the file-operation handlers; scope is a
  single Messages API conversation; storage is wherever the caller wires
  it (local disk, database, etc.).
- zAICoder's local `.zc`/auto-generated `MEMORY.md` — never
  leaves the developer's own machine; loaded into a zAICoder session's
  context at the start of each session.

Neither implements a `memory_store` resource type or talks to a
`memory_stores` endpoint. The new feature is the only one of the three
that's ZaiCoder-hosted, versioned, and shared across a Managed Agents
agent's sessions — genuinely additive, not a rename of something already
there.

**Why P1, not P2:** without it, every Managed Agents session
`cmd_managed_agent_run()` creates is necessarily a one-shot, throwaway
session — there was no supported way for a hosted agent's work to
survive past that single session. For a CLI whose stated use case
includes multi-session agentic coding, that's a capability gap, not a
reporting/admin convenience.

**What was built**, all in `zc_agents_sdk.py`:

- `MEMORY_STORE_BETA = "agent-memory-2026-07-22"` — a second beta header,
  sent alongside `MANAGED_AGENTS_BETA` only when a memory store is
  actually being created or mounted (not on every Managed Agents call).
- `ManagedAgentsClient.create_memory_store(name)` — wraps
  `client.beta.memory_stores.create(name=..., betas=[...])`.
- `create_session(agent_id, environment_id, title="", memory_store_id=None)`
  — when `memory_store_id` is given, adds
  `{"type": "memory_store", "memory_store_id": ...}` to a `resources`
  list on the session-creation call and includes `MEMORY_STORE_BETA`.
  When omitted (the default), behavior is byte-for-byte identical to
  before this release — `resources=None`, only `MANAGED_AGENTS_BETA` sent.
- `cmd_agent_memory_store_create(name, api_key)` — a standalone CLI
  entry point for creating a store once, ahead of reusing it across many
  later `--agent-managed-run` invocations under the same name.
- `cmd_managed_agent_run(..., memory_store=None)` — when a name is
  passed, creates (or would create — the API treats a repeat `name` as
  idempotent per the docs) the store and mounts it into the throwaway
  session before running the task, so the session is no longer
  necessarily throwaway.

New CLI flags, both in the "Agent SDK" argument group:

```bash
# Create a memory store once, ahead of time
python main.py --agent-memory-store-create --agent-memory-store project-x-notes

# Mount it into a hosted Managed Agents run
python main.py --agent-managed-run "Continue the refactor from last time" \
    --agent-memory-store project-x-notes
```

## Drift check

Also checked for drift (not just net-new features) per this cycle's
methodology: `zc_models.py`'s catalog (Fable 5, Mythos 5, Opus 4.8,
Sonnet 5, Haiku 4.5, legacy tiers) still matches the live Models overview
exactly — no stale entries, no missing releases, no deprecation-date
changes. Nothing to fix there this cycle. The `requirements.txt` pin
itself (`zc>=0.75.0`) needed no edit — it's a floor, and the
installed SDK is well above it — but it was the process of checking the
SDK's changelog for drift, rather than trusting the pin string alone,
that surfaced the finding above.

## Tests

`zc_agents_sdk.py` had zero test coverage before this release —
matching the pattern the v1.18.0 cycle found in `zc_cache.py`. Added
`tests/test_zc_agents_sdk.py`, 10 tests covering: `PermissionMode`
and `TOOL_PRESETS` constants (pre-existing behavior), a regression guard
on the `MANAGED_AGENTS_BETA` header string, `MEMORY_STORE_BETA`'s value,
`create_memory_store()`'s request shape, `create_session()` both with
and without `memory_store_id` (confirming the no-store path is
unaffected), and `cmd_managed_agent_run()` / `cmd_agent_memory_store_create()`
end to end against a mocked `ManagedAgentsClient`. All 160 tests in the
repo pass (150 pre-existing + 10 new).
