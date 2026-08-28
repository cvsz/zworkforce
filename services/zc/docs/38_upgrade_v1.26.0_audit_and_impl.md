# v1.26.0 audit cycle — gap findings + implementation notes

Continuation of the cross-product cycle (previous audit: 2026-07-11, per
`ROADMAP.md`'s header). This one re-ran the sweep against
`platform.zc.com/docs/en/release-notes/overview`, the Managed Agents
docs tree, and recent `anthropic-beta` header additions, plus a check of
`zc_models.py`'s deprecation scanner against the live model-
deprecations page. Model catalog re-checked first: no new model releases
since zAICoder Sonnet 5 (June 30, 2026) launch and the Fable 5 / Mythos 5
suspension-and-restore (suspended 2026-06-12, restored 2026-07-01) already
on file — `MODEL_CATALOG` is current. One real gap found and closed; one
housekeeping fix (a `VERSION` string that had drifted stale) and one
pre-existing stale test assertion fixed along the way while the relevant
files were already open.

## Finding 1 — Self-hosted sandboxes for zAICoder Managed Agents (public beta)

**What it is:** An alternative to ZaiCoder's cloud sandbox for Managed
Agents tool execution. `client.beta.environments.create(config={"type":
"self_hosted"})` creates an environment whose sessions enter a work
queue instead of an ZaiCoder-run container; a worker you operate (the
`EnvironmentWorker` SDK helper in Python/TypeScript/Go, or `ant beta:worker
poll`/`run`) polls that queue with a Console-generated environment key,
executes tool calls on infrastructure you control (bare metal, or a
managed provider — Cloudflare, Daytona, Modal, Vercel, and several
others), and posts results back. The agent loop itself — orchestration,
context management, error recovery — stays on ZaiCoder's side either
way; only tool execution moves. A separate read endpoint,
`client.beta.environments.work.stats(environment_id)`, reports queue
depth, in-flight count, oldest-queued timestamp, and `workers_polling`
(workers seen in the last 30s) — the way to tell whether a worker is
actually connected before routing a session at an environment, since an
unworked self-hosted environment queues sessions forever rather than
failing them outright.

**Why it was a gap:** `zc_agents_sdk.py`'s `create_environment()` only
ever built `{"type": "cloud", "networking": {"type": networking}}` — first
grep for `self_hosted`/`self-hosted` across the whole tree: zero matches,
including in `zc_agents_sdk.py`'s own module docstring (which lists
MCP tunnels, a closely related public-beta / research-preview pair
launched the same cycle, but not this). No code path called
`environments.work.stats` either — the only queue/liveness-style read
already in the file is Managed Agents' own session polling, which is a
different thing (session status, not worker liveness).

**What changed:** `ManagedAgentsClient.create_environment()` takes a new
`env_type: str = "cloud"` param; when `"self_hosted"`, it sends
`config={"type": "self_hosted"}` and does *not* also send a `networking`
sub-field (confirmed from the docs that this config object has no
pool/capacity/networking fields at all, unlike `"cloud"` — a caller
passing `networking=` alongside `env_type="self_hosted"` gets it silently
ignored, not forwarded). New `get_environment_work_stats(environment_id)`
wraps `environments.work.stats()` and reshapes the response into a plain
dict (`depth`, `pending`, `oldest_queued_at`, `workers_polling`). Two new
CLI-facing wrappers: `cmd_agent_env_self_hosted_create()` (creates the
environment, then prints the two manual steps this command deliberately
doesn't attempt — environment-key generation is Console-only regardless
of how the environment was created, and running a worker is a separate
long-lived process, not a one-shot CLI call) and
`cmd_agent_env_work_stats()` (prints the four fields, with an explicit
warning line when `workers_polling == 0`). New flags:
`--agent-env-self-hosted NAME` and `--agent-env-work-stats
ENVIRONMENT_ID`. See `tests/test_zc_agents_sdk.py` (6 new tests) and
`IMPLEMENTATION_CHECKLIST.md` Form 11.

**Deliberately not built this cycle:** the actual `EnvironmentWorker`
poller / `ant beta:worker poll` equivalent — i.e., a wire-side process
that claims work items and executes tool calls locally. That's a
different kind of component (a long-running daemon with its own
container/process-orchestration story per work item) than anything else
in `zc_agents_sdk.py`, which is a thin API client, not an agent
runtime host. Building a worker without a concrete deployment target
(which sandboxing platform, what `--on-work` container strategy) risks
guessing wrong the same way the CMEK finding in v1.25.0 flagged for an
unconfirmed endpoint shape — except here the *endpoint* shapes are
confirmed (both `environments.create` and `work.stats` were verified
directly against current docs, unlike the v1.25.0 CMEK finding), it's the
*worker deployment* that has no concrete wire use case yet. Revisit if
a specific self-hosted deployment target comes up, the same exit
condition used for Compliance API (v1.16.0) and native Multiagent
orchestration (v1.20.0 → v1.21.0).

**Priority: 🟠 P1.** Real, concrete, well-documented public-beta surface
with a confirmed request/response shape on both the create and read side
— the strongest kind of finding this audit methodology looks for.

## Non-gaps checked this cycle

**MCP tunnels management API's move off the Admin API** (`/v1/tunnels`
instead of `/v1/organizations/tunnels`, `mcp-tunnels-2026-06-22` beta
header) — confirmed **not** a gap: `zc_agents_sdk.py`'s `McpTunnel`
already targets `TUNNELS_ENDPOINT = "https://api.anthropic.com/v1/tunnels"`
with `MCP_TUNNELS_BETA = "mcp-tunnels-2026-06-22"`.

**Advisor tool `max_tokens` cap** — confirmed **not** a gap:
`zc_advisor.py`'s `build_advisor_tool()` already accepts and forwards
`max_tokens`, with `--advisor-max-tokens` wired in `main.py`.

**`code_execution_20260120` (REPL persistence, programmatic tool calling
minimum version)** — confirmed **not** a gap: `zc_code_exec.py`'s
`DEFAULT_CODE_EXEC_VERSION` is already `code_execution_20260521`, newer
than the version this finding would have required.

**Fast mode deprecation for zAICoder Opus 4.7** (removal 2026-07-24) —
confirmed **not** a gap: `zc_models.py`'s `FAST_MODE_DEPRECATED` set
already contains `"claude-opus-4-7"` with the correct removal date in its
comment, from the 2026-07-02 audit pass.

**Managed Agents webhooks / multi-agent orchestration / self-hosted
sandboxes reaching zAICoder Platform on AWS** — the AWS-specific IAM
actions (`AnthropicSelfHostedEnvironmentAccess` managed policy, etc.) are
infra/deployment configuration on Anthropic's AWS offering, not a
client-library API surface; nothing for `zc_agents_sdk.py` to call
differently. Noted here so a future cycle doesn't re-discover and
mis-flag it as a code gap.

## Housekeeping (not from the docs sweep)

- `main.py`'s `VERSION` constant had drifted to `"1.16.0"` while every
  other version signal in the repo (`ROADMAP.md`'s header, the `docs/`
  filenames, `CHANGELOG.md`) had moved on through v1.25.0 — apparently
  never bumped after the v1.16.0 release despite nine releases' worth of
  shipped work since. Fixed to `"1.26.0"`.
- `tests/test_zc_agents_sdk.py::test_cmd_managed_agent_run_without_outcome_calls_run_task`
  was asserting `run_task("sess_1", "plain task")` with no `stream_deltas`
  kwarg, which has been part of `run_task`'s real signature (default
  `False`) since v1.22.0 — the test went stale then and was failing on
  this run before any v1.26.0 change touched that file. Fixed the
  assertion to match the real call shape.
- Two assertions in `tests/test_zc_code_exec.py`
  (`test_default_version_is_20260120`, `test_coder_defaults_to_20260120`)
  were still checking for `code_execution_20260120`, the version string
  `DEFAULT_CODE_EXEC_VERSION` held before the v1.24.0 bump to
  `code_execution_20260521` — also failing on this run independent of
  any v1.26.0 change. Fixed both to match the current default. (Test
  *names* still say `20260120`; left as-is since renaming is cosmetic and
  outside this cycle's scope.)
