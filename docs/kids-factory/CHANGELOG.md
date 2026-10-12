# Kids Factory Changelog

Scoped to the AI Kids Content Factory vertical slices. This feature is
**not** part of any `v3.0.x` release line — do not copy these entries into
the root `CHANGELOG.md` until a release authority explicitly promotes the
subsystem. Status as of 2026-10-12; delivery vehicle is PR #285
(`feat/ai-kids-content-factory`), CI green, awaiting independent review.

## Slice 1 — domain + core API (`335438b`)

- Tenant-scoped brand/character/episode/script/scene/asset/timeline/render/approval/publishing/analytics persistence (SQLite + PostgreSQL portable).
- `/api/v1/kids/*` transport (reads `viewer/workforce:read`, writes `operator/automation:write`).
- `kids.*` MCP tools, mutations deny-by-default.
- Kids Studio dashboard panel reading live backend state only.
- Deterministic FFmpeg sample render (SHA-256) + approval-gated mock YouTube publishing + synthetic analytics.
- LumiKids "Colorful Learning Bus" end-to-end demo proven; 9 tests.

## Slice 2 — campaign + pipeline + budget (`1f51fc3`)

- Campaign planner, one-shot episode pipeline with durable `kids_agent_runs` checkpoints and idempotent resume; publishing stays manual.
- Episode `budget_credits` gate; MCP campaign/pipeline tools; 13 tests.

## Slice 3 — shorts + voice/music + quotas (`8dc15a3`)

- 9:16 Shorts derivation with provenance; voice profiles with consent-gated cloning + synthetic WAV previews; licensed music registry; per-brand quotas; `kids.derive_shorts`; 17 tests.

## Slice 4 — variants + marketing + analytics (`7b462cc`)

- Language-variant drafts flagged `needs_review`; marketing drafts labeled estimates; analytics summary from persisted rows only; 20 tests.

## Slice 5 — async queue + translation (`0d5e681`)

- Async render queue (`queue` + `tick`, 3 attempts, dead-letter); shared `execute_render_job`; human translation workflow; 23 tests.

## Slice 6 — schedules + routes + export (`7703330`)

- Future tz-aware publishing slots with per-channel conflict guard; provider route config + resolve (externals disabled); full episode export bundles; 26 tests.

## Slice 7 — import/restore (`f010e87`)

- Same-tenant bundle import of the creative graph; renders/approvals/publishing deliberately not restored (approvals must be re-done); round-trip proven; 27 tests.

## Runbook (`dd1e8eb`)

- `RUNBOOK.md`: incidents, backup/restore drill, rollback, escalation.

## Slice 8 — review hardening (this commit)

Addresses the ~35 Codex review findings on PR #285 (all valid ones fixed, with regression tests):

- Four-eyes: requester cannot approve their own approval; approval decisions are compare-and-set (`state='pending'` guard, losers read terminal state).
- Approvals bound to content: publishing fails when scripts/scenes/timelines changed after the decision (microsecond timestamps for exact ordering); usage counted once on the prepared → published transition; render job must exist, match the episode, and be `succeeded` at prepare time.
- Shared safety corpus (script + visuals + dialogue + captions + timeline tracks) on HTTP, MCP, and pipeline transports.
- Nested-settings secret scan (brand/channel/scene dialogue); server-generated asset IDs (no cross-tenant squatting); asset bytes verified against claimed SHA-256 (or strict 64-hex for metadata-only).
- Locked characters reject material edits until unlocked; storyboard replace drops stale scenes.
- Timeline-ordered renders (trims/reorders respected); true 1920x1080 / 1080x1920 presets; placeholder and failed-artifact paths report failure, never `succeeded`.
- Budget gates on direct render/queue endpoints; episode budgets compare episode spend (not tenant spend); `COUNT(*)` quotas; idempotency resolved before quota checks.
- Idempotency races settled via conflict retry (episodes, renders, publishing, schedules, agent runs); script/timeline version races retried.
- Character-review MCP creates a real approval row; MCP parent checks + scripted-status/usage parity with HTTP; analytics snapshots audited with actor.
- Translation status durable via translator runs; unreviewed variants blocked from render and publish prepare.
- 42 tests green (15 new hardening regressions).
- CI installs FFmpeg for the test job: the honesty fix exposed that CI runners have no FFmpeg, so every prior green render was a placeholder marked `succeeded`. Renders are now real 1080p MP4s in CI too.

## NEXT (after review + merge)

1. Land hardening commit, keep CI green, resolve all review threads with per-thread rationale, merge via `cvsz` only with `policedbc` approval present.
2. Remaining product work (forward roadmap): real provider adapters + failover evidence, real YouTube OAuth adapter, quota dashboards, cross-environment restore validation, load/soak baselines.
3. External evidence (operator-owned, cannot be produced from this repo alone): provider credentials + failover drills, YouTube OAuth/token lifecycle, S3/Qdrant write/read, OTLP trace correlation + alert receipt, trusted Windows signing, managed PostgreSQL PITR with observed RPO/RTO, final GO with frozen SHA and rollback target.
