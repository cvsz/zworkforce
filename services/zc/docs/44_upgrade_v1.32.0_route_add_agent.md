# v1.32.0 — Multi-Agent Router: `--route-add-agent`, the one flag last cycle didn't wire

v1.31.0's CLI-to-API wiring audit (`docs/43_upgrade_v1.31.0_cli_wiring_audit.md`)
wired four modules and thirteen functions, and explicitly left two things
alone. One (`zc_evals.py`'s `cmd_eval`) was a dead-code call, correctly
out of scope. The other, `zc_router.py`'s `--route-add-agent`, wasn't
dead code or a naming problem — it was a real gap that cycle didn't have an
answer for yet: `route_and_call()`, `cmd_route()`, and `cmd_route_list()`
have all accepted an `extra_table: Optional[dict] = None` parameter since
day one, but nothing on the command line could ever populate it. This cycle
closes that.

## The design decision

The docstring's placeholder (`--route-add-agent NAME  Register a custom
agent description in the routing table`) only ever showed one value, `NAME`,
for something that's actually a two-part `{name: description}` entry. Three
shapes were on the table:

- **JSON on the command line** — `--route-add-agent '{"dba": "Query plans
  and indexing"}'` — flexible, but out of step with everything else in this
  parser (nothing else in `main.py` asks for inline JSON; quoting it
  correctly on Windows vs. a POSIX shell is its own support burden).
- **A file** — `--route-add-agent-file agents.json` — reasonable for a large
  table, but a custom agent is usually one or two entries added on the fly,
  and a whole file for that is heavier than the feature needs.
- **Two paired values on the flag itself** — `--route-add-agent NAME
  DESCRIPTION` — matches the shape of the data directly, no quoting
  gymnastics, and has direct precedent elsewhere in this same parser:
  `--git-pr BASE HEAD`, `--eval-compare MODEL_A MODEL_B`, `--hooks-add EVENT
  COMMAND` are all `nargs=2` already.

Went with the third. The one piece that shape doesn't cover on its own —
registering *more than one* custom agent in a single invocation — is handled
by stacking it with `action="append"`, the same pattern `--browse-allow-domain`
already uses for "let the user repeat this flag":

```
python main.py --route "optimise this slow query" \
  --route-add-agent dba "Query plans, indexing, and slow-query diagnosis" \
  --route-add-agent frontend "React, CSS, and accessibility"
```

## What changed

- **`zc_router.py`**: new `extra_table_from_pairs(pairs)` helper — turns
  the `[[NAME, DESCRIPTION], ...]` list argparse hands back into the
  `{NAME: DESCRIPTION}` dict `cmd_route()`/`cmd_route_list()` already know
  how to merge. Returns `None` (not `{}`) for a falsy input, so every call
  site can write `extra_table=extra_table_from_pairs(args.route_add_agent)`
  unconditionally instead of an `if args.route_add_agent else None` at each
  one. Duplicate `NAME`s: last one wins — plain dict semantics, same as the
  existing `table.update(extra_table)` merge.
- **`main.py`**: `--route-add-agent NAME DESCRIPTION` added to the
  Multi-Agent Router argument group (`nargs=2`, `action="append"`), wired
  into both router dispatch branches (`--route` and `--route-list`) via the
  new helper.
- **`zc_router.py`**'s module docstring updated to describe the real
  flag shape instead of the old one-value placeholder, with a short note on
  why — mirrors how other modules in this codebase document their own CLI
  surface.

Like the rest of this router, none of this touches the network —
`--route-list` with a custom agent renders the merged table with no API
call involved; only `--route` (actually routing a prompt) does.

## Scope note: per-invocation, not persisted

A custom agent registered with `--route-add-agent` lives only as long as the
process does — it's merged into the routing table for that one
`--route`/`--route-list` call and then it's gone. That's not an oversight;
it's the same lifetime `extra_table` has always had in `route_and_call()`,
and it's consistent with what the v1.31.0 docstring was actually promising
(a table parameter, not a config file). Persisting custom agents across
invocations — the way `--hooks-add` writes to a hooks config file, or the
prompt library persists to disk — would be a new feature, not a wiring fix,
and wasn't part of what this cycle set out to close. Worth a future
`ROADMAP.md` entry if there's demand for it; not invented here.

## Also fixed in passing

Two small drifts, both directly in the file this cycle was already
touching:

- `main.py`'s module-level docstring still described the *v1.30.0*
  thinking-mode fix even though `VERSION` had already moved to `"1.31.0"`
  last cycle — a one-release lag, same class of thing `pyproject.toml` had
  going into v1.29.0 (see `docs/27_upgrade_v1.13.0.md` /
  `docs/41_upgrade_v1.29.0.md`). Rewritten to describe this cycle instead.
- `pyproject.toml`'s `version` was still `"1.30.0"` — one release behind
  `main.py`'s `VERSION`, same drift, same fix: bumped both together.

## Tests

Nine new tests in `tests/test_cli_wiring.py`: flag parsing (single pair,
repeated pairs, default-is-`None` when the flag isn't used),
`extra_table_from_pairs()` as a standalone unit (dict-building, `None`/`[]`
→ `None`, last-write-wins on a duplicate `NAME`), and dispatch-level checks
that `--route-add-agent` actually reaches `cmd_route()` and
`cmd_route_list()`'s `extra_table` parameter — including the negative case,
that omitting the flag still passes `extra_table=None` rather than silently
dropping the keyword.

`tests/test_cli_wiring.py`: 62 → 71 pytest-collected cases (62 already
included 47 of those from the single parametrized
`test_every_cmd_function_is_referenced_in_main`; the other 15 → 24 are the
module's regular tests).

While updating this count, noticed the running "full suite" total has
drifted: v1.31.0's entry in `CHANGELOG.md` states 336 tests excluding
`test_webapp_server.py`, but a fresh count against every file actually in
this tree — properly expanding every `@pytest.mark.parametrize` the same
way `test_cli_wiring.py`'s own 62 was counted, rather than counting each
decorated function once — comes to 387 immediately before this cycle's
changes. Likely explanation: parametrized cases in
`test_zc_agents_sdk.py`, `test_zc_compliance_api.py`,
`test_zc_wif.py`, `test_security.py`, `test_tui_streaming.py`, and
`test_utils.py` weren't consistently expanded when past totals were
tallied by hand. Not chasing that down further here — a suite-wide
recount is its own cycle, not a router flag's — but the number below is a
fresh, verified count, not a running increment on the old one.

Full suite after this cycle: **396 tests, regression-clean** (excluding
`test_webapp_server.py`, which needs `fastapi`, not installed in every
environment; 407 including it).
