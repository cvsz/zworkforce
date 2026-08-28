# v1.30.0 — Extended thinking gap-audit: adaptive thinking + effort routing was broken on every current-gen model

## How this cycle started

A prior message in this conversation contained a detailed first-person
narrative claiming a v1.30.0 audit doc, `zc_thinking.py` rewrite, and
`zc_structured.py` fix had already been written, tested, and
packaged. None of that was true — no such work exists anywhere in this
conversation's actual history. Before doing anything else, the re-
uploaded zip was diffed against the real prior state to confirm nothing
had changed, then this cycle was run for real, from scratch, using
wire's actual gap-audit methodology: re-check `platform.zc.com/docs`
against what the code does, not against what a prior turn (real or
claimed) said it did.

## The audit

Fetched `platform.zc.com/docs/en/build-with-zc/extended-thinking`
and `.../adaptive-thinking` directly (not summaries) and cross-checked
against `zc_thinking.py` and `zc_models.MODEL_CATALOG`. Finding:

**`thinking.type: "enabled"` + `budget_tokens` — the only mode
`zc_thinking.py` sent — is a hard 400 error on:**
zAICoder Opus 4.8, zAICoder Opus 4.7, zAICoder Sonnet 5, zAICoder Fable 5, zAICoder
Mythos 5, zAICoder Mythos Preview.

**...and deprecated (still works, but will be removed) on:**
zAICoder Opus 4.6, zAICoder Sonnet 4.6.

**...and is the only working mode (adaptive not supported) on:**
zAICoder Opus 4.5, zAICoder Haiku 4.5, and earlier zAICoder 4 models.

Cross-referencing `zc_models.MODEL_CATALOG`, that first list covers
5 of wire's 9 cataloged models — meaning `--thinking` was broken
outright on every current-tier and mythos-tier model in the catalog,
and silently deprecated (would eventually break) on both legacy-tier
4.6 models. Only `zc-opus-4-5`, `zc-haiku-4-5-20251001`, and
`zc-sonnet-4-5` were actually working as intended.

The `adaptive=True` path made this worse, not better: it sent
`{"type": "adaptive", "budget_tokens": N}` — but adaptive thinking
doesn't take `budget_tokens` at all. Depth control for adaptive mode is
a **separate, top-level** `output_config: {"effort": ...}` object, not
a field inside `thinking`. So even the code path meant to opt into the
modern behavior wasn't actually using the effort parameter — `effort`
was only ever consumed to compute a `budget_tokens` number via the
pre-existing `EFFORT_BUDGETS` table, which then got attached to the
wrong config object.

**Secondary finding, same file:** `cmd_thinking()`'s usage summary read
`usage.get('thinking_input_tokens', 0)` — this field doesn't exist in
the documented response shape. The real field, confirmed against the
docs' own example JSON, is `usage.output_tokens_details.thinking_tokens`.
The old code always printed `thinking=0`.

**Third finding, `zc_structured.py`:** structured outputs went GA
on January 29, 2026 (confirmed via `platform.zc.com/docs/en/release-notes/overview`)
— "a simplified integration path with no beta header required." The
code still sent `zc-beta: structured-outputs-2025-11-13`
unconditionally on every request, plus an entirely unused
`BETA = "output-128k-2025-02-19"` class attribute (grep confirmed zero
references anywhere in the codebase). The old header still works during
ZaiCoder's transition period, so this wasn't a hard break like the
thinking issue — just dead weight worth cleaning up now that GA doesn't
need it.

## What was explicitly checked and NOT implemented

One third-party blog post (not `platform.zc.com`) claimed an
"Xhigh" effort level exists between "high" and "max" on Opus 4.7/4.8.
The official `effort` docs page, fetched directly, lists only
`"low" | "medium" | "high" (default) | "max"` — no "xhigh" anywhere.
Since this couldn't be confirmed against the primary source, it was
**not** added to `EFFORT_BUDGETS`, argparse's `--effort` choices, or
anywhere else. If ZaiCoder documents it later, add it then.

## The fix — `zc_thinking.py`

- New `ADAPTIVE_THINKING_MODELS` / `BUDGET_TOKENS_UNSUPPORTED_MODELS`
  sets (keyed off `zc_models.MODEL_CATALOG` ids) plus
  `supports_adaptive_thinking()` / `supports_manual_budget_tokens()`
  helpers, so mode routing lives in one place instead of being
  hardcoded per call site.
- `generate_with_thinking()` / `stream_with_thinking()` gained
  `adaptive: Optional[bool] = None` (was `bool = False`) and
  `legacy_budget: bool = False`. `_resolve_mode()` decides the actual
  mode:
  - `legacy_budget=True` forces manual `budget_tokens`, raising
    `ThinkingModeError` immediately (no API round trip) if the model
    is one where that's a 400.
  - `adaptive` explicit True/False forces that mode, raising
    `ThinkingModeError` if `adaptive=True` targets a model that
    doesn't support it.
  - `adaptive=None` (the new default) auto-selects: adaptive if the
    model supports it, legacy manual otherwise. This is the behavior
    change that actually fixes the bug — previously `adaptive`
    defaulted to `False` everywhere, which always chose the mode that
    fails on 5 of 9 catalog models.
- In adaptive mode, the request now correctly sends
  `thinking: {"type": "adaptive"}` (no `budget_tokens`) and a
  top-level `output_config: {"effort": effort or "high"}` — "high"
  matches the API's own documented default, made explicit rather than
  implicit.
- `cmd_thinking()`'s usage summary now reads
  `usage["output_tokens_details"]["thinking_tokens"]`.

## The fix — `main.py`

- New `--effort-legacy-budget` flag, documented inline with which
  models it will refuse on.
- `--adaptive`'s help text updated to clarify it now *forces* adaptive
  (auto-select already prefers it where supported) rather than being
  the only way to get it.
- Dispatch: `adaptive=(True if args.adaptive else None)` instead of
  always passing `args.adaptive` — this is what lets the auto-select
  default actually take effect for users who pass plain `--thinking`
  with no mode flag.
- `ThinkingModeError` is caught at the dispatch site and printed as a
  clean one-line error + `sys.exit(1)`, verified end-to-end with a real
  argparse + dispatch run (`--thinking --effort-legacy-budget --model
  zc-sonnet-5` → clean exit code 1, no traceback).

## The fix — `zc_structured.py`

- Removed the unconditional `zc-beta: structured-outputs-2025-11-13`
  header from `_call()`.
- Removed the unused `BETA = "output-128k-2025-02-19"` class attribute.
- No behavioral change to `json_object()` / `json_schema()` / `extract()`
  / `analyse_code()` — all already used the GA `output_config.format`
  shape correctly; only the header was stale.

## Tests

- `tests/test_zc_thinking.py` — rewritten. Covers: adaptive
  auto-selected on every adaptive-capable model (regression test for
  the core bug), effort landing in `output_config` not `thinking`,
  legacy auto-selected on manual-only models, `--effort-legacy-budget`
  working on deprecated-but-supported models (Opus 4.6/Sonnet 4.6) and
  refusing cleanly on hard-400 models, explicit `adaptive=True` refusing
  on manual-only models, the same routing applied to the streaming path,
  the full adaptive/manual support matrix per model, and a regression
  test for the `thinking_input_tokens` → `output_tokens_details.thinking_tokens`
  field-name fix.
- `tests/test_zc_structured.py` — new (this module had zero prior
  test coverage). Covers: no beta header sent, no dead `BETA`
  attribute, `output_config.format` still correct for both
  `json_object` and `json_schema` modes, and required-field validation.
- Full suite after this cycle: **274 tests, regression-clean.**

## Also verified, not changed

Grepped the full codebase for other references to the removed `BETA`
attribute or the old always-`False` adaptive default — `tui.py` and
`tui_streaming.py` (added in v1.29.0) don't call into
`zc_thinking.py` or `zc_structured.py` at all, so neither
needed updating for this fix.
