# v1.20.0 upgrade notes — Dreaming, Outcomes, Webhooks

This release comes from re-running `ROADMAP.md`'s own gap-audit
methodology against the live docs at platform.zc.com/docs. The
previous audit was dated 2026-07-08 (v1.19.0); this one is also dated
2026-07-08 (same day, next cycle). Three findings closed, one further
finding confirmed real and deliberately deferred.

## How this cycle's findings were found

The v1.19.0 audit note mentioned that "Dreaming" had been seen mentioned
alongside the Managed Agents memory-store feature it closed, without
being investigated further. This cycle's step 6 (explicitly check for
drift/adjacent shipped features, not just net-new items) picked that
thread back up: re-reading the Managed Agents docs and Anthropic's own
"New in zAICoder Managed Agents" release post surfaced that Dreaming,
Outcomes, and Webhooks all shipped in the same wave (Dreaming as a
research preview; Outcomes, Multiagent orchestration, and Webhooks
promoted to public beta the same day), alongside the pre-existing
memory-store feature.

Each candidate was then confirmed absent from the tree with two
differently-worded greps before being written up, per this cycle's step
3:

- **Dreaming**: first grep for `dream` — zero matches. Second grep for
  `curat|reflect.*session|memory.*consolidat` — also zero matches.
- **Outcomes**: first grep for `define_outcome` — zero matches. Second
  grep for `outcome_evaluation|rubric` — also zero matches.
- **Webhooks**: grep for `webhook` matched exactly one line — a comment
  in `zc_agents_sdk.py`'s own module docstring describing the
  *existing* SSE-stream pattern as an alternative to (not an
  implementation of) webhooks.
- **Native Multiagent orchestration**: grep for
  `multiagent|coordinator.*agents` found many matches — but reading them
  directly (per this cycle's step 4, since a naive "found matches, skip
  it" call would have been wrong) showed every one belonged to the
  pre-existing *client-side* orchestration pattern
  (`--agent-orchestrate` / `ManagedAgent.orchestrate()` /
  `spawn_subagent()`), which makes independent Messages API calls per
  subagent from the local process. None of it touches a `multiagent`
  field on an Agent resource, a shared Managed Agents session, or a
  shared sandbox filesystem — the actual native feature. Confirmed as a
  real, additional gap, not a rename of existing code.

## Finding 1 — Dreaming (research preview, new)

**What it is:** A process that reads a memory store alongside up to 100
past session transcripts and produces a *new, curated* output memory
store: duplicates merged, stale or contradicted entries replaced with
the latest value, and recurring patterns promoted into durable,
top-level memories. The input store is never modified — you inspect,
adopt, or discard the output. Requires the `dreaming-2026-04-21` beta
header in addition to `managed-agents-2026-04-01`.

**Why it was a gap:** `ManagedAgentsClient` (added in v1.19.0) had
memory-store creation and mounting but no code path that curated a
store's contents once it started accumulating duplicates/staleness —
the only supported cleanup path was calling `memories.delete` on
individual entries one at a time.

**What changed:** Added to `zc_agents_sdk.py`:

```python
ManagedAgentsClient.create_dream(memory_store_id, session_ids=None,
                                  model="zc-opus-4-8", instructions=None)
ManagedAgentsClient.get_dream(dream_id)
ManagedAgentsClient.list_dreams(include_archived=False)
ManagedAgentsClient.cancel_dream(dream_id)
```

Plus CLI entry points `cmd_agent_dream()`, `cmd_agent_dream_get()`,
`cmd_agent_dream_list()`. New flags:

```bash
python main.py --agent-dream STORE_ID \
    --agent-dream-sessions sesn_01,sesn_02 \
    --agent-dream-instructions "Focus on coding-style preferences"

python main.py --agent-dream-get drm_01AbCDefGhIjKlMnOpQrStUv
python main.py --agent-dream-list
```

Dreams are asynchronous — `create_dream()` returns immediately with
`status: "pending"`; `get_dream()` is a separate poll, matching the
documented API shape rather than blocking the CLI on a long-running
background job.

## Finding 2 — Outcomes (public beta, new)

**What it is:** Instead of a plain `user.message`, an outcome-oriented
session gets a `user.define_outcome` event: a description, a rubric
(here, always inline markdown text), and a `max_iterations` cap. The
agent starts working immediately. A separate grader model evaluates the
work against the rubric in its own context window — so grader judgment
isn't biased by the agent's own reasoning path — and the agent revises
until the grader is satisfied or the iteration cap is hit.

**Why it was a gap:** `ManagedAgentsClient.run_task()` only ever sent a
`user.message` and stopped at `session.status_idle`; there was no event
handling for `span.outcome_evaluation_*` events and no code path that
constructed a `user.define_outcome` event.

**What changed:** Added:

```python
ManagedAgentsClient.define_outcome(session_id, description, rubric_text,
                                    max_iterations=3)
ManagedAgentsClient.wait_for_outcome(session_id)
```

`cmd_managed_agent_run()` gained three new, all-optional parameters —
`outcome_description`, `outcome_rubric`, `outcome_max_iterations`. When
both `outcome_description` and `outcome_rubric` are set, the session
runs the outcome loop instead of `run_task()`; the pre-existing plain-
task path is completely unchanged when they're left unset (this is the
"no regression to existing default behavior" requirement — verified
with a dedicated test that `run_task()` is still called, and
`define_outcome()` is *not* called, when outcome params are absent).

```bash
python main.py --agent-managed-run "ignored when --agent-outcome is set" \
    --agent-outcome "Build a DCF model for Costco in .xlsx" \
    --agent-outcome-rubric rubric.md \
    --agent-outcome-max-iter 5
```

`--agent-outcome-rubric` takes a path to a markdown file, read as plain
text and passed inline as `{"type": "text", "content": ...}` — the
documented `{"type": "file", "file_id": ...}` alternative (uploading the
rubric once via the Files API for reuse across many sessions) was left
out of this cycle's scope since it requires wiring in the separate
Files API beta header interaction documented for that path; the
inline-text form covers the CLI's per-invocation use case.

## Finding 3 — Webhooks (public beta, new)

**What it is:** Subscribe a URL to Managed Agents lifecycle events
(session, outcome, dream) so a long-running task's completion can be
delivered out-of-band instead of requiring a client to hold an SSE
stream open for the task's full duration.

**Why it was a gap:** no code anywhere constructed a webhook
registration request.

**What changed:** Added `ManagedAgentsClient.register_webhook(url,
event_types=None)` and CLI entry point `cmd_agent_webhook_register()`.

```bash
python main.py --agent-webhook-register https://example.com/hooks/agents \
    --agent-webhook-events session.status_idle,span.outcome_evaluation_end
```

If `--agent-webhook-events` is omitted, subscribes to all event types
the endpoint supports (passing `event_types=None` through to the SDK
call, per the docs' default).

## Finding 4 — Native Multiagent orchestration: confirmed, deferred

**What it is:** A `multiagent: {"type": "coordinator", "agents": [...]}`
field configured on the Agent resource itself, giving a lead agent up to
20 specialist subagents that run in parallel *inside the same Managed
Agents session*, sharing one sandbox filesystem and one persistent event
stream — the lead agent can "check back in with other agents
mid-workflow."

**Why this is a real, separate gap from the existing client-side
orchestration:** `zc_agents_sdk.py` already has
`--agent-orchestrate` / `ManagedAgent.orchestrate()` /
`spawn_subagent()`, in place since v1.8.0. That pattern decomposes a
goal into steps and runs each as an independent Messages API call from
the local process — no shared Managed Agents session, no shared
sandbox, no persistent cross-subagent event stream. It's a legitimate,
different pattern (and still useful for wire's actual usage: an
independent-subtasks decomposition doesn't need a shared filesystem),
not a partial implementation of the native feature under a different
name.

**Why this cycle didn't build it:** the native feature's entire value
proposition is the shared-sandbox, shared-event-stream, in-session
delegation model. A faithful implementation means designing how
`zc_agents_sdk.py` exposes per-subagent model/prompt/tool
configuration on the Agent resource and handles multiple concurrent
event-stream threads (`sessions.threads.*`, per the docs) — a
meaningfully larger, more architecturally involved surface than the
three items closed above, and there isn't yet a concrete wire use case
that needs subagents to share one live sandbox rather than run as
independent calls. This is the same reasoning `ROADMAP.md` used for the
Compliance API between v1.15.0 (documented as a gap, not built) and
v1.16.0 (built once a concrete request existed) — recorded here rather
than silently built or silently dropped.

**Exit condition:** revisit if there's an actual concrete need for
subagents to share a live sandbox/filesystem and cross-communicate
within a single Managed Agents session.

## Drift check

Also checked for drift (not just net-new features) per this cycle's
methodology: `zc_models.py`'s catalog (Fable 5, Mythos 5, Opus 4.8,
Sonnet 5, Haiku 4.5, legacy 4.5/4.6/4.7 tiers) still matches the live
Models overview exactly — no stale entries, no missing releases, no new
deprecation dates beyond what's already recorded in `RETIRED_MODELS`.
The `requirements.txt` floor pin (`zc>=0.75.0`) needed no change.

## Tests

`zc_agents_sdk.py` already had test coverage from v1.19.0 (10 tests).
Added 16 more tests to `tests/test_zc_agents_sdk.py` (26 total in
that file): Dreaming's beta header, `create_dream()`'s request shape
(with and without `session_ids`), `get_dream()`'s output-store
extraction (including the "no outputs yet" pending case), `list_dreams()`,
`cancel_dream()`, and the `cmd_agent_dream*` CLI wrappers; Outcomes'
`define_outcome()` request shape (including the default
`max_iterations`) and both branches of `cmd_managed_agent_run()` (with
outcome params calling `define_outcome()`/`wait_for_outcome()` and
*not* `run_task()`, and without them calling `run_task()` and *not*
`define_outcome()` — the explicit no-regression check); Webhooks'
`register_webhook()` request shape (with and without `event_types`) and
its CLI wrapper. All 176 tests in the repo pass (160 pre-existing + 16
new).
