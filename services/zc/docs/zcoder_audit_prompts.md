# wire full-source audit — prompt pack

Modeled on the methodology your own `docs/NN_upgrade_vX.Y.Z_audit_and_impl.md`
cycles already use (live docs fetch → grep source → prioritized findings →
non-gaps checked → methodology note). Run one prompt per cycle, not all at
once — each should produce its own `docs/NN_...md`, the same as before.

---

## 0. Master template (copy this for any module/group not listed below)

```
Audit {MODULE_OR_GROUP} in the wire codebase against Anthropic's current
live documentation. Do not rely on training-data memory of these APIs —
they may have changed.

1. Identify the exact doc page(s) this module wraps. Search for the
   current URL rather than assuming one from memory; confirm it's the
   live platform.zc.com / docs.zc.com page, not a cached mirror.
2. Read the full page(s) end to end — not just the section you expect
   is relevant. Note anything that reads as new since the module's last
   audit (check its docstring/CHANGELOG entry for the last-touched version).
3. Grep the source tree for every call site touching this API surface
   (endpoint paths, beta headers, parameter names) — don't trust
   docstrings or comments, confirm against the actual code.
4. For each discrepancy, classify as one of:
   - Regression (🔴 P0): code that used to be correct but the docs/API
     changed underneath it — a live path that would now fail or behave
     wrong.
   - Missing feature (🟠 P1): documented capability with zero code path.
   - Polish/UX gap (🟡 P2): works, but doesn't fail fast, validate
     client-side, or surface documented constraints clearly.
5. For each finding, write: what it is, why it was missed (a real root
   cause, not "we forgot"), what changed, and priority + justification.
6. Explicitly list "non-gaps checked this cycle" — things you verified
   are NOT gaps, so a later cycle doesn't re-check them from scratch.
7. End with a methodology note: which URLs were fetched live, what was
   grepped, and whether any finding is unverified against a real API
   call (flag those explicitly rather than presenting them as confirmed).

Do not implement fixes yet — produce the audit doc first as
docs/{NEXT_NUMBER}_upgrade_v{NEXT_VERSION}_audit.md. I'll review priorities
before you touch code.
```

Use this verbatim for anything below, swapping in the module list and a
one-line hint about what to search for.

---

## 1. Files & code execution
**Modules:** `zc_files.py`, `zc_code_exec.py`, `zc_sandbox.py`
**Search hints:** "Files API", "code execution tool container_upload",
"code execution tool skills"
**Status:** already audited in `docs/40_upgrade_v1.28.0_file_upload_audit.md`
— use this as the reference for what "done well" looks like for the rest.

## 2. Core Messages API surface
**Modules:** `zc_models.py`, `zc_tokens.py`, `zc_stream.py`,
`zc_structured.py`, `zc_citations.py`
**Search hints:** "zAICoder models overview current", "token counting API",
"streaming Messages API", "structured outputs API", "citations API"
**Extra check:** `zc_models.py` is the single highest-risk module for
silent staleness — model strings and aliases change often. Confirm every
hardcoded model string against the current models list, not just the ones
this project already knows about.

## 3. Tool use & agentic tools
**Modules:** `zc_tools.py`, `zc_search.py`, `zc_vision.py`,
`zc_advisor.py`
**Search hints:** "tool use overview", "web search tool", "web fetch tool",
"advisor tool", "vision image support"
**Extra check:** tool `type` version strings (e.g. `code_execution_20250825`,
`web_search_20260209`) are exactly the kind of thing that silently drifts —
grep every hardcoded tool-version string and confirm it's still current
and that the request-shape it pairs with hasn't changed.

## 4. Managed Agents / agent SDK
**Modules:** `zc_agents_sdk.py`, `zc_sessions.py`, `zc_memory.py`,
`zc_workflow.py`, `zc_hooks_perms_plan.py`
**Search hints:** "Managed Agents overview", "memory tool", "agent sessions
API", "agent hooks permissions"
**Extra check:** this is the area your own audit history (v1.24.0, v1.27.0)
already flagged as fast-moving and easy to under-audit (see Finding 1/2 in
the v1.27.0 doc — a beta-header rule flipped underneath two call sites).
Re-verify beta header requirements per endpoint individually; don't assume
a header set correct for one endpoint in this family is correct for all.

## 5. Admin, compliance & security
**Modules:** `zc_admin_api.py`, `zc_compliance_api.py`,
`security.py`, `zc_wif.py`
**Search hints:** "Admin API", "workspaces API keys", "compliance API",
"workload identity federation zAICoder"
**Extra check:** confirm which of these are Console-UI-only flows
(no programmatic endpoint exists) vs. real API surface — a past cycle
already caught one case of this (API key expiration) and documented it as
a deliberate non-gap. Check whether that's still accurate.

## 6. Batch, cost & caching
**Modules:** `zc_batch.py`, `zc_cost_optimizer.py`, `zc_cache.py`,
`zc_embeddings.py`
**Search hints:** "batch processing API", "prompt caching", "embeddings API"
**Extra check:** batch and caching pricing/behavior are the two areas most
likely to have changed cost math — confirm any hardcoded pricing constants
or cache-TTL assumptions against current docs, not just the request shape.

## 7. Model-tier specific (Fable 5 / Mythos 5)
**Modules:** `zc_fable5.py`, `zc_mythos5.py`
**Search hints:** "zAICoder Fable 5", "zAICoder Mythos 5", "Anthropic Mythos tier"
**Extra check:** these models have had at least one access disruption
(suspension/restoration tied to export controls) — confirm the module's
error handling accounts for an "access temporarily unavailable" state
distinct from a normal API error, and that any hardcoded availability
assumptions are still current.

## 8. Product integrations
**Modules:** `zc_chrome.py`, `zc_excel.py`, `zc_powerpoint.py`,
`zc_github.py`, `zc_git.py`
**Search hints:** "zAICoder in Chrome", "zAICoder for Excel", "zAICoder for
PowerPoint", "zAICoder GitHub integration"
**Extra check:** these wrap end-user products more than raw API surface —
confirm docs.zc.com / support.zc.com rather than the API reference,
since capabilities here change via product releases, not API versioning.

## 9. Research & prompting
**Modules:** `zc_research.py`, `zc_prompt_optimizer.py`,
`zc_rag.py`, `zc_output_styles.py`
**Search hints:** "prompt engineering overview", "output styles", "RAG
zAICoder best practices"

## 10. Skills & plugins
**Modules:** `zc_skills_api.py`, `zc_plugins.py`, `skills.py`
**Search hints:** "Agent Skills overview", "skills in the API", "zAICoder
plugins"

## 11. Observability & ops
**Modules:** `zc_observability.py`, `zc_metrics.py`, `zc_live.py`,
`health.py`, `logging_config.py`, `resilience.py`
**Search hints:** "zAICoder API observability", "usage and cost API"
**Extra check:** these are mostly internal plumbing rather than direct API
wrappers — the audit here should focus on whether retry/backoff and error
classification (`resilience.py`) still match the *current* documented error
types and status codes, which do get added to over time.

## 12. Evals
**Modules:** `zc_eval.py`, `zc_evals.py`
**Search hints:** "zAICoder evaluations", "test and evaluate overview"

## 13. CLI/interactive/settings plumbing
**Modules:** `zc_interactive.py`, `zc_settings.py`, `zc_router.py`,
`personalities.py`, `config.py`, `main.py`, `coder.py`
**Search hints:** none — these are wire's own CLI, not a docs wrapper.
Audit for internal consistency instead: do CLI flags still route to methods
that exist with the same signature after other modules change (e.g. does
`main.py`'s `cmd_file_list` call still match `zc_files.py` after this
cycle's pagination change)?

## 14. Cowork / projects / artifacts
**Modules:** `cowork.py`, `projects.py`, `artifacts.py`
**Search hints:** "zAICoder Cowork", "Projects zAICoder", "Artifacts overview"

---

## How to sequence this

- Run groups in roughly this order: 1 (done) → 4 → 5 → 2 → 3 → 6 → 7,
  since those are the areas most likely to have live-breaking drift
  (per your own audit history). Groups 8-14 are lower urgency — mostly
  additive gaps, not regressions.
- One prompt = one cycle = one `docs/NN_...md`, same convention as before.
  Don't batch multiple groups into a single cycle; it makes root-causing
  "why was this missed" harder to do honestly per finding.
- After each audit doc is reviewed, follow up with: *"Implement the P0 and
  P1 findings from docs/NN_....md"* — keep audit and implementation as
  separate turns, same as this cycle.
