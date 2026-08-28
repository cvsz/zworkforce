# v1.27.0 audit cycle — gap findings + implementation notes

Continuation of the cross-product cycle (previous audit: 2026-07-13, per
`ROADMAP.md`'s header). This one re-ran the sweep against
`platform.zc.com/docs/en/release-notes/overview` (fetched fresh
rather than trusted from the previous cycle's notes) and, per this
cycle's step 6 (check for *drift* in already-"done" features, not just
net-new ones), re-read `platform.zc.com/docs/en/managed-agents/memory`
end to end against what `zc_agents_sdk.py` actually implements for
memory stores — the area flagged "done" most recently (v1.19.0, then
touched again in v1.24.0 for the list-behavior change). That re-read is
what this cycle's findings came from, not the top-level release-notes
page, which had only one dated entry since the last cycle with any code
implications.

Model catalog re-checked first: no new model releases since zAICoder
Sonnet 5 (June 30, 2026); `zc_models.py`'s `MODEL_CATALOG` is
current. `requirements.txt`'s floor pin (`anthropic>=0.75.0`) needed no
change.

## Finding 1 — Regression: memory store endpoints now reject the beta header combination wire sends (🔴 P0, bug not a missing feature)

**What it is:** The July 2, 2026 release note reads: "On memory store
endpoints, `agent-memory-2026-07-22` replaces `managed-agents-2026-04-01`;
sending both returns a `400` error." This is a breaking change to a
header *combination* wire was actively sending, not a new feature to
adopt — the platform changed underneath already-shipped code.

**Why it was a gap:** `ManagedAgentsClient.create_memory_store()` and
`.list_memories()` (v1.19.0 and v1.24.0 respectively) both sent
`betas=[MANAGED_AGENTS_BETA, MEMORY_STORE_BETA]`. That was correct when
written — the original memory-store docs said the beta header was
required "in addition to" `managed-agents-2026-04-01`. The July 2 change
flipped that specific rule for the two direct `/v1/memory_stores/*`
endpoints wire calls (`memory_stores.create`,
`memory_stores.memories.list`), and no later audit cycle re-read the
memory docs closely enough to catch it — the v1.24.0 cycle that touched
`list_memories()` added the *list-behavior* changes (stable order,
`depth` restricted to `0`/`1`/omitted, `path_prefix` trailing-slash
requirement) from the same July 2 note correctly, but missed the beta
header line in the same paragraph. Confirmed live: both call sites
matched a grep for `MANAGED_AGENTS_BETA, MEMORY_STORE_BETA` before this
fix, and nothing else in the file's other Managed Agents endpoints
(sessions, agents, environments, dreams, vaults, deployments) touches
`/v1/memory_stores/*` directly, so the fix is scoped to exactly these
two call sites plus the four new ones added in Finding 2 below.

**What changed:** Both call sites now send `betas=[MEMORY_STORE_BETA]`
only. `create_session()`'s `memory_store_id` branch is deliberately
*unchanged* — it calls `/v1/sessions`, not a memory_stores endpoint, and
the docs scope the header replacement to memory store endpoints
specifically, so the additive `[MANAGED_AGENTS_BETA, MEMORY_STORE_BETA]`
there is still correct (unverified against a live 400 response either
way, same caveat as any docs-only finding — flagging for a future
cycle's list of things to re-confirm if a concrete failure report comes
in). Two pre-existing tests in `tests/test_zc_agents_sdk.py` were
asserting the now-wrong header combination and were updated to match;
see `IMPLEMENTATION_CHECKLIST.md` Form 12.

**Priority: 🔴 P0.** A live code path that would 400 on every call as of
July 2, 2026 is more urgent than any unbuilt feature — this was shipped,
believed-working code silently broken by a platform change, not a gap
in coverage.

## Finding 2 — Memory and memory-store CRUD never built beyond create + list (🟠 P1)

**What it is:** `platform.zc.com/docs/en/managed-agents/memory`
documents a full CRUD surface wire only partially covers:

- Memory stores: `create` (had it), `retrieve`, `update`, `list`,
  `archive`, `delete` (all five missing).
- Individual memories: `list` (had it), `retrieve`, `create`, `update`
  (with optimistic-concurrency `content_sha256` preconditions),
  `delete` (four of five missing).
- Memory versions: `list`, `retrieve`, `redact` (audit trail /
  point-in-time recovery / compliance-style redaction — all missing).

**Why it was a gap:** A grep for `memory_stores\.` before this cycle
matched exactly two call sites — `memory_stores.create` and
`memory_stores.memories.list`. Nothing else in the file touched
`memory_stores.retrieve/update/list/archive/delete` or
`memory_stores.memories.retrieve/create/update/delete`, and nothing
touched `memory_versions` at all. `create_memory_store()`'s own
docstring called memory stores "FUSE-mounted" and implied read/write
access was purely the *agent's* filesystem-level access inside a
session — true, but incomplete: the docs are explicit that stores "can
be managed directly via the API," independent of any session, "for
building review workflows, correcting bad memories, or seeding stores
before any session runs." wire had no way to do any of that outside
of a live agent session.

**What changed (this cycle):**
- Memory store management: `get_memory_store()`, `list_memory_stores()`,
  `archive_memory_store()`, `delete_memory_store()` — plus
  `create_memory_store()` gained an optional `description` param it was
  missing (the docs pass `description` at creation to tell the agent
  what the store contains; wire's version silently dropped it since
  the wrapper never accepted one).
- Memory CRUD: `create_memory()`, `get_memory()`, `update_memory()`
  (with `content_sha256` optimistic-concurrency support), `delete_memory()`.
- CLI: `--agent-memory-stores-list` (+`--agent-memory-stores-include-archived`),
  `--agent-memory-store-archive ID`, `--agent-memory-store-delete ID`
  (+`--agent-memory-store-delete-yes` — dry-run by default, same
  confirmation pattern as `zc_compliance_api.py`'s hard-delete
  commands, since store deletion is irreversible and destroys version
  history too), `--agent-memory-get/-create/-update/-delete STORE_ID`
  (+`--agent-memory-id`, `--agent-memory-path`, `--agent-memory-content`;
  delete also gated behind `--agent-memory-delete-yes`).
- Tests: 13 new tests in `tests/test_zc_agents_sdk.py` covering every
  new method's beta-header correctness plus the two delete commands'
  dry-run/confirm gating.

**Deliberately not built this cycle: memory versions (`list`,
`retrieve`, `redact`).** This is the same "revisit when there's a
concrete request" call the Compliance API got between v1.15.0 and
v1.16.0, and native Multiagent orchestration got in v1.20.0: version
history is fundamentally an audit/compliance feature (point-in-time
recovery, PII/secret redaction while preserving the "who changed what"
trail) rather than something a session's own agentic workflow needs day
to day — `memories.update`'s `content_sha256` precondition (built this
cycle) already covers the concurrent-write-safety use case that would
otherwise motivate reaching for version history. Redact in particular
has a real compliance/legal-hold shape (a version that's the current
head of a live memory can't be redacted; you write a new version or
delete the memory first, then redact the old one) that's worth building
against an actual need rather than guessing at wire's own semantics
for "why would this CLI's user want to redact a memory version" in the
abstract. **Exit condition:** revisit if a concrete workflow shows up
that needs to inspect, restore, or redact a memory's history rather than
just its current content.

**Priority: 🟠 P1** for what was built (a real capability gap — findable
via the API but with zero client-side path in wire — for a use case
the roadmap already validated by building `create_memory_store` and
`list_memories` in earlier cycles), **not P0**, since nothing here was a
regression the way Finding 1 was.

## Non-gaps checked this cycle

**API key expiration (`platform.zc.com/docs`, July 8, 2026)** —
confirmed **not** a wire gap: the feature ("Choose a preset, a custom
duration, or Never" when creating a key) is scoped to "when you create
an API key or an Admin API key in the **zAICoder Console**" — a Console UI
flow, not a new Messages/Admin API request parameter. `expires_at` being
surfaced on the *read* side (`--admin-list-keys`) was already covered in
v1.24.0, and `zc_admin_api.py`'s `--admin-create-key` already
explains, rather than fakes, why key creation isn't done programmatically
(ZaiCoder doesn't expose a create-key endpoint — keys are Console-only
so the secret is shown exactly once). No code path changed by this
release note.

**CMEK content-preservation docs expansion (July 10, 2026)** — confirmed
**not** a code gap: this release note only expands documentation (a
filter example, an example event payload, two preservation reason
codes) for an *existing* `cmek_preserve` Access Transparency event type.
`zc_admin_api.py`'s CMEK coverage (`--cmek-list`, flagged
⚠️ unverified endpoint shape back in v1.25.0) is about the
`external_keys` Admin API, a different surface than Access Transparency
event logging; this note doesn't touch it either way.

**Managed Agents dreams / multiagent / outcomes / webhooks** — re-read
their docs pages alongside the memory page for this cycle's drift check;
no changes found since the versions already implemented (v1.20.0/v1.21.0
for dreams/outcomes/webhooks, still deliberately deferred for native
multiagent per v1.20.0's exit condition, unchanged this cycle).

## Methodology note (unchanged from prior cycles, restated for this one)

Confirmed via a live fetch of `platform.zc.com/docs/en/release-notes/
overview` (not cached from a previous cycle's notes) plus a full re-read
of `platform.zc.com/docs/en/managed-agents/memory` end to end, then
grepping the source tree for the concrete API surface of each item
(`memory_stores\.`, beta header strings) rather than trusting docstrings.
Where a docstring claimed a header requirement the current docs no
longer state, the docs won — this is the first cycle where the finding
was "code that used to be correct is now wrong," not "code was never
written," so it's filed as a 🔴 P0 bug (Finding 1) ahead of the 🟠 P1
missing-feature finding (Finding 2), reversing the usual priority
ordering where missing-feature findings dominate a cycle.
