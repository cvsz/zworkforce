# wire v1.33.0 — Deep Audit Report

**Scope:** `wire-v1_33_0.zip` (current release), diffed against `wire-v1_32_0.zip` (previous release)
**Method:** Static analysis (AST + grep across all 91 Python files / ~26,200 LOC), manual line-by-line review of every security- and correctness-critical module, independent re-derivation of the project's own CLI-wiring test, and a full file-level diff between the two supplied archives.
**Not done, and why:** This sandbox has no network access, so `zc`, `pytest`, `fastapi`, `pydantic`, and `uvicorn` could not be installed. I could not execute the test suite or actually run the FastAPI backend. Every finding below is either (a) confirmed by direct code inspection with exact file:line citations, or (b) explicitly marked as inferred/unverified. Nothing here is a guess dressed up as a fact.

---

## 1. Executive Summary

The uploaded instructions describe continuing to build a **multi-tenant, CLI-to-API SaaS product** — organizations, workspaces, a backend the CLI talks to, per-tenant authorization and audit, database migrations, container smoke tests. That product does not exist here, and per the repo's own `ARCHITECTURE.md` was never the design. **wire is a single-user, local Python CLI that talks directly to Anthropic's real public APIs using the user's own API key**, plus one optional local FastAPI+vanilla-JS web UI. Section 3 explains why this matters for how to read the rest of this report — most of the uploaded prompt's specific invariants (tenant scoping, DB migrations, job-queue cancellation) don't have a referent in this codebase's actual shape, so I audited it against what it actually is rather than mechanically checking boxes that don't apply.

Within that real shape, the codebase is a mix of genuinely good engineering and serious, concrete defects:

- **A dedicated security module (`security.py`) that centralizes path-traversal, file-size, secret, URL, and filename validation is never called from anywhere except its own test file.** Its tests prove the functions work; nothing in the product uses them.
- **Two CLI commands (`--project-delete`, `--artifact-delete`) recursively delete a caller-supplied path with zero sanitization** — an absolute path or a `..`-laden ID escapes the intended directory entirely, because of how Python's `pathlib` handles path joining.
- **The flagship coding-agent's file tools (Read/Write/Edit) and shell tool (Bash) have no path confinement and no sandboxing by default.** The only mitigation is opt-in and, by its own docstring, "best-effort" and bypassable.
- **A permission mode (`acceptEdits`) silently behaves as "approve everything, including Bash, with no confirmation"** instead of its documented "ask before non-edit tools" — because the code has no branch for that mode at all. This is the default mode for subagents and for custom/plugin slash commands.
- **The optional web UI has no authentication, binds to all network interfaces by default, allows wildcard CORS, and lets any caller overwrite the user's persisted API key** via an unauthenticated `POST`.
- **The same "hardcoded temperature crashes Sonnet-5-family models" bug was fixed in one place and left in three others**, including the web UI's own streaming-chat endpoint, which is broken out of the box against its own default model.
- Conversely: the retry/circuit-breaker layer, the error taxonomy, the core single-shot generation path, CLI argument wiring (independently re-verified), and this release's actual new feature (native Word/PDF chat) are all solid, honestly documented, and correctly connected end-to-end.

Full detail, file:line citations, and a prioritized fix list follow.

---

## 2. What's Actually In The Box

```
91 Python files, ~26,230 LOC (root + tests + webapp)
65 root-level modules (49 of them zc_*.py feature modules)
149 total files, including 46 docs/ markdown files, a Dockerfile, a Makefile, tests/, webapp/
No git history shipped with either archive — comparisons below are file-level diffs of the two zips.
```

No database. No server the CLI talks to. No user accounts, sessions, or multi-tenant model. `pip`-installable dependencies (`zc`, `fastapi`, `pydantic`, `uvicorn`, `textual`) were unavailable in this sandbox (no network egress), which is itself relevant — see Finding **BUG-4**.

---

## 3. Framing: What This Product Actually Is

`ARCHITECTURE.md` is explicit and, on inspection, accurate: wire is "a CLI that wraps Anthropic's public API," run locally, authenticated with the user's own `ANTHROPIC_API_KEY`. I confirmed this by grep: **20 files import the `anthropic` SDK directly**, and **`ANTHROPIC_API_KEY` is read directly inside CLI-layer files** (`main.py`, `coder.py`, `tui.py`, `zc_embeddings.py`, `zc_code.py`). There is no backend that owns provider credentials on the CLI's behalf.

The uploaded execution-loop prompt assumes the opposite: a CLI that talks only to *your own* backend API, which then holds provider credentials server-side, with per-organization/workspace tenant isolation, authenticated mutating operations, database migrations, and container startup checks. Those requirements describe a different product. Two consequences for this report:

1. Invariants like "CLI imports no provider SDK" and "never store provider credentials in client-side configuration" are **violated by design**, not by oversight — that design is what `ARCHITECTURE.md` documents and what the README sells ("bring your own key, runs on your machine"). I'm noting it for completeness, not scoring it as a bug to fix by rearchitecting.
2. Where the uploaded checklist has no referent (org/workspace tenant scoping, DB migration-from-empty, job-queue cancellation, container smoke tests — there is a `Dockerfile` but it packages the optional local webapp, not a multi-tenant service), I looked instead for the *analogous* real risk. That's exactly where the worst findings in this report live: "every mutating operation is authorized and audited" doesn't map onto this codebase, but "every filesystem-mutating operation is path-confined" does, and that's where **SEC-2/SEC-3/SEC-5** are.

The one piece of this codebase that *does* resemble a multi-tenant backend — `webapp/backend/server.py` — is audited on those terms in **SEC-7**, because it's the one place a "CLI-to-API" reading is actually apt.

---

## 4. Complete Feature Inventory

Extracted directly from `main.py`'s argument parser (the ground truth for what's user-reachable), not from prose docs. **51 feature groups, 420 flags.** Independently re-verified: every one of the 420 argparse destinations is read somewhere in the dispatch code (0 orphaned flags), and all but one `cmd_*` function across the 49 feature modules is reachable from `main.py` — see **§7 Wiring Integrity** for how that was checked and the one documented exception.

| # | Group | Flags | What it does |
|---|-------|:---:|---|
| 1 | Global | 12 | Model/temperature/max-tokens selection, interactive TUI, health checks, service tier, geo routing |
| 2 | Skills & Agents | 6 | Built-in "skill" and "agent persona" system prompts, personalities |
| 3 | Feature Projects | 16 | Local project workspaces: create/list/show/plan/run/archive/delete, task tracking |
| 4 | Artifacts | 21 | Versioned code/doc artifacts: create/iterate/diff/tag/export/delete |
| 5 | Extended Thinking | 8 | Thinking-budget/effort control, interleaved thinking, adaptive effort |
| 6 | Web Search & Fetch | 6 | ZaiCoder's hosted web_search / web_fetch tools |
| 7 | Vision | 7 | Image/PDF vision, OCR, code-from-screenshot, visual diffing |
| 8 | Batch API | 8 | Async batch message submission/status/results/cancel |
| 9 | Prompt Caching | 10 | Cache control, TTL, warm-up, diagnostics, multi-turn caching |
| 10 | Tool Use | 11 | Generic tool-calling agent, server-side tools, context management, compaction |
| 11 | Advisor Tool | 4 | A bounded-use "advisor" tool-calling pattern |
| 12 | Embeddings | 5 | Voyage embeddings + similarity |
| 13 | Structured Outputs | 5 | JSON-schema-constrained generation, extraction |
| 14 | Files API | 7 | Upload/list/delete/download/ask-about files |
| 15 | Code Execution | 4 | ZaiCoder's hosted code-execution tool |
| 16 | Token Counting | 2 | Pre-flight token counting |
| 17 | Citations & RAG | 3 | Citations-enabled responses |
| 18 | Models API | 8 | List/inspect models, deprecation checks, guided model upgrades |
| 19 | zAICoder Fable 5 / Mythos 5 | 5 | Fable 5 access + fallback-chain configuration |
| 20 | zAICoder Mythos 5 (limited access) | 2 | Mythos 5 access |
| 21 | Admin API | 27 | Org usage/cost reporting, API-key list/revoke (not create — see **§8**), spend limits, rate limits, CMEK |
| 22 | Workload Identity Federation | 13 | OIDC token exchange, service accounts, issuers, trust rules |
| 23 | Compliance API | 25 | Activity feed, chat/file/project export & delete, org/group directory |
| 24 | Agent Skills API | 2 | Platform skill_id listing/info |
| 25 | Computer Use | 1 | ZaiCoder's hosted computer-use tool |
| 26 | Agent SDK | 61 | Sessions, orchestration, managed runs, memory stores, dreams, outcomes, webhooks, vault/credentials, scheduling, multi-agent review |
| 27 | Cowork | 6 | Multi-file/multi-step batch task runner |
| 28 | Excel / Data Chat | 4 | Spreadsheet chat (native + local fallback) |
| 29 | PowerPoint / Slide Chat | 3 | Slide-deck chat (native + local fallback) |
| 30 | Word / PDF Chat | 4 | **New in v1.33.0** — Skills-API-only doc chat, no local fallback (by design — see **§9**) |
| 31 | Browse | 4 | Browser-automation-style agent loop |
| 32 | zAICoder | 25 | The flagship coding agent: sessions, MCP, hooks, checkpoints, subagents, slash commands, sandboxing |
| 33 | Plugins & Marketplaces | 12 | Install/list/enable/disable third-party plugin bundles |
| 34 | Memory | 9 | Long-term memory store (add/recall/forget/stats) |
| 35 | Sessions & Checkpoints | 4 | List sessions, show, list checkpoints, away-summary |
| 36 | zai-live | 1 | Live/streaming session mode |
| 37 | Deep Research | 3 | Multi-step research agent |
| 38 | RAG | 6 | Local folder indexing + retrieval |
| 39 | Evaluation | 5 | Eval-suite running/comparison/scaffolding |
| 40 | Git Integration | 7 | Commit-message generation, PR description, changelog, blame explain |
| 41 | GitHub Integration | 6 | PR review, issue triage, commit summarization |
| 42 | Multi-Agent Router | 5 | Task routing across specialized agent configs |
| 43 | Cost Optimizer | 4 | Model-downgrade-for-cost heuristics, cost summary |
| 44 | Prompt Optimizer | 8 | Prompt scoring, A/B testing, a small prompt library |
| 45 | Observability | 5 | Latency/error-rate reporting, log tail |
| 46 | Metrics | 5 | Local usage log show/export/clear |
| 47 | Workflows | 3 | Scriptable multi-step workflow runner |
| 48 | Hooks | 4 | Lifecycle hook registration (pre/post tool use, etc.) |
| 49 | Permissions | 3 | Tool-permission allowlist management |
| 50 | Plan Mode | 3 | Read-only "plan before executing" agent mode |
| 51 | Settings | 2 | Settings display, status-line customization |

This is a large, genuinely broad feature surface — it tracks Anthropic's real public API surface closely (Messages, Batches, Files, Admin, Compliance, Agent SDK, Skills, Computer Use) plus a substantial amount of original CLI/agent tooling on top (zAICoder clone, plugins, workflows, routing, cost/prompt optimizers). The wiring connecting flags to implementations is, with the exceptions below, sound.

---

## 5. Findings — Critical (Security)

### SEC-1: The centralized security module is built, tested, and never used

`security.py` defines `safe_resolve()` (path-traversal guard), `check_file_size()`, `contains_secret()`/`assert_no_secret()`, `validate_url()` (scheme allowlist), `validate_name()`, and `env_flag()`. Its docstring and `ARCHITECTURE.md` both state it replaces ad hoc checks previously "duplicated across `zc_files.py`, `zc_code_exec.py`, `zc_sandbox.py`, `projects.py`, and `artifacts.py`."

```
grep -rn "safe_resolve\|check_file_size\|contains_secret\|assert_no_secret\|validate_url\|validate_name\|env_flag" --include="*.py" .
```
returns **zero matches outside `security.py` itself and `tests/test_security.py`.** None of the five modules named in its own docstring import it.

This isn't a hypothetical gap — `tests/test_security.py` proves the functions are *correct*: `test_safe_resolve_blocks_traversal` and `test_safe_resolve_blocks_absolute_escape` both pass `"../../etc/passwd"` and `"/etc/passwd"` and assert a `SecurityError` is raised. Had `projects.py`'s `delete_project()` called `security.safe_resolve(project_id, PROJECTS_DIR)` instead of raw path-joining, **SEC-2 below would not exist** — the exact test protecting against it already exists, it's just wired to nothing.

### SEC-2: `--project-delete` recursively deletes an arbitrary path

`projects.py:30-31`:
```python
def _project_path(project_id: str) -> Path:
    return _projects_dir() / project_id
```
`projects.py:159-163`:
```python
def delete_project(self, project_id: str) -> bool:
    pp = _project_path(project_id)
    if pp.exists():
        shutil.rmtree(pp)
```
wired directly to user input at `main.py:1349-1350`:
```python
if args.project_delete:
    from projects import ProjectManager; ProjectManager().delete_project(args.project_delete)
```
`args.project_delete` is a raw string from `--project-delete ID` (`main.py:137`, no `type=` validator). Two independent escape routes:
- **Absolute path:** in Python's `pathlib`, `Path(base) / "/some/abs/path"` discards `base` entirely and evaluates to `/some/abs/path`. `--project-delete /home/you/Documents` deletes `/home/you/Documents`, not anything under the projects directory.
- **Relative traversal:** `--project-delete ../../` walks out of the projects directory before `shutil.rmtree` ever runs.

No confirmation prompt, no dry-run, no allowlist check — the same codebase's Compliance-API deletions require an explicit `--compliance-yes` flag as a safety gate; this one has none.

### SEC-3: `--artifact-delete` — identical vulnerability

`artifacts.py:42-43`:
```python
def _artifact_path(artifact_id: str) -> Path:
    return _artifacts_dir() / artifact_id
```
`artifacts.py:281-286`:
```python
def delete(self, artifact_id: str) -> bool:
    ap = _artifact_path(artifact_id)
    if ap.exists():
        shutil.rmtree(ap)
        return True
    return False
```
wired at `main.py:1381-1382`. Same absolute-path and `..`-traversal escape as SEC-2, byte-for-byte the same missing guard.

**Related, lower severity:** `ArtifactManager.export(output_path=...)` writes file content to a caller-supplied path with no validation at all — an arbitrary-file-*write* primitive, not just delete, if `output_path` is ever fed by anything other than a human typing at a terminal (see SEC-5 for why that's not a hypothetical concern in this codebase).

### SEC-4: The generic tool-agent's demo file tools have no confinement

`zc_tools.py`'s `build_code_tools_registry()` (wired to `--tool-agent`, `main.py:1729-1731`) registers:
```python
def read_file(path: str) -> str:
    with open(path) as f: return f.read()
def write_file(path: str, content: str) -> str:
    with open(path, "w") as f: f.write(content)
```
No path confinement, no use of `security.py`. Any prompt that gets the model to call these with `/etc/passwd` or `~/.aws/credentials` succeeds.

### SEC-5: The flagship coding agent's file and shell tools have no confinement by default

This is the most consequential finding in the report, because `zc_code.py`'s `CodeAgent` is the product's primary feature, not an edge case.

`zc_code.py:804-821` (Read/Write/Edit):
```python
if name == "Read":
    p = Path(cwd) / inputs["path"]
    return p.read_text()[:8000]
elif name == "Write":
    p = Path(cwd) / inputs["path"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(inputs["content"])
elif name == "Edit":
    p = Path(cwd) / inputs["path"]
    ...
```
`inputs["path"]` is whatever the model outputs — including anything a prompt-injection payload embedded in a file, web page, or repo the agent is asked to work with could steer it toward. Same absolute-path/`..` escape as SEC-2/SEC-3, but now the "attacker" input channel is model output rather than a CLI argument, which is a meaningfully larger and less controllable attack surface. `Write` additionally auto-creates parent directories (`mkdir(parents=True, exist_ok=True)`), so it isn't even limited to overwriting files that already exist.

`zc_code.py:823-842` (Bash):
```python
elif name == "Bash":
    cmd = inputs["command"]
    if os.environ.get("AI_CODER_SANDBOX") == "1":
        ...enforce(cmd, cwd, allow_net=allow_net, extra_roots=roots)...
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
```
`shell=True` with a fully model-controlled command string. The only mitigation, `zc_sandbox.py`, is **opt-in** (off unless `--code-agent-sandbox` is passed — correctly wired to the `AI_CODER_SANDBOX` env var, I verified that connection and it's fine) and, by its own docstring, "best-effort... not a substitute for a real OS sandbox... when running fully untrusted code." Concretely, `check_filesystem()` (`zc_sandbox.py:87-114`) only inspects `>`/`>>` redirects and `rm|mv|cp` arguments via regex — it does not catch `tee`, `dd`, `sed -i`, `python -c "..."`, command substitution (`` $(...) ``), or base64-piped payloads, all standard ways to write files or exfiltrate data that a naive string scan won't flag.

### SEC-6: `acceptEdits` permission mode silently approves everything, including Bash

`zc_code.py:112-117` documents five permission modes, including:
```
"acceptEdits":       "Auto-approve file edits; ask for other tool calls"
"bypassPermissions": "Auto-approve ALL tool calls (use with caution)"
```
But the actual dispatch (`zc_code.py:770-789`) only special-cases three modes:
```python
if permission == "planMode": return "[PLAN MODE] ..."
if permission == "dontAsk":  return "[DENIED] ..."
if permission == "askPermission":
    ... # confirmation logic
# no branch for "acceptEdits" or "bypassPermissions" — both fall through here:
result = self._run_tool(name, inputs, session)
```
There is no `elif permission == "acceptEdits"` anywhere in the file. The mode that's supposed to "ask for other tool calls" asks for nothing — it behaves identically to `bypassPermissions`. This isn't a hypothetical: it's the **default, hardcoded mode** for two real features:
- `cmd_code_subagent` (`--code-agent-subagent`, `zc_code.py:1210-1217`) — `tools="safe"` (read-only preset), so the practical impact is unconfirmed filesystem reads.
- Custom slash commands and installed plugin commands (`zc_code.py:1323-1325`, `1337-1339`) — `tools="code"`, which is `["Read","Write","Edit","MultiEdit","Bash","Glob","Grep","LS"]` (`zc_code.py:104`). **Invoking any custom or plugin slash command grants it silent, unconfirmed shell execution**, the moment it's run, with no branch of the code ever asking the user anything.

### SEC-7: The web UI has no authentication, binds to all interfaces, allows wildcard CORS, and lets any caller overwrite the stored API key

`webapp/backend/server.py`:
- Line 17 (docstring, i.e. the documented way to run it): `uvicorn webapp.backend.server:app --host 0.0.0.0 --port 8420` — all interfaces, not just localhost.
- Lines 58-63: `CORSMiddleware(allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])`.
- Zero auth mechanism on any of the 12 endpoints — no API key check, no session, no bearer token.
- `POST /api/config` (lines 206-215) accepts `{"api_key": "..."}` and calls `cfg.set("api_key", update.api_key)`, which (`config.py:19-22`) writes straight to `~/.ai-coder-config.json` — **the same file the CLI itself reads.**

Put together: anyone on the same network — or, per the well-documented "malicious webpage reaches a localhost service" pattern (which wildcard CORS actively opts into allowing, rather than merely failing to block), anyone whose page the user's browser merely loads while the server happens to be running — can silently replace the user's real ZaiCoder API key with an attacker-controlled one via a single unauthenticated `POST`. Every subsequent chat, in the web UI *and the CLI*, then routes through the attacker's account, giving them a live feed of the user's prompts. The 30-req/min rate limiter (line 124-135) is explicitly scoped by its own comment to "a runaway client loop, not... a determined attacker," and doesn't apply to this at all since config writes aren't rate-limited the same way chat is (rate limiting is only invoked inside `/api/chat` and `/api/chat/stream`, not `/api/config`).

---

## 6. Findings — High (Functional Bugs)

### BUG-1: The "Sonnet-5-family rejects explicit sampling params" fix wasn't applied everywhere

`utils.py` defines `sampling_kwargs()` specifically because zAICoder Sonnet 5 / Fable 5 / Mythos 5 return a 400 if `temperature`/`top_p`/`top_k` are set to any non-default value at all (confirmed via the model's documented behavior, and via `zc_cost_optimizer.py`'s own fix comment referencing a prior hardcoded-temperature bug). It is **not used consistently** — three confirmed call sites still hardcode the parameter directly against the real API:

| Site | Code | Reachable via | Effect |
|---|---|---|---|
| `zc_observability.py:126` | `client.messages.create(model=model, max_tokens=512, temperature=0, ...)` | `--obs-errors` | 400s with the default model (`claude-sonnet-5`) |
| `zc_hooks_perms_plan.py:241` | `self.client.messages.create(model=self.model, max_tokens=max_tokens, temperature=0.3, ...)` | `--plan` (`PlanModeAgent`, model passed through from `_model(args)`, default `claude-sonnet-5`) | 400s out of the box |
| `webapp/backend/server.py:313-314` | `if 0.0 <= req.temperature <= 1.0: kwargs["temperature"] = req.temperature` | `POST /api/chat/stream` | `ChatRequest.model` defaults to `"claude-sonnet-5"` (line 79) and `temperature` defaults to `0.3` (line 80), both always in range, so this condition is true on effectively every default-configuration request |

The sibling non-streaming endpoint (`POST /api/chat`) is fine, because it goes through `Coder.generate()`, which correctly calls `sampling_kwargs()` (`coder.py:84`, verified). So in the same file, against the same default model, `/api/chat` works and `/api/chat/stream` — presumably the more-used path, since streaming is the better UX — does not.

### BUG-2: `/compact` prints success and does nothing

`zc_code.py:1254-1257`:
```python
if cmd == "compact":
    print("\033[94mℹ Compacting message history (summarising)…\033[0m")
    # Stub: in real SDK this compacts via PreCompact hook
    return
```
No call to `build_context_management()`, `resume_after_compaction()`, or any summarization. The underlying capability is real: `build_context_management()` (`zc_tools.py:265`) *is* correctly wired into the agent's automatic outgoing-request context management (`zc_code.py:1178-1179`, opt-in, works in the background on every turn). But the explicit command a user types to force compaction right now does nothing beyond print a message shaped like success. A user relying on `/compact` because their context is getting large gets no actual relief and no error telling them so.

### BUG-3: Checkpoint/rewind is a one-way, contentless feature

Two separate gaps stack here:

1. `CodeSession.checkpoint()` (`zc_code.py:241-249`) records only `{id, label, ts, turn}` — a bookmark to a turn number, not any file content, diff, or git state — despite the module's own docstring listing "File checkpointing (rewindFiles)" as a capability (`zc_code.py:14`) and the method's own docstring calling it "a file-level checkpoint (rewind point)." There is nothing here that a rewind could actually restore.
2. Separately, `zc_sessions.py:141` defines `rewind_to_checkpoint(s, cpid)` — the function that would perform a rewind — and it is **never called anywhere in the repository.** No CLI flag, slash command, or code path reaches it. `--code-agent-checkpoint` creates checkpoints (via a different, in-memory-only `CodeSession.checkpoint()` method than the one `zc_sessions.py` implements); nothing can ever use them.

### BUG-4: `pyproject.toml` declares no dependencies

```toml
[project]
name = "wire"
version = "1.33.0"
...
# no `dependencies = [...]` key anywhere in the file
```
This is a real `[build-system]` + `[project]` table (setuptools-backed), i.e. `pip install .` is meant to work. It currently installs a package with **none** of `zc`, `fastapi`, `pydantic`, `uvicorn`, `pandas`, `openpyxl`, `python-pptx`, `PyYAML`, or `python-dotenv` — all genuinely imported by the codebase per `requirements.txt` and direct grep of `import` statements. The only place dependencies are actually declared is `requirements.txt`, which `pip install .` does not consult. This is precisely the "clean dependency installation" step the uploaded validation checklist calls for as step 1 of final repo-wide validation, and it would fail immediately.

---

## 7. Findings — Medium/Low (Quality & Hygiene)

- **QUAL-1 — Two disagreeing file-size ceilings.** `security.py`'s unused `MAX_FILE_SIZE_BYTES` defaults to 25MB; `zc_files.py` defines and *actually enforces* (`zc_files.py:100`) its own separate `MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024` (500MB) — a 20x difference between the "canonical" limit and the real one.
- **QUAL-2 — Dead formatting helpers.** `utils.py`'s `print_header`/`print_success`/`print_error`/`print_info`/`print_warn` are never imported anywhere else; every module hand-rolls its own ANSI codes instead, producing inconsistent CLI output styling across features.
- **QUAL-3 — Cross-cutting docs have drifted from the code by several versions.** `ROADMAP.md`'s own header still reads "v1.32.0" against an actual v1.33.0 codebase, and its "Part 1 — Current Coverage" table claims "46 modules, ~11,700 lines" against an actual 65 root modules / ~21,000 lines (root only, before tests/webapp). `CHECKLIST.md`'s title still reads "v1.16.0." These are the documents the task's own instructions name as "source of truth" — they can't be trusted at face value for the last several versions without cross-checking the code, which is what this report did instead.
- **QUAL-4 — Stray duplicate directory shipped in the v1.32.0 release zip.** `v1_32_0.zip` unpacks to `wire/wire/` (129 files, a stale partial snapshot missing docs 39-44) sitting alongside `wire/wire_release/` (149 files, the real one) — leftover from whatever process produced that release artifact.
- **QUAL-5 — Webapp rate limiter keys on the immediate peer IP** (`webapp/backend/server.py:129`, `request.client.host`), with no `X-Forwarded-For` handling. Behind a reverse proxy (plausible, given the file's own Docker/orchestrator framing), every real client would collapse into one shared bucket.
- **QUAL-6 — Secret redaction coverage is uneven across credential types.** `logging_config.py:31-35` catches Anthropic keys by shape (`sk-ant-...`) regardless of context, but GitHub tokens, Voyage keys, and WIF/OAuth tokens are only redacted if the literal env-var name string happens to appear next to the value in the log line — a much weaker guarantee for every credential type except Anthropic's own.
- **QUAL-7 — Inconsistent line endings.** Seven files (`zc_embeddings.py`, `zc_advisor.py`, `zc_compliance_api.py`, `zc_observability.py`, `zc_hooks_perms_plan.py`, `tests/test_zc_compliance_api.py`, `tests/test_zc_fable5.py`) use CRLF while the rest of the repository uses LF.
- **QUAL-8 — Test-count bookkeeping has repeatedly drifted across versions**, by the project's own admission (`IMPLEMENTATION_CHECKLIST.md` documents v1.31.0's stated 336 vs. a freshly-recounted 387 for the same commit). I could not execute the suite to independently verify v1.33.0's claimed 416 (no network access to install `pytest`/`anthropic` in this sandbox); a raw `grep -c "def test_"` finds 358 test functions (347 excluding `test_webapp_server.py`), and the gap is structurally explainable by `@pytest.mark.parametrize` usage (one function alone, `test_every_cmd_function_is_referenced_in_main`, expands to 49 cases), but I can't confirm the exact figure.
- **Naming debt, tracked correctly:** `zc_eval.py` and `zc_evals.py` coexist; the latter is a pre-v1.10 predecessor explicitly superseded by the former. This is handled well, not badly — it's a documented, intentional entry in `tests/test_cli_wiring.py`'s `KNOWN_EXCEPTIONS`, which itself has a self-check (`test_known_exceptions_are_still_valid`, `test_cli_wiring.py:68-76`) that fails if the dead function is ever actually removed, so the exception can't silently go stale. Worth cleaning up eventually, not worth losing sleep over.

---

## 8. What's Actually Solid

To keep this report honest in both directions:

- **CLI wiring is genuinely good.** I independently re-derived the project's own `test_cli_wiring.py` check via AST rather than trusting its self-report: parsing every `add_argument()` call and every `cmd_*` function definition and cross-referencing against `main.py`'s dispatch code by hand. Result: **all 426 argparse destinations are read somewhere in `main.py`** (zero orphaned flags), and **all but one of the `cmd_*` functions across 49 feature modules are reachable** — the one exception (`zc_evals.cmd_eval`) is the documented, tracked case described above.
- **`resilience.py`** (jittered exponential backoff, a proper three-state circuit breaker, retry-eligibility driven by a typed exception hierarchy rather than string matching) and **`exceptions.py`** (a clean, documented error taxonomy with stable `error_code`s and an explicit `RETRYABLE` flag) are well-designed and internally consistent — no bugs found in either.
- **`coder.py`'s core `generate()` path** correctly gates sampling parameters, correctly parses multi-block API responses, and correctly routes errors through the resilience layer. It's the one thing in this codebase that everything else *should* be routing through, and where it is (the non-streaming webapp chat, the interactive CLI chat, the browse agent), things work.
- **This release's actual new feature — native Word/PDF chat (`zc_word.py`, `zc_pdf.py`)** — is clean. It's honestly scoped in its own docstring ("no local python-docx dependency needed for this path... Skills-only"), and it's wired end-to-end: `--docx-native`/`--pdf-native` → `cmd_docx_chat`/`cmd_pdf_chat` → argparse → dispatch, all confirmed. This is a good template for what "vertical slice, actually complete" looks like in this codebase.
- **`cmd_admin_create_key()`** (`zc_admin_api.py:485-498`) is a good example of the right way to leave something unimplemented: rather than silently no-op-ing (like BUG-2) or faking a response, it explains exactly why Anthropic's real Admin API doesn't expose key creation and points to the supported alternative.
- **The opt-in Bash sandbox is correctly wired end-to-end** — `--code-agent-sandbox` sets `AI_CODER_SANDBOX=1`, which `zc_code.py:826` checks before running any Bash command — and its own docstring is honest about its limits rather than overselling them as real isolation.

---

## 9. v1.32.0 → v1.33.0: What This Release Actually Shipped

File-level diff of the two supplied archives (after discounting the stray duplicate directory in the v1.32.0 zip — see QUAL-4 — and using the real `wire_release/` copy as the baseline):

```
New:      zc_word.py, zc_pdf.py, tests/test_zc_word_pdf.py,
          docs/45_upgrade_v1.33.0_docx_pdf_native.md
Modified: zc_skills_api.py, main.py, pyproject.toml (version bump only),
          tests/test_cli_wiring.py, CHANGELOG.md, README.md, ROADMAP.md, CHECKLIST.md,
          IMPLEMENTATION_CHECKLIST.md
```
So the release's real scope was: native Word/PDF document chat via the Skills API, plus the CLI wiring and tests to support it. As covered in §8, that specific slice was implemented cleanly. The pre-existing issues in this report (SEC-1 through BUG-4) all predate v1.33.0 and were not introduced or fixed by it — they were simply not in scope for this release, which is fair, but they also weren't caught by whatever review process produced `docs/45_upgrade_v1.33.0_docx_pdf_native.md`, which is scoped only to the feature it's naming.

---

## 10. Prioritized Recommendations

**Fix before anyone relies on this for real work:**
1. Add a path-confinement check (reuse `security.safe_resolve()` — it already exists and is tested) to `projects.py:delete_project`, `artifacts.py:delete`, and `artifacts.py:export`. (SEC-2, SEC-3, SEC-4)
2. Confine `zc_code.py`'s Read/Write/Edit tools to `session.cwd` (or an explicit allowlist of roots) by default, not just under the opt-in sandbox. (SEC-5)
3. Add the missing `elif permission == "acceptEdits"` branch so it actually distinguishes edit tools from everything else, per its own documented behavior. (SEC-6)
4. Either add authentication to `webapp/backend/server.py` or change its documented default run command to bind `127.0.0.1` and drop the wildcard CORS origin. At minimum, `/api/config` should not accept writes without some form of local-only confirmation. (SEC-7)
5. wire `sampling_kwargs()` into the three remaining raw call sites. (BUG-1)
6. Add `dependencies = [...]` to `pyproject.toml` matching `requirements.txt`, or drop the `[build-system]` table if `pip install .` was never meant to work. (BUG-4)

**Fix soon:**
7. Either implement `/compact` for real or change its output so it doesn't claim success. (BUG-2)
8. Either wire `rewind_to_checkpoint()` to a real command, or stop advertising "rewindFiles" until checkpoints capture something restorable. (BUG-3)
9. Reconcile the two `MAX_FILE_SIZE_BYTES` values. (QUAL-1)

**Housekeeping:**
10. Refresh `ROADMAP.md`/`CHECKLIST.md` headers and coverage numbers, or stop treating them as living documents. (QUAL-3)
11. Remove the stray `wire/wire/` duplicate from the release pipeline. (QUAL-4)
12. Normalize line endings; delete `zc_evals.py` once its `KNOWN_EXCEPTIONS` entry is intentionally retired.

---

## 11. Audit Coverage & Limitations

- **No execution.** No network access meant no `pip install`, so nothing here was verified by actually running it — every finding is a static-analysis/manual-trace claim with an exact file:line citation, not a reproduced crash. I'd treat the confidence as high (the logic is directly readable and the control flow is unambiguous) but not "watched it fail in a debugger" certain.
- **Depth was uneven by design.** `zc_code.py`, `projects.py`, `artifacts.py`, `security.py`, `resilience.py`, `exceptions.py`, `coder.py`, `webapp/backend/server.py`, and the two new v1.33.0 modules got full line-by-line review. Modules like `zc_router.py`, `zc_github.py`, `zc_git.py`, `zc_research.py`, and most of the 61-flag Agent SDK group got structural/wiring checks (imports, dispatch, dead-code scan) but not the same depth of manual logic review — there is very likely more to find in that remaining surface area, especially given the pattern established here (issues cluster around anything touching the filesystem or the network).
- **Test quality was spot-checked, not exhaustively read.** `tests/test_security.py` was read in full because it directly bears on SEC-1; the other ~40 test files were confirmed to exist, compile, and (via parametrize accounting) roughly reconcile with the claimed count, but not read function-by-function.
