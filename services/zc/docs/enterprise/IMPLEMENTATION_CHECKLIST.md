# IMPLEMENTATION CHECKLIST (Form) — wire v1.16.0

Source: `ROADMAP.md` Part 2 — Gap Audit vs. `platform.zc.com/docs` (checked 2026-07-04)
One form per gap. All six gaps are now done — Forms 1–5 shipped in
v1.15.0, Form 6 (Compliance API) shipped in v1.16.0 once its own stated
exit condition ("revisit only if there's an actual concrete request for
it") was met. See `CHANGELOG.md`, `CHECKLIST.md`, and
`docs/29_upgrade_v1.15.0.md` / `docs/30_upgrade_v1.16.0.md` for the
narrative writeups this form-style tracker summarizes.

---

## Form 1 — 🔴 P0: Server-side fallback (`fallbacks` parameter)

| Field | Value |
|---|---|
| Priority | 🔴 P0 |
| Module(s) affected | `zc_fable5.py` |
| Est. effort | ~1 file, ~60 lines, no new deps |
| Owner | wire maintainers |
| Target date | v1.15.0 |
| Status | ☐ Not started ☐ In progress ☐ In review ☑ Done |

**Task list**
- [x] Add `fallback_chain: list[str] = None` param to `Fable5Client.__init__`
- [x] `call()`: set `payload["fallbacks"] = fallback_chain` when provided (replaces manual path, not additive)
- [x] `call_with_fallback()` reworked into compatibility wrapper (fallback_chain path vs. legacy manual path)
- [x] New CLI flag `--fable5-fallback-chain MODEL1,MODEL2` (max 3 incl. primary)
- [x] Docstring updated: explain manual retry vs. `fallbacks` param, and when to use each
- [x] Tests added/updated for both code paths (`tests/test_zc_fable5.py`, 15 tests)

**Sign-off**
- Reviewed by: wire maintainers  Date: v1.15.0 release
- Notes: Shipped as planned, no scope changes.

---

## Form 2 — 🟠 P1: Context editing

| Field | Value |
|---|---|
| Priority | 🟠 P1 |
| Module(s) affected | ~~New: `zc_context_editing.py`~~; integration: `zc_code.py` (see notes — no new module was needed) |
| Est. effort | ~1 new file + 1 integration point, ~200 lines (revised: 0 new files, ~1 integration point) |
| Owner | wire maintainers |
| Target date | v1.15.0 |
| Status | ☐ Not started ☐ In progress ☐ In review ☑ Done |

**Task list**
- [x] ~~New module `zc_context_editing.py` mirroring `zc_cache.py` structure~~ — not needed
- [x] ~~`ContextEditingConfig` dataclass...`~~ — not needed
- [x] Function to build `context_management` payload block — already existed as `zc_tools.build_context_management()`
- [x] wire into `zc_code.py` agent loop behind `--agent-context-editing` (opt-in)
- [x] Worked example added to `docs/` showing Compaction + context editing together (`docs/29_upgrade_v1.15.0.md`)
- [x] Confirm default behavior unchanged (opt-in only, `context_management=None` default)

**Sign-off**
- Reviewed by: wire maintainers  Date: v1.15.0 release
- Notes: The original gap-audit was wrong about this one — `zc_tools.py`
  already had a complete `build_context_management()`, so no new module
  was created. The real gap was narrower: `zc_code.py`'s agent loop
  never called it. Module(s) affected / Est. effort above are struck
  through rather than deleted, to keep an honest record of what the audit
  originally assumed vs. what was actually true.

---

## Form 3 — 🟠 P1: Agent Skills via the API (`skill_id`)

| Field | Value |
|---|---|
| Priority | 🟠 P1 |
| Module(s) affected | New: `zc_skills_api.py`; follow-up: `zc_excel.py`, `zc_powerpoint.py` |
| Est. effort | ~1 new file, ~120 lines (excel/pptx integration is a separate follow-up) |
| Owner | wire maintainers |
| Target date | v1.15.0 |
| Status | ☐ Not started ☐ In progress ☐ In review ☑ Done |

**Task list**
- [x] New module `zc_skills_api.py`
- [x] `list_skills()` wrapper
- [x] `SkillRef` helper for `skill_id` in Messages requests
- [x] CLI flag `--skills-list`
- [x] CLI flag `--skills-info ID` (info-only, matches `cmd_fable5_info` pattern)
- [x] **Follow-up PR (separate, not this one):** `--excel-native` / `--pptx-native` flags on `zc_excel.py` / `zc_powerpoint.py`, existing hand-rolled logic kept as fallback — landed in the same v1.15.0 pass, ahead of the original schedule

**Sign-off**
- Reviewed by: wire maintainers  Date: v1.15.0 release
- Notes: Follow-up item landed early rather than as a separate PR; no
  regression to the fallback path when Skills access isn't available.

---

## Form 4 — 🟡 P2: Usage and Cost API

| Field | Value |
|---|---|
| Priority | 🟡 P2 |
| Module(s) affected | New: `zc_admin_api.py` (renamed from planned `zc_usage_api.py`, folded with Form 5); cross-link: `zc_cost_optimizer.py` |
| Est. effort | ~1 file, ~100 lines. Requires Admin API key |
| Owner | wire maintainers |
| Target date | v1.15.0 |
| Status | ☐ Not started ☐ In progress ☐ In review ☑ Done |

**Task list**
- [x] New module `zc_admin_api.py`
- [x] `get_usage_report(start, end, group_by)` wrapper (plus `get_cost_report`)
- [x] CLI flag `--usage-report` (prints table)
- [x] Cross-link from `zc_cost_optimizer.py` docstring
- [x] CLI help text clearly flags Admin API key requirement (avoid silent 401)

**Sign-off**
- Reviewed by: wire maintainers  Date: v1.15.0 release
- Notes: Named `zc_admin_api.py`, not `zc_usage_api.py` — see
  Form 5, folded into the same module.

---

## Form 5 — 🟡 P2: API key management (Admin API)

| Field | Value |
|---|---|
| Priority | 🟡 P2 |
| Module(s) affected | `zc_admin_api.py` |
| Est. effort | ~80 lines, combined with Usage API module |
| Owner | wire maintainers |
| Target date | v1.15.0 |
| Status | ☐ Not started ☐ In progress ☐ In review ☑ Done (list/revoke — create is N/A by design) |

**Task list**
- [x] Decide module grouping — folded into `zc_admin_api.py` alongside Usage API
- [x] CLI flag `--admin-list-keys`
- [x] CLI flag `--admin-create-key NAME` — implemented as an explanation, not a real call: no documented create-key endpoint exists (Console-only, secret shown once), so this prints why rather than faking success
- [x] CLI flag `--admin-revoke-key ID`
- [x] Admin API auth requirements documented alongside Usage API

**Sign-off**
- Reviewed by: wire maintainers  Date: v1.15.0 release
- Notes: `--admin-create-key` deliberately does not call an endpoint —
  see the module docstring for why that's a documented boundary, not a
  gap.

---

## Form 6 — 🟡 P2: Compliance API

| Field | Value |
|---|---|
| Priority | 🟡 P2 |
| Module(s) affected | New: `zc_compliance_api.py`; integration: `main.py` (new `Compliance API` argument group + dispatch block) |
| Est. effort | Originally estimated N/A (documented gap only); actual: ~450 lines (client + all `cmd_*` wrappers) |
| Owner | wire maintainers |
| Target date | v1.16.0 |
| Status | ☐ Documented gap (default) ☑ Reconsidered — built |

**Task list**
- [x] Confirm gap remained documented in `ROADMAP.md` / `README.md` through v1.15.0
- [x] No speculative implementation in v1.15.0 — waited, as recommended
- [x] Revisit trigger arrived: the Compliance API is now real and documented
  at `platform.zc.com/docs/en/manage-zc/compliance-api*`
  (confirmed 2026-07-04), which is the "concrete request" condition the
  v1.15.0 recommendation named
- [x] `ComplianceApiClient`: documented retry contract (429 + retryable
  5xx back off exponentially 1s→60s; 400/401/403/404/409 never retry)
- [x] Activity Feed: list + cursor-safe pagination (`iterate_activities`)
- [x] Chats: list, get messages, hard-delete
- [x] Files: download (with `Content-Disposition` filename parsing), hard-delete
- [x] Projects: list, info, attachments, hard-delete
- [x] Directory: orgs, org users, org roles, org settings, groups, group members
- [x] Dry-run-by-default guard on every destructive `cmd_*`, requires
  explicit `yes=True` (`--compliance-yes`)
- [x] Surfaces the documented 403 scope-mismatch message with a concrete
  fix instead of a bare permission error
- [x] 23 new CLI flags wired into `main.py` under a `Compliance API`
  argument group, dispatch mirrors `zc_admin_api.py`'s block
- [x] Key fallback order documented: `--compliance-api-key` →
  `ZC_COMPLIANCE_API_KEY` → `--admin-api-key` →
  `ZC_ADMIN_API_KEY` (Admin key fallback reaches only the Activity
  Feed endpoint)
- [x] Tests: `tests/test_zc_compliance_api.py`, 28 tests, all passing

**Sign-off**
- Reviewed by: wire maintainers  Date: v1.16.0 release
- Notes: This is not a reversal of the v1.15.0 "leave as a gap" call —
  that recommendation's own stated exit condition was met, so building
  it now is consistent with the original plan, not a departure from it.

---

## Form 7 — 🟠 P1: Mid-conversation system messages

| Field | Value |
|---|---|
| Module(s) affected | `zc_cache.py`; integration: `main.py` (new `Prompt Caching` group flags + dispatch) |
| Est. effort | ~150 lines (builder + validator + threading through `generate_cached()`/`multi_turn_cached()`) |
| Owner | wire maintainers |
| Target date | v1.18.0 |
| Status | ☑ Done |

**Task list**
- [x] Confirmed genuinely absent — zero matches for `role.*system` message
  construction anywhere in the tree outside test fixtures, not just no
  module with a matching name
- [x] `build_mid_system_message(text)` — builds the `{"role": "system", ...}`
  message block (text-only content, per docs)
- [x] `validate_system_message_placement(messages)` — encodes all five
  documented placement rules (not first entry; not adjacent to another
  system message; must follow a user turn or an assistant turn ending in
  server tool use; cannot sit between a tool_use and its tool_result; must
  be the last entry or followed by an assistant turn) and raises a
  dedicated `SystemMessagePlacementError` naming which rule failed
- [x] `MID_SYSTEM_SUPPORTED_MODELS = {"zc-opus-4-8"}` model gate, since
  this feature is Opus 4.8 only (no beta header) per docs
- [x] `mid_system` param threaded through `generate_cached()`
- [x] `mid_system_updates` (turn-index → text map) threaded through
  `multi_turn_cached()` — the realistic use case, since the placement
  rules require existing conversation history to attach to
- [x] CLI: `--cache-multi-turn TEXT [TEXT...]`, `--cache-mid-system TEXT`,
  `--cache-mid-system-after N`, dispatched via new `cmd_cache_multi_turn()`
- [x] Confirm default behavior unchanged — `mid_system`/`mid_system_updates`
  both default to `None`/`{}`, no effect unless explicitly passed
- [x] Tests: `tests/test_zc_cache.py` (new file — this module had zero
  test coverage before this cycle)

**Sign-off**
- Reviewed by: wire maintainers  Date: v1.18.0 release
- Notes: Placement validation runs client-side before the request goes
  out, so a misplaced system message fails fast with a specific message
  instead of spending a round trip on the API's 400.

---

## Form 8 — 🟡 P2: Cache diagnostics (beta) — CLI wiring

| Field | Value |
|---|---|
| Module(s) affected | `main.py` only — `zc_cache.py`'s client-side support already existed |
| Est. effort | ~10 lines (one flag, one kwarg passthrough) |
| Owner | wire maintainers |
| Target date | v1.18.0 |
| Status | ☑ Done |

**Task list**
- [x] Initial grep for `cache_diagnostic`/`cache.diagnostic` found nothing
  and looked like a fresh P1/P2 gap
- [x] Read `zc_cache.py` directly before writing new code (per the
  Methodology note's "confirm with a second grep" correction) — found
  `diagnose=` on `generate_cached()`, the `cache-diagnosis-2026-04-07`
  beta header, the `diagnostics.previous_message_id` request field, and
  `cache_miss_reason` surfaced through `cache_stats()`/`print_cache_stats()`
  already fully implemented
- [x] Real gap identified: `main.py` never set `diagnose=True` anywhere —
  the feature was unreachable from the CLI despite being fully built
- [x] Added `--cache-diagnose` flag, wired to `cmd_cache_generate(diagnose=...)`
- [x] Tests: `tests/test_zc_cache.py` covers the `diagnose=True` request
  shape (both the first-call `previous_message_id: None` case and the
  second-call reference-prior-id case) and the beta header

**Sign-off**
- Reviewed by: wire maintainers  Date: v1.18.0 release
- Notes: Not a reversal or correction of any prior claim — Part 1 of
  `ROADMAP.md` always listed Prompt caching as covered by `zc_cache.py`
  and that was accurate; this was a CLI-reachability gap, not a coverage
  gap.

---

## Form 9 — 🟠 P1: Managed Agents memory stores

| Field | Value |
|---|---|
| Module(s) affected | `zc_agents_sdk.py`, `main.py` |
| Est. effort | ~90 lines + tests |
| Owner | wire maintainers |
| Target date | v1.19.0 |
| Status | ☑ Done |

**Task list**
- [x] Found via `requirements.txt` SDK-drift check (step 6 of the audit
  methodology), not a direct docs-feature-list grep: `zc-sdk-python`
  v0.116.0's changelog mentions a new `agent-memory-2026-07-22` beta
  header, which led to the Managed Agents memory-store docs pages
- [x] Confirmed absence with two differently-worded greps
  (`memory_store` and `memory.?store|agent-memory|resources.*memory`)
  before concluding it was a real gap
- [x] Checked the other two "memory" features already in the tree
  (`zc_memory.py`'s `memory_20250818` tool, zAICoder's local
  `MEMORY.md`) to confirm neither already implements this under a
  different name — confirmed they don't; different scope and storage
  model each
- [x] Added `ManagedAgentsClient.create_memory_store(name)`
- [x] Added `memory_store_id` param to `create_session()`, mounting a
  `{"type": "memory_store", "memory_store_id": ...}` `resources` entry
  and the new beta header when set
- [x] Added `cmd_agent_memory_store_create()` standalone helper
- [x] `cmd_managed_agent_run()` gained an optional `memory_store` param
- [x] CLI: `--agent-memory-store NAME`, `--agent-memory-store-create`
- [x] Tests: new `tests/test_zc_agents_sdk.py` (10 tests) — module
  had zero coverage before this cycle, so also covers pre-existing
  `PermissionMode`, `TOOL_PRESETS`, and `MANAGED_AGENTS_BETA`

**Sign-off**
- Reviewed by: wire maintainers  Date: v1.19.0 release
- Notes: Purely additive — `memory_store_id` defaults to `None` and
  `create_session()`'s existing callers are unaffected; `--agent-managed-run`
  behaves exactly as before when `--agent-memory-store` isn't passed.

---

## Form 10 — 🟠 P1 / 🟡 P2: Dreaming, Outcomes, Webhooks (native Multiagent orchestration deferred)

| Field | Value |
|---|---|
| Module(s) affected | `zc_agents_sdk.py`, `main.py` |
| Est. effort | ~180 lines + tests |
| Owner | wire maintainers |
| Target date | v1.20.0 |
| Status | ☑ Done (Dreaming, Outcomes, Webhooks) / ⏸ Deferred (native Multiagent orchestration) |

**Task list**
- [x] Re-checked Managed Agents docs for what shipped alongside the
  memory-store feature closed in v1.19.0 (per this cycle's step 6),
  surfacing Dreaming, Outcomes, Webhooks, and native Multiagent
  orchestration as candidates
- [x] Confirmed each candidate's absence with two differently-worded
  greps before writing it up: Dreaming (`dream`, then
  `curat|reflect.*session|memory.*consolidat`); Outcomes
  (`define_outcome`, then `outcome_evaluation|rubric`); Webhooks
  (`webhook`, only an unrelated comment matched); native Multiagent
  orchestration (`multiagent|coordinator.*agents`, confirmed distinct
  from the pre-existing client-side `--agent-orchestrate` by reading
  the code directly, not just grep output)
- [x] Added `ManagedAgentsClient.create_dream/.get_dream/.list_dreams/.cancel_dream`
  (`dreaming-2026-04-21` beta header)
- [x] Added `ManagedAgentsClient.define_outcome/.wait_for_outcome`;
  `cmd_managed_agent_run()` gained opt-in outcome params
- [x] Added `ManagedAgentsClient.register_webhook`
- [x] CLI: `--agent-dream(-sessions/-instructions/-list/-get)`,
  `--agent-outcome(-rubric/-max-iter)`, `--agent-webhook-register`,
  `--agent-webhook-events`
- [x] Tests: 16 new tests added to `tests/test_zc_agents_sdk.py`
  (26 total in that file)
- [x] Native Multiagent orchestration — deliberately not implemented
  this cycle; see `ROADMAP.md`'s Priority Summary section for the full
  reasoning and stated exit condition

**Sign-off**
- Reviewed by: wire maintainers  Date: v1.20.0 release
- Notes: All three shipped features are purely additive —
  `outcome_description`/`outcome_rubric` default to `None` so
  `cmd_managed_agent_run()`'s existing plain-task behavior is unchanged
  when they're not passed. Native Multiagent orchestration intentionally
  left open with a stated exit condition, matching the Compliance API
  precedent from v1.15.0 → v1.16.0.

---

## Shared Definition of Done (all forms)

- [x] CLI flag follows house naming style (`--flag-name`)
- [x] Module docstring documents the feature and its relationship to any similar existing feature
- [x] Tests added/updated
- [x] `README.md` per-flag reference updated
- [x] `CHANGELOG.md` entry added
- [x] No regression to existing default behavior
- [x] `ROADMAP.md` updated — item moved from Part 2 (gap) to Part 1 (implemented)

## Rollup Status

| # | Item | Priority | Status |
|---|---|---|---|
| 1 | Server-side `fallbacks` param | 🔴 P0 | ✅ Done (v1.15.0) |
| 2 | Context editing | 🟠 P1 | ✅ Done (v1.15.0) |
| 3 | Agent Skills API (`skill_id`) | 🟠 P1 | ✅ Done (v1.15.0) |
| 4 | Usage and Cost API | 🟡 P2 | ✅ Done (v1.15.0) |
| 5 | API key management | 🟡 P2 | ✅ Done (v1.15.0) |
| 6 | Compliance API | 🟡 P2 | ✅ Done (v1.16.0) |
| 7 | Mid-conversation system messages | 🟠 P1 | ✅ Done (v1.18.0) |
| 8 | Cache diagnostics CLI wiring | 🟡 P2 | ✅ Done (v1.18.0) |
| 9 | Managed Agents memory stores | 🟠 P1 | ✅ Done (v1.19.0) |
| 10a | Managed Agents Dreaming | 🟠 P1 | ✅ Done (v1.20.0) |
| 10b | Managed Agents Outcomes | 🟠 P1 | ✅ Done (v1.20.0) |
| 10c | Managed Agents Webhooks | 🟡 P2 | ✅ Done (v1.20.0) |
| 10d | Managed Agents native Multiagent orchestration | 🟡 P2 | ⏸ Deferred (v1.20.0) |
| 11 | Managed Agents self-hosted sandboxes | 🟠 P1 | ✅ Done (v1.26.0) |
| 12 | Memory store beta-header regression fix + memory/memory-store CRUD | 🔴 P0 / 🟠 P1 | ✅ Done (v1.27.0) |
| 13 | CLI-to-API wiring audit (GitHub, Router, Prompt Optimizer, Metrics) | 🟠 P1 | ✅ Done (v1.31.0) |
| 14 | `--route-add-agent` follow-up from Form 13 | 🟡 P2 | ✅ Done (v1.32.0) |
| 15 | `--docx-native` / `--pdf-native` — last two pre-built Skills | 🟠 P1 | ✅ Done (v1.33.0) |

---

## Form 11 — 🟠 P1: Managed Agents self-hosted sandboxes

| Field | Value |
|---|---|
| Module(s) affected | `zc_agents_sdk.py`, `main.py` |
| Est. effort | ~90 lines + tests |
| Owner | wire maintainers |
| Target date | v1.26.0 |
| Status | ☑ Done |

**Task list**
- [x] Found via the docs-feature-list sweep (step 1 of the audit
  methodology): the Managed Agents docs tree lists "Self-hosted
  sandboxes" alongside "Cloud environment setup" as a peer configuration
  path, not a variant of it
- [x] Confirmed absence with a repo-wide grep for `self_hosted`/
  `self-hosted` before concluding it was a real gap — zero matches
- [x] Verified both the create config shape (`{"type": "self_hosted"}`,
  no networking/pool/capacity sub-fields, unlike `"cloud"`) and the
  `environments.work.stats()` read shape directly against current docs
  rather than guessing — both confirmed, so this did not need the
  "implemented defensively, needs a follow-up verification pass" caveat
  the v1.25.0 CMEK finding required
- [x] Added `env_type` param to `ManagedAgentsClient.create_environment()`
- [x] Added `ManagedAgentsClient.get_environment_work_stats(environment_id)`
- [x] Added `cmd_agent_env_self_hosted_create()` and
  `cmd_agent_env_work_stats()` CLI-facing wrappers
- [x] CLI: `--agent-env-self-hosted NAME`, `--agent-env-work-stats
  ENVIRONMENT_ID`
- [x] Tests: 6 new tests in `tests/test_zc_agents_sdk.py`
- [x] Deliberately did not build a worker/poller component (no concrete
  deployment target yet) — noted as a deferred, not abandoned, item in
  `docs/38_upgrade_v1.26.0_audit_and_impl.md`
- [x] Fixed a stale pre-existing test assertion in the same test file
  (`run_task` missing `stream_deltas=False`) while it was already open
- [x] Fixed `main.py`'s `VERSION` constant, which had drifted stale at
  `"1.16.0"`

**Sign-off**
- Reviewed by: wire maintainers  Date: v1.26.0 release
- Notes: Purely additive — `env_type` defaults to `"cloud"`, so every
  existing `create_environment()` caller is unaffected.

---

## Form 12 — 🔴 P0 bug fix + 🟠 P1: Memory store beta-header regression, memory/memory-store CRUD

| Field | Value |
|---|---|
| Module(s) affected | `zc_agents_sdk.py`, `main.py`, `tests/test_zc_agents_sdk.py` |
| Est. effort | ~260 lines + tests |
| Owner | wire maintainers |
| Target date | v1.27.0 |
| Status | ☑ Done |

**Task list**
- [x] Re-fetched `platform.zc.com/docs/en/release-notes/overview`
  live (not reused from a prior cycle) and re-read
  `.../managed-agents/memory` end to end per this cycle's step 6
  (drift check on an already-"done" area)
- [x] **Bug found:** `create_memory_store()` and `list_memories()` both
  sent `betas=[MANAGED_AGENTS_BETA, MEMORY_STORE_BETA]`; the July 2,
  2026 docs state this combination now 400s on memory store endpoints
  (`agent-memory-2026-07-22` replaces, not adds to,
  `managed-agents-2026-04-01` there)
- [x] Fixed both call sites to send `betas=[MEMORY_STORE_BETA]` alone
- [x] Confirmed `create_session()`'s `memory_store_id` branch is
  correctly unchanged — it's a `/v1/sessions` call, not a memory store
  endpoint, so the additive header combination still applies there
- [x] Updated the two pre-existing tests that asserted the now-wrong
  header combination (`test_create_memory_store_sends_expected_betas`,
  the `list_memories` beta-header assertion)
- [x] **Gap found:** memory store management (`retrieve`, `update`,
  `list`, `archive`, `delete`) and memory CRUD (`retrieve`, `create`,
  `update`, `delete`) were never built beyond `create_memory_store` and
  `list_memories`
- [x] Added `get_memory_store()`, `list_memory_stores()`,
  `archive_memory_store()`, `delete_memory_store()`
- [x] Added `create_memory()`, `get_memory()`, `update_memory()` (with
  `content_sha256` optimistic-concurrency precondition support),
  `delete_memory()`
- [x] Gave `create_memory_store()` the `description` param the docs'
  create call takes but the existing wrapper silently dropped
- [x] CLI: `--agent-memory-stores-list`
  (+`--agent-memory-stores-include-archived`),
  `--agent-memory-store-archive`, `--agent-memory-store-delete`
  (+`--agent-memory-store-delete-yes`, dry-run by default),
  `--agent-memory-get/-create/-update/-delete`
  (+`--agent-memory-id/-path/-content`, delete gated behind
  `--agent-memory-delete-yes`)
- [x] Tests: 13 new tests in `tests/test_zc_agents_sdk.py` (beta
  header correctness for every new method, dry-run/confirm gating for
  both delete commands)
- [x] Deliberately deferred memory versions (`list`/`retrieve`/`redact`)
  — audit/compliance-shaped feature, same "wait for a concrete request"
  call as Compliance API (v1.15.0→v1.16.0) and native Multiagent
  orchestration (v1.20.0); see `docs/39_upgrade_v1.27.0_audit_and_impl.md`
  for the exit condition
- [x] Checked API key expiration (July 8) and CMEK docs expansion (July
  10) release notes — confirmed non-gaps, documented why
- [x] Bumped `main.py`'s `VERSION` to `"1.27.0"`

**Sign-off**
- Reviewed by: wire maintainers  Date: v1.27.0 release
- Notes: Finding 1 is a regression fix (previously-correct code broken
  by a platform change), filed ahead of Finding 2's new-capability work
  since a live 400 on every memory-store call outranks an unbuilt
  feature. `create_session()`'s additive header usage was checked and
  left alone deliberately, not overlooked.

---

## Form 13 — 🟠 P1: CLI-to-API wiring audit (GitHub, Router, Prompt Optimizer, Metrics)

| Field | Value |
|---|---|
| Module(s) affected | `main.py`, `tests/test_cli_wiring.py` (new) |
| Est. effort | ~170 lines (main.py) + ~220 lines (new test file) |
| Owner | wire maintainers |
| Target date | v1.31.0 |
| Status | ☑ Done |

**Task list**
- [x] Different audit type this cycle: not platform.zc.com/docs vs.
  code, but `zc_*.py`'s own `cmd_*` functions vs. `main.py`'s
  dispatch — checked with `ast.parse` per module, not a docs fetch
- [x] Found 4 modules (`zc_github.py`, `zc_router.py`,
  `zc_prompt_optimizer.py`, `zc_metrics.py`) with 13 `cmd_*`
  functions total, none referenced in `main.py`
- [x] Caught and avoided a naming collision before wiring anything:
  `zc_prompt_optimizer.py`'s docstring specifies `--v2` for the
  second A/B variant, but `--v2` already exists as a `type=int` artifact
  flag — used `--ab-prompt-b` instead
- [x] Added argument groups: GitHub Integration, Multi-Agent Router,
  Prompt Optimizer, Metrics (local usage log)
- [x] Added dispatch blocks calling each `cmd_*` function with correct
  positional argument order (verified against each function's real
  signature, not assumed)
- [x] Evaluated `zc_evals.py`'s `cmd_eval` — confirmed superseded by
  the already-wired `zc_eval.py`, left unwired on purpose, recorded
  in `tests/test_cli_wiring.py`'s `KNOWN_EXCEPTIONS`
- [x] Evaluated `zc_router.py`'s `--route-add-agent` (docstring-only,
  no backing `cmd_*` function) — left as a follow-up, not guessed at
- [x] New `tests/test_cli_wiring.py`: parametrized regression test over
  every `zc_*.py` module (62 new tests total, includes flag-parsing
  and dispatch-level coverage for all 4 newly-wired modules)
- [x] Bumped `main.py`'s `VERSION` to `"1.31.0"`
- [x] `ROADMAP.md`, `CHANGELOG.md`, `README.md` updated

**Sign-off**
- Reviewed by: wire maintainers  Date: v1.31.0 release
- Notes: Purely additive — no existing flag, dest name, or dispatch
  order was changed. The `test_cli_wiring.py` regression test is the
  actual deliverable of this cycle as much as the 4 modules' flags are;
  it's what prevents this exact gap from reappearing for the next
  fully-built-but-unwired module.

## Form 14 — 🟡 P2: `--route-add-agent` follow-up from Form 13

| Field | Value |
|---|---|
| Module(s) affected | `zc_router.py`, `main.py`, `tests/test_cli_wiring.py` |
| Est. effort | ~40 lines (`zc_router.py` + `main.py`) + ~65 lines (new tests) |
| Owner | wire maintainers |
| Target date | v1.32.0 |
| Status | ☑ Done |

**Task list**
- [x] Made the design decision Form 13 deferred: `--route-add-agent NAME
  DESCRIPTION` as a repeatable `nargs=2` flag (`action="append"`), matching
  the paired-value shape of `--git-pr`/`--eval-compare` and the
  repeatable-flag pattern `--browse-allow-domain` already uses
- [x] Added `zc_router.extra_table_from_pairs()` — folds the collected
  `[NAME, DESCRIPTION]` pairs into the dict `cmd_route()`/`cmd_route_list()`
  already accept as `extra_table`; returns `None` (not `{}`) for a falsy
  input so every call site can use it unconditionally
- [x] wired into both router dispatch branches (`--route` and
  `--route-list`) in `main.py`
- [x] Updated `zc_router.py`'s `CLI flags:` docstring to the real flag
  shape (previously showed only `NAME`, not `NAME DESCRIPTION`)
- [x] Confirmed scope: per-invocation only, not persisted — matches
  `extra_table`'s existing lifetime; persistence would be a new feature,
  not a wiring fix, and was explicitly left out
- [x] Fixed in passing: `main.py`'s module docstring (still described
  v1.30.0 despite `VERSION` already at `"1.31.0"`) and `pyproject.toml`'s
  `version` (still `"1.30.0"`) — both one release behind, both bumped
- [x] Re-ran Form 13's own `ast`-based wiring audit after the change —
  zero regressions, all `cmd_*` functions still reachable
- [x] Added 9 new tests to `tests/test_cli_wiring.py`: flag parsing,
  `extra_table_from_pairs()` unit coverage, and dispatch-level merge
  checks for both `--route` and `--route-list` (62 → 71 pytest-collected
  cases in that file)
- [x] Bumped `main.py`'s `VERSION` and `pyproject.toml`'s `version` to
  `"1.32.0"`
- [x] `ROADMAP.md`, `CHANGELOG.md`, `README.md` updated;
  `docs/44_upgrade_v1.32.0_route_add_agent.md` added

**Sign-off**
- Reviewed by: wire maintainers  Date: v1.32.0 release
- Notes: Closes the only flag-level item Form 13 left open. While
  updating the suite test count, found the running "full suite" total in
  `CHANGELOG.md` had drifted from what a fresh, parametrize-aware count
  actually produces (387 vs. the stated 336, before this cycle's own +9)
  — recorded honestly in `docs/44_upgrade_v1.32.0_route_add_agent.md`
  rather than silently patched over or silently left unreconciled.
  Reconciling the drift's root cause across every prior cycle is a
  separate effort, out of scope here.

---

## Form 15 — 🟠 P1: `--docx-native` / `--pdf-native` — last two pre-built Skills

| Field | Value |
|---|---|
| Module(s) affected | `zc_word.py` (new), `zc_pdf.py` (new), `zc_skills_api.py`, `main.py`, `tests/test_zc_word_pdf.py` (new), `tests/test_cli_wiring.py` |
| Est. effort | ~230 lines (two new modules) + ~20 lines (`main.py`) + ~190 lines (new tests) |
| Owner | wire maintainers |
| Target date | v1.33.0 |
| Status | ☑ Done |

**Task list**
- [x] Confirmed the gap: `zc_skills_api.py`'s `PREBUILT_SKILLS` has
  listed `docx`/`pdf` since v1.15.0; `--excel-native`/`--pptx-native`
  (v1.16.0) never got a docx/pdf counterpart; grep across `main.py`
  confirmed zero flags referencing either format outside the
  `--skills-list` help string
- [x] Built `zc_word.py` (`cmd_docx_chat`) and `zc_pdf.py`
  (`cmd_pdf_chat`), each mirroring `zc_powerpoint.py`'s
  `_cmd_pptx_chat_native()` one-for-one — upload-once/download-per-turn
  shape against `SkillsApiClient.call_with_skills_turn()`
- [x] Skills-only by design, no `native=` boolean — unlike xlsx/pptx,
  there's no hand-rolled fallback for docx/pdf in this CLI to branch to
- [x] wired `--docx-native [FILE]` / `--docx-output FILE` /
  `--pdf-native [FILE]` / `--pdf-output FILE` into `main.py`'s new
  "Word / PDF Chat (Skills API only)" argument group, same
  `nargs="?", const=""` shape as `--excel`/`--pptx`
- [x] Corrected `zc_skills_api.py`'s module docstring — it called
  xlsx/pptx Skills routing "a separate follow-up," stale since v1.16.0
  shipped it
- [x] Ran `test_cli_wiring.py`'s existing `ast`-based wiring audit —
  picked up both new `cmd_*` functions automatically (globs
  `zc_*.py`), passed with zero changes needed to that test itself
- [x] Added `tests/test_zc_word_pdf.py` (12 tests): upload path,
  upload-failure/missing-id exit paths, container-id reuse across turns,
  API-error handling, generated-file download, correct skill name sent
  per module
- [x] Added 9 tests to `tests/test_cli_wiring.py`: flag parsing (with
  file, bare flag, omitted-defaults-to-`None`) and dispatch-level checks
  for both new flags
- [x] Bumped `main.py`'s `VERSION` and `pyproject.toml`'s `version` to
  `"1.33.0"`; rewrote `main.py`'s module docstring for this cycle
- [x] `ROADMAP.md`, `CHANGELOG.md`, `README.md` updated;
  `docs/45_upgrade_v1.33.0_docx_pdf_native.md` added

**Sign-off**
- Reviewed by: wire maintainers  Date: v1.33.0 release
- Notes: Closes out all four pre-built Skills (`pptx`, `xlsx`, `docx`,
  `pdf`) with native CLI routing. Deliberately did not build a
  hand-rolled docx/pdf fallback the way `zc_excel.py` reimplements
  xlsx — that would be a new capability (docx/pdf generation without
  Skills access), not closing this gap, and wasn't asked for.
