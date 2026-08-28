# Merge notes — ai-coder-cli-v1 + ai-coder-cli-v2 → v1.12.0 "Release"

Input: `ai-coder-cli-merged.zip`, containing two separate project folders:

- **`ai-coder-cli-v1`** — this project. Modular, one `zc_*.py` file per
  API feature, versioned to v1.11.1 with a full dated audit trail in
  `docs/`. ~52 files.
- **`ai-coder-cli-v2`** — a smaller, independently-developed CLI. A single
  `coder.py` core plus `config.py`/`utils.py`/`skills.py`, an `agents.py` /
  `multi_agent_core.py` local orchestration layer, and — uniquely —
  standalone-executable packaging (`build.sh`/`.bat`, `ai-coder.spec`,
  `setup.sh`/`.bat`, `LICENSE`) that v1 never had. Its own `CHANGELOG.md`
  shows it was independently audited against the same July 2026 docs
  (service tiers, refusal/`stop_details`, fast mode, prompt caching) —
  real, correct work, just duplicating ground v1 already covers.

## What got merged in

**Packaging/distribution only**: `build.sh`, `build.bat`, `ai-coder.spec`,
`setup.sh`, `setup.bat`, `LICENSE` (MIT), copied over unmodified except a
copyright year bump. These reference `main.py` generically and don't
depend on which lineage's `main.py` they point at, so they carry over
cleanly. Also added `.env.example` — referenced by both projects'
`setup.sh`/`.bat` but present in neither, a real (small) gap in both.
`requirements.txt` bumped `zc` to `>=0.75.0` per v2's own finding
that newer SDK versions are needed for `service_tier`/`inference_geo`/
`stop_details`/the beta client — v1 already used all of these, just hadn't
stated the version floor explicitly.

## What did NOT get merged, and why

Everything else in v2 duplicates something v1 already has, under the same
names, already wired into v1's much larger `main.py` and its own audit
history:

| v2 file | Overlaps with | Decision |
|---|---|---|
| `coder.py`, `config.py`, `utils.py` | v1's own `coder.py`/`config.py`/`utils.py` (same names, different implementation, actively imported by v1's `main.py`) | Kept v1's. Swapping in v2's would break every call site in v1's `main.py` that depends on v1's `Coder.__init__` signature. |
| `managed_agents.py` (`ManagedAgentsClient`) | `zc_agents_sdk.py`'s own `ManagedAgentsClient`, already wrapping the real `/v1/agents`, `/v1/environments`, `/v1/sessions` API and already wired to `--agent-managed-run` | Kept v1's — it passes `betas=[MANAGED_AGENTS_BETA]` explicitly per-call rather than assuming the SDK sets it, and v1's `zc_agents_sdk.py` has an explicit comment block distinguishing it from the older local `ManagedAgent` class, which v2 never had to disambiguate in the first place. Importing both under the same class name would have been a straight collision. |
| `skills.py` | v1's `skills.py` | Kept v1's; v2's `agents.py`/`multi_agent_core.py` depend on v2's specific `SkillManager`/`SkillType` shape, which isn't a drop-in match for v1's. |
| `agents.py`, `multi_agent_core.py`, `workflow_examples.py` | v1's `zc_agents_sdk.py` (`ManagedAgent`, subagent spawning, `orchestrate()`) and `projects.py`/`personalities.py` | Not merged — this is v2's own local multi-agent orchestration layer, built against v2's `coder.py`/`skills.py`/`config.py` internals. Re-platforming it onto v1's modules would be close to a rewrite for capability v1's `--agent-orchestrate` already covers. |
| `batches.py` | v1's `zc_batch.py` | Kept v1's — more complete per v1's own audit history (`docs/19_upgrade_v1.10.0.md` etc.). |

If anything in the unmerged v2 files turns out to do something genuinely
not covered by the v1 equivalent, that's worth a follow-up pass — but
nothing found in this comparison qualified; every overlap checked was v1
having the same or broader coverage already.

## Net result

v1.12.0 is functionally identical to v1.11.1 (see `docs/*_upgrade_*.md`
for that full history) plus a working standalone-build story it didn't
have before. `ai-coder-cli-v2` as a whole isn't a subset of this release —
it's a smaller, competently-built, independently-audited CLI covering a
narrower feature set — but everything in it that wasn't purely
packaging was already present here in a more complete form.
