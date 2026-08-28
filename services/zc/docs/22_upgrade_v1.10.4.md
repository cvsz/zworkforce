# v1.10.4 — Retired-model registry, deprecation scanner, effort-level info

Follow-up to v1.10.3's pricing/catalog pass. That release made the
*current and still-callable-legacy* data accurate; this release adds the
piece that was still missing — a maintained record of model IDs that no
longer work at all, plus tooling to find them in a codebase before they
cause a production failure.

## What changed

**`zc_models.py`** — added `RETIRED_MODELS`, a dict distinct from
`MODEL_CATALOG`'s `legacy` tier:

- `MODEL_CATALOG["...']["tier"] == "legacy"` means superseded but still
  callable (Opus 4.5/4.6/4.7, Sonnet 4.5/4.6) — these keep working.
- `RETIRED_MODELS` means the ID now errors: the original zAICoder 4.0
  releases (`claude-opus-4-20250514`, `claude-sonnet-4-20250514`, and
  their dateless `-4-0` aliases — retired 2026-06-15) and zAICoder Haiku 3
  (`claude-haiku-3-20240307` — retired 2026-02-19), each with a
  recommended replacement ID.

Conflating these two categories in one "legacy" bucket was the actual gap
from v1.10.3 — that release's catalog was accurate for what it covered,
but had no representation at all for IDs that stopped working entirely,
so `--model-info` on one of those just surfaced whatever raw error the
API happened to return.

- `cmd_model_info()` now checks `RETIRED_MODELS` before the live API
  call and, on a match, prints the retirement date and replacement ID
  up front — then still attempts the live call and local-catalog
  fallback afterward in case the local record itself is stale.
- New `cmd_check_deprecated(path)` / `--check-deprecated PATH` greps a
  single file or walks a directory for any `RETIRED_MODELS` key and
  reports every hit with `file:line` and the suggested replacement.
  Text-based matching, not an AST — deliberately, since the point is to
  catch these strings wherever they appear (API calls, env files, CI
  YAML, database seed data), matching ZaiCoder's own migration guidance
  to check the whole codebase rather than just the primary call site.
- `cmd_model_info()`'s live-API branch now also prints the response's
  `capabilities.effort` block (supported levels + default) when present,
  next to the vision/thinking/structured-outputs fields it already
  printed. This was the other open item from v1.10.3's deep-dive review:
  Opus 4.8 and Sonnet 5 both default `effort` to `high`, and that default
  was previously invisible unless you already knew to look for it.

**`main.py`** — new `--check-deprecated PATH` flag, registered in the
"no API key required" dispatch block since it's a local file scan with
no network call.

## What was NOT changed

- `MODEL_CATALOG` pricing/context/tier data — re-verified during this
  pass, no drift found since v1.10.3.
- The Fable 5 / Mythos 5 suspension-and-restoration note — still
  accurate, untouched.
- `RETIRED_MODELS` is a snapshot, same caveat as `MODEL_CATALOG`: it's a
  convenience cache, not a live lookup. A model that retires after this
  file was last edited won't show up until the entry is added.

## Verification

- `python3 -m py_compile *.py` — all modules compile after the edits.
- `--check-deprecated` smoke-tested against a scratch file containing
  `zc-sonnet-4-20250514`, `zc-opus-4-0`, and a current ID —
  correctly flagged the two retired strings with file:line and replacement,
  and did not flag the current one.
- `--model-info zc-sonnet-4-20250514` smoke-tested — prints the
  retirement notice with the correct replacement ID before falling
  through to the (expected-to-fail) live lookup.
