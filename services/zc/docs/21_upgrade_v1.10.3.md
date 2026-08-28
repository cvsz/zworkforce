# v1.10.3 — Full model catalog, verified pricing, legacy tier

Follow-up to v1.10.2's ID cleanup. That release fixed *which strings*
were used; this release fixes the *data attached to them* — pricing
had drifted from ZaiCoder's actual published rates, and the CLI had
no local record of legacy-but-still-callable models at all.

## What changed

**`zc_models.py`** — added `MODEL_CATALOG`, a dict keyed by model
ID with `display_name`, `tier` (`mythos` / `current` / `legacy`),
`context_window`, `max_output`, `price_in`, `price_out`, `thinking`
mode, `effort_default`, and free-text `notes`. Ten entries: the two
Mythos-class models, the three current-tier models, and five legacy
models that are superseded but still respond to API calls (Opus
4.7/4.6/4.5, Sonnet 4.6/4.5).

- `cmd_list_models()` now renders this catalog grouped by tier when the
  live Models API is unreachable, instead of a flat list with legacy
  Opus rows that had silently collapsed into duplicate-key dead code
  in v1.10.1 and earlier. Legacy models are hidden by default; the new
  `--list-models-legacy` flag includes them.
- `cmd_model_info()` now falls back to the catalog (clearly labeled as
  such) when the live API call fails or the ID isn't recognized, and
  when the live call *does* succeed, it now also prints the response's
  `capabilities` object (vision, adaptive/extended thinking support,
  structured outputs) instead of only ID/name/context/created-date.

**Pricing corrections** (verified against
platform.zc.com/docs/en/about-zc/models/overview,
2026-07-02) in `zc_cost_optimizer.py`, `zc_metrics.py`, and
`zc_tokens.py`:

| Model | Old (wrong) | Corrected |
|---|---|---|
| Opus 4.8 (and legacy Opus 4.5–4.7) | $15 / $75 per MTok | $5 / $25 per MTok |
| Haiku 4.5 | $0.80 / $4 per MTok | $1 / $5 per MTok |
| Sonnet 5 / 4.6 / 4.5 | $3 / $15 per MTok (unchanged, was already correct) | $3 / $15 per MTok |
| Fable 5 / Mythos 5 | $10 / $50 per MTok (unchanged, was already correct) | $10 / $50 per MTok |

The Opus figure was the most consequential: $15/$75 is roughly 3x the
real rate, meaning every prior `--cost-summary`, `--optimized`, and
`--count-tokens` cost estimate involving Opus was overstating spend by
~3x. Anyone who used those estimates for budgeting should treat
pre-v1.10.3 Opus numbers as unreliable.

Also added: `zc_cost_optimizer.py` now models Sonnet 5's
introductory pricing ($2/$10 per MTok, through 2026-08-31) as a
separate `SONNET5_INTRO_PRICE` constant and an `estimate_cost(...,
use_intro_pricing: bool = False)` parameter, rather than picking one
of the two real rates and silently using it for the whole window.
Default stays off (uses the standing $3/$15 rate) so existing callers
that don't pass the new argument get the same behavior as before this
change, just with the corrected base number.

## What was NOT changed

- `zc_fable5.py`'s `FABLE_MYTHOS_INFO` pricing ($10/$50) — this was
  already correct, cross-checked again this round.
- The suspension/restoration note added in v1.10.2 — still accurate,
  untouched.
- No new CLI commands beyond `--list-models-legacy`; this was a data
  and enrichment pass, not a feature pass.

## Verification

- `python3 -m py_compile *.py` — all modules compile after the edits.
- Grepped for the old `15.0`/`75.0` Opus pair and the old `0.8`/`4.0`
  Haiku pair across every `.py` file; zero remaining matches.
- Manually cross-checked every number in the new `MODEL_CATALOG`
  against the live models-overview and migration-guide docs pages
  fetched during this session, rather than trusting the prior
  in-repo values as a starting point.
