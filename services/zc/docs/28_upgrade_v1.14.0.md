# v1.14.0 — Chat & Excel

No existing CLI flags were removed or renamed. Two additions to the
argument surface: `-i`/`--interactive` goes from a dead flag to a real
feature, and `--excel`/`--excel-output`/`--excel-sheet` are new.

## New modules

- **`zc_interactive.py`** — `cmd_interactive()`: a persistent,
  multi-turn chat REPL against `Coder.generate()`. `-i`/`--interactive`
  has been an argparse flag since v1.7.0 (`main.py:72`) but was never read
  anywhere — passing it fell through every branch in `main()` to
  `parser.print_help()`. This module is the first actual implementation.
  Plain chat only: no tool execution, no filesystem access — that's what
  `--code-agent` is for. Slash commands: `/help`, `/reset`, `/system
  [TEXT]`, `/model [NAME]`, `/save FILE`, `/history`, `/exit`/`/quit`.

- **`zc_excel.py`** — `ExcelSession` + `cmd_excel_chat()`: a
  conversational spreadsheet assistant. Each turn, the user's request and
  a summary of the current sheets (shape, columns, dtypes, a head()
  preview) go to the model with a system prompt asking it to respond with
  either (a) a fenced Python code block that mutates a `sheets` dict of
  DataFrames in place and/or calls a supplied `add_chart(sheet,
  chart_type, title, categories_col, value_cols)` helper, or (b) plain
  text for pure questions that don't change the data. Code blocks are
  extracted, checked against a denylist (`import os`, `subprocess`,
  `open(`, `eval(`, etc. — see the module docstring for why this is
  best-effort rather than a real sandbox), executed against the live
  DataFrames, and the workbook is rewritten to disk after every applied
  turn via `pandas.ExcelWriter` + a follow-up `openpyxl` pass that adds
  any queued charts. Session commands: `/help`, `/sheets`, `/show SHEET
  [N]`, `/undo` (keeps the last 20 snapshots), `/exit`/`/quit`.

  Requires `pandas` + `openpyxl` (new entries in `requirements.txt`,
  clearly marked optional — nothing else in the CLI needs them).
  `cmd_excel_chat()` checks for `pandas` up front and exits with an
  install hint rather than an ugly `ImportError` traceback if it's
  missing.

## Changed

- **`main.py`**:
  - `-i`/`--interactive` now dispatches to `zc_interactive.cmd_interactive()`
    instead of falling through to help text. New `--interactive-system
    TEXT` sets the starting system prompt.
  - New `--excel [FILE]` (nargs, so bare `--excel` starts an empty
    workbook and `--excel data.csv` loads one), `--excel-output FILE`,
    and `--excel-sheet NAME` (pick a sheet out of a multi-sheet input
    workbook) dispatch to `zc_excel.cmd_excel_chat()`.
  - Both new branches sit right after `key = _api_key(args)` /
    `model = _model(args)` — same "API key required" section every other
    generate-backed flag lives in — and both `return` immediately after,
    same pattern as every other dispatch branch in `main()`.
- **`skills.py`**: added a `spreadsheet_analysis` entry so `--list-skills`
  and `--skill spreadsheet_analysis` (as a system-prompt fragment on the
  plain `-p`/`-f` path) reflect the new capability too, independent of
  `--excel` itself.
- **`requirements.txt`**: added `pandas>=2.0.0` and `openpyxl>=3.1.0`,
  both commented as optional and scoped to `--excel` only.

## Why a denylist instead of real sandboxing for `--excel`

`security.py`'s own module docstring is explicit that local code-execution
sandboxing is out of scope for that module and left to whichever feature
needs it — `--code-agent-sandbox` handles it for Bash-tool calls by
isolating filesystem/network access. `--excel` executes short,
narrowly-scoped pandas snippets against in-memory DataFrames (no file or
network access needed for any legitimate spreadsheet operation), so a
denylist on `exec()`'s available builtins plus a string-level check for
`import os`/`subprocess`/`open(`/`eval(`/etc. is a proportionate bar for
this feature rather than standing up a second sandbox. This is
best-effort against a model mistake, not a hardened boundary against a
malicious actor — treat `--excel` with the same trust level as
`--code-agent` without `--code-agent-sandbox`.

## What's still open

- `/undo` in `--excel` only reverts in-memory state for the *next* save —
  it immediately re-saves the reverted state, so the on-disk workbook and
  in-memory `sheets` never drift, but there's no redo.
- No multi-sheet chart placement heuristics beyond "next to the data" —
  `_write_charts()` anchors every chart two columns right of the last data
  column, which can overlap if several charts target sheets with very
  different widths.
- `zc_interactive.py`'s `/save` transcript format is plain Markdown
  headers, not a session format any other command in this CLI reads back
  (contrast `--code-agent-session`/`--sessions-list`, which use the real
  session store in `zc_sessions.py`). Wiring plain chat sessions into
  that same store is a reasonable follow-up if `-i` sessions need to be
  resumable later.
