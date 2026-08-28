# v1.12.1 — Deep-dive bug pass + Upgrade All (Fable 5 / Opus 4.8)

Prompted by a direct audit request against v1.12.0 "Release": find what's
incomplete, broken, or missing, fix it, and add bulk-upgrade logic for
Fable 5 and Opus. v1.12.0 itself was packaging-only (see CHANGELOG), so
this is the first pass to touch `main.py`/`coder.py`/`zc_models.py`
since v1.11.1.

## Bugs found and fixed

1. **`coder.py`'s `Coder.generate()` — fragile response parsing.**
   `data["content"][0]["text"]` assumed the first content block was always
   plain text. Every thinking-capable model (Sonnet 5, Opus 4.8, and
   especially Fable 5/Mythos 5, which — per `zc_fable5.py` — have
   thinking on by default) can return a `thinking` block first, which has
   no `"text"` key and would silently return an empty string via
   `.get()`, or previously (with plain indexing) risk a `KeyError`
   depending on response shape. Multi-text-block responses also silently
   dropped every block after the first. Fixed to concatenate all
   `type == "text"` blocks, matching the pattern already used correctly in
   `zc_models.py` / `zc_fable5.py` / `zc_mythos5.py`. Also
   added a clearer `[REFUSED]` message instead of returning an empty
   string when `stop_reason == "refusal"` yields no text content.

2. **`-i`/`--interactive`, `--skill`, `--agent` — accepted, never read.**
   All three were valid CLI flags with zero effect: nothing in `main.py`
   ever referenced `args.skill` or `args.agent`, and `-i`/`--interactive`
   had no interactive-mode code path at all. `--skill` and `--agent` are
   now wired into the default single-prompt flow: `--skill` looks up the
   skill in `skills.py`'s `SkillManager` and prepends its description to
   the system prompt (warning on an unknown skill name instead of silently
   ignoring it); `--agent` prepends a role-specific system prompt for one
   of the seven roles `--list-agents` already printed — which, until now,
   existed *only* as print strings in that one place, with no data behind
   `--agent` itself. `--list-agents` now reads from that same new
   `AGENT_SYSTEM_PROMPTS` table instead of a second hardcoded copy of the
   same seven names, so the two can no longer drift apart.
   `-i`/`--interactive` is left as a known no-op for now — an actual REPL
   is a bigger feature than a bug-fix pass; flagging for a future round.

3. **`personalities.py` fully built, never reachable.** `PersonalityManager`
   was already implemented and even wired into `coder.py`'s
   `Coder.__init__(personality_style=...)` — but no CLI flag ever supplied
   `personality_style`, and none of the five `Coder(...)` construction
   sites in `main.py` passed it. Added `--personality {creative,pragmatic,
   precise,socratic,teaching}` and `--list-personalities`, and threaded
   `personality_style=args.personality` into the default prompt flow's
   `Coder(...)` call.

4. **`--cache-stats` — accepted, had zero effect either way.** `--cache`'s
   dispatch in `main.py` hardcoded `show_stats=True` regardless of the
   flag, so passing `--cache-stats` did nothing and *not* passing it also
   did nothing (stats always printed). Now threaded through as
   `show_stats=args.cache_stats`, so the flag actually controls the
   behavior its name and help text describe.

## New: `--upgrade-all` (Fable 5 / Opus 4.8)

`--check-deprecated` (existing, unchanged) only *flags* retired model IDs
and never touches the filesystem — it has no concept of "upgrade
everything to the best available model" and wouldn't touch a perfectly
callable-but-superseded `zc-sonnet-4-6` or a plain
`zc-haiku-4-5-20251001` reference, since neither is retired.

New in `zc_models.py`, wired into `main.py`'s existing Models API
group:

```
--upgrade-all PATH             Rewrite every known zAICoder model ID under PATH
                                to --upgrade-target. Dry-run by default.
--upgrade-target {fable5,opus} fable5 -> zc-fable-5 (default)
                                opus   -> zc-opus-4-8
--upgrade-yes                  Actually write changes (default: preview only)
--upgrade-no-backup            Skip the .bak backup normally written per changed file
```

Implementation notes:

- Source ID set is every key in `RETIRED_MODELS` + every key in
  `MODEL_CATALOG` + a small `MODEL_ID_ALIASES` table (currently just
  `zc-haiku-4-5` -> the dated ID, per `MODEL_CATALOG`'s own alias
  note) — minus the chosen target, so re-running against an
  already-upgraded tree is a correct no-op instead of matching its own
  output.
- Matched longest-first with a manual `(?<![\w-])...(?![\w-])` boundary
  (not `\b`, which treats `-` as a boundary itself and would let a
  substring like `zc-opus-4-5` match inside a longer, unrelated ID) so
  IDs are never partially rewritten.
- Files are read with `errors="strict"`; anything that isn't valid UTF-8
  (binaries, e.g. a PyInstaller `dist/` output) is skipped rather than
  risked with a text-mode write.
- `*.bak` files from a previous run are excluded from the walk, so
  running `--upgrade-all` twice in a row doesn't chase its own backups.
- Dry-run is the default specifically because this writes to disk in
  place (unlike every other `zc_*.py` command, which only calls the
  API) — `--check-deprecated`'s read-only report-then-decide pattern
  is preserved as the default and application requires the explicit
  `--upgrade-yes`.

## What was NOT changed

- No attempt made to implement `-i`/`--interactive` as a real REPL — out
  of scope for a bug-fix pass, noted above for later.
- Did not extend `--skill`/`--agent`/`--personality` to the other
  `Coder(...)` call sites (`--project-plan`, `--project-run`,
  `--artifact-create`, `--artifact-iterate`) — those are driven by
  project/artifact templates with their own prompt construction, and
  folding skill/agent/personality selection into that felt like a
  separate feature decision (which one wins if a project template and
  `--agent` disagree?) rather than a bug fix. Flagging for a future pass
  if wanted.
- The `docs/zc-api-gap-audit-v1.10.5.md` gap list (advisor tool
  real implementation follow-through, task budgets, embeddings module
  usage, etc.) was re-read but not re-audited this pass — this pass's
  scope was "what's broken", not "what's still missing from the API
  surface", which is already tracked separately in that file and in
  CHANGELOG's v1.11.x history.
