# v1.31.0 — CLI-to-API wiring audit: four fully-built modules with zero CLI access

Different kind of cycle than usual. Every prior cycle in this series
(`docs/35` through `docs/42`) re-checked wire's *API-level* behavior
against `platform.zc.com/docs` — did we send the right request shape,
handle the right response fields, use the current beta header. This one
checked something else: for every `zc_*.py` module, is every
`cmd_*` function it defines actually reachable from `main.py`? A module
can be a perfectly correct, fully-tested implementation of some zAICoder
capability and still be dead weight to the person typing `python main.py
--help` if nothing in `main.py` ever imports it.

## Method

```
for each zc_*.py file:
  parse it and collect every top-level `def cmd_*` function name
  for each name: grep for it (word-boundary) in main.py
  anything with zero hits is a candidate gap
```

Word-boundary matching mattered: a first pass without `\b` produced a
false negative for `zc_prompt_optimizer.cmd_optimize`, because
`main.py` contains the *unrelated* `cmd_optimized` (from
`zc_cost_optimizer.py`, a different module, different feature) and
`"cmd_optimized"` contains `"cmd_optimize"` as a substring. Re-ran with
`\bcmd_optimize\b` and it correctly showed up as missing.

## Findings

**Four modules, thirteen functions, wired for the first time:**

| Module | Functions | CLI flags added |
|---|---|---|
| `zc_github.py` | `cmd_gh_review_pr`, `cmd_gh_triage`, `cmd_gh_commits`, `cmd_gh_pr_description` | `--gh-review-pr`, `--gh-triage-issues`, `--gh-summarise-commits`, `--gh-pr-description`, `--gh-token`, `--gh-max-items` |
| `zc_router.py` | `cmd_route`, `cmd_route_list` | `--route`, `--route-explain`, `--route-parallel`, `--route-list` |
| `zc_prompt_optimizer.py` | `cmd_optimize`, `cmd_score`, `cmd_ab_test`, `cmd_prompt_lib_list` (+ `lib_add`/`lib_get` used directly, no `cmd_` wrapper existed for those two) | `--optimize`, `--score-prompt`, `--ab-test`, `--ab-prompt-b`, `--ab-task`, `--prompt-lib-add`, `--prompt-lib-list`, `--prompt-lib-get` |
| `zc_metrics.py` | `cmd_metrics_show`, `cmd_metrics_clear`, `cmd_metrics_export` | `--metrics-show`, `--metrics-today`, `--metrics-model`, `--metrics-clear`, `--metrics-export` |

All four modules turned out to already document their own intended CLI
flags in a `CLI flags:` docstring block at the top of the file — this
wasn't guesswork about naming, it was implementing what each module's
own comments already specified was supposed to exist. All four
docstrings say `AI Model Coder CLI v1.9.1`, meaning these modules were
written that early and never wired in the ~20 releases since.

`zc_metrics.py` is a special case worth flagging: it's not inert.
`zc_stream.py` already calls `record()` on every streamed
completion, so the JSONL log at `~/.ai-coder/metrics.jsonl` has been
quietly accumulating real usage data release after release — there was
just no CLI command to read, filter, export, or clear it. This is the
closest thing this audit series has found to a "feature was silently
half-shipped" bug rather than a "feature was never started" gap.

**One naming collision caught before it caused a bug:** the
`zc_prompt_optimizer.py` docstring documents `--ab-test ... With
--prompt and --v2`, but `--v2` is already a `type=int` flag elsewhere in
`main.py` (artifact version numbers). Reusing it for the second A/B
prompt variant would have silently broken argparse type coercion the
first time someone passed a non-numeric string. Used `--ab-prompt-b`
instead — the collision was checked for explicitly before wiring
anything, not discovered after.

## One thing found and *not* wired: `zc_evals.py`

`zc_evals.py` (plural) defines `cmd_eval`, also undocumented in
`main.py`, also carrying a `CLI flags:` docstring describing `--eval`,
`--eval-create`, etc. But `zc_eval.py` (singular) already covers the
same ground — run a suite, compare two models, scaffold a template — with
more features (`--eval-threshold`, `--eval-output`) and *is* wired
(`--eval-run`, `--eval-list`, `--eval-scaffold`, `--eval-compare`).
Wiring `zc_evals.cmd_eval` too would mean two different `--eval`-
family flag sets doing overlapping jobs, which is worse than leaving one
unwired. Treated this as a **dead-code finding, not a wiring gap** —
recorded in `tests/test_cli_wiring.py`'s `KNOWN_EXCEPTIONS` with the
reasoning inline, so the new regression test (see below) doesn't flag it
every run, but also doesn't let it get "fixed" into a two-flag-set mess
by someone who didn't know the history. `zc_evals.py` is a
reasonable deletion candidate for a future cycle; not touched here since
removing a whole module was out of scope for "wire it up."

`--route-add-agent`, mentioned in `zc_router.py`'s own docstring,
was also left out: unlike the other flags, there's no `cmd_`-style
function backing it, only `route_and_call()`'s `table: Optional[dict]`
parameter — adding a custom agent means constructing a dict entry, which
doesn't fit today's single-value-flag dispatch pattern without a small
design decision (JSON on the command line? a file? two paired flags?)
this cycle didn't make. Left as a known follow-up rather than guessing.

## New regression test: `tests/test_cli_wiring.py`

The bug this cycle fixed is exactly the kind of thing that reappears
quietly — a module gets written, tested at the function level, and
nobody adds the argparse flag before moving to the next thing. Added a
parametrized test that walks every `zc_*.py` file, collects its
`cmd_*` functions via `ast.parse` (not a fragile regex — actually parses
the module), and asserts each one is referenced in `main.py`. New
modules with a genuinely unwired `cmd_*` function will now fail CI
immediately instead of silently sitting there for twenty releases. The
`zc_evals.cmd_eval` exception is recorded with its reasoning inline,
plus a second test that fails if the exception entry itself goes stale
(function renamed, file deleted). Also added targeted parse- and
dispatch-level tests for the four newly-wired modules (flag parsing,
positional-argument order into each `cmd_*` call, and the two
validation error paths — `--ab-test` without both variants,
`--prompt-lib-add` without `--prompt`).

62 new tests in `tests/test_cli_wiring.py`. Full suite after this cycle:
**336 tests, regression-clean** (`tests/test_webapp_server.py` requires
`fastapi`, not in this environment's installed set — a local dependency
gap, not a code issue; excluded from the count, same as any environment
without that optional extra).
