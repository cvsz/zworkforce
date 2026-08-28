# v1.33.0 — `--docx-native` / `--pdf-native`: the two pre-built Skills that were never wired

Follow-up to the "dive deep, find something we can implement" pass over
`docs/44_upgrade_v1.32.0_route_add_agent.md`'s territory. That cycle
closed the last *CLI-wiring* gap (`cmd_*` functions with no argparse
flag). This one is a different kind of gap: a fully documented,
already-integrated API capability with a real matching module that
simply never got a second half built.

## What was found

`zc_skills_api.py`'s `PREBUILT_SKILLS` dict has listed all four
Anthropic-maintained Skills since v1.15.0:

```python
PREBUILT_SKILLS = {
    "pptx": {...}, "xlsx": {...}, "docx": {...}, "pdf": {...},
}
```

v1.16.0 built native routing for two of them — `--excel-native` and
`--pptx-native` route `zc_excel.py` / `zc_powerpoint.py`'s chat
loops through the xlsx/pptx Skills instead of the hand-rolled
pandas/openpyxl or python-pptx path. `docx` and `pdf` never got the same
treatment: `--skills-list` has been printing them as available skill_ids
for seventeen releases, and nothing in the CLI could ever invoke either
one. Confirmed with a plain grep across `main.py` for `docx`/`.pdf` — the
only hit was the `--skills-list` help string itself.

This isn't the `test_cli_wiring.py` class of bug (a `cmd_*` function with
no flag) — there was no `zc_word.py` or `zc_pdf.py` to wire in
the first place. The gap was one level up: an API capability the project
already knows how to call (the Skills client, file upload/download, the
container-reuse pattern) that nobody had pointed at these two formats.

## What changed

**Two new modules**, `zc_word.py` and `zc_pdf.py`, each a single
`cmd_docx_chat()` / `cmd_pdf_chat()` function mirroring
`zc_powerpoint.py`'s `_cmd_pptx_chat_native()` one-for-one: upload the
starting file once (if given), run a `messages`/`container_id` chat loop
through `SkillsApiClient.call_with_skills_turn()`, download whatever
`extract_output_file_ids()` finds after each turn. Same error handling,
same `/exit`-only command surface, same reasoning for why there's no
`/undo` or content preview (the Skill owns the document server-side —
this CLI never holds a local copy to inspect or revert).

**Unlike xlsx/pptx, there's no `native=` branch.** `zc_excel.py` and
`zc_powerpoint.py` each have a hand-rolled pandas/openpyxl or
python-pptx path that `native=False` (the default) still uses — Skills
access is opt-in there because the fallback is a real, working
alternative. No such fallback exists for Word documents or PDFs in this
CLI, so `zc_word.py` / `zc_pdf.py` are Skills-only: one function
each, no boolean parameter, always native. The `-native` suffix on the
flag name stays anyway — it's still documentation of *which*
implementation runs (ZaiCoder's maintained Skill vs. a hand-rolled one),
consistent with the other two, even though today it's the only choice.

**`main.py`**: new "Word / PDF Chat (Skills API only)" argument group —
`--docx-native [FILE]`, `--docx-output FILE`, `--pdf-native [FILE]`,
`--pdf-output FILE` — same `nargs="?", const=""` shape as `--excel` /
`--pptx` (bare flag starts a fresh document, a path loads an existing
one), dispatched right after the `--pptx` branch.

**`zc_skills_api.py`**: module docstring corrected. It previously
described routing xlsx/pptx through Skills as "intentionally left as a
separate follow-up," which was already stale before this cycle started —
that follow-up shipped in v1.16.0, the docstring just never caught up.
Rewritten to describe the actual current state: xlsx/pptx route through
Skills as an opt-in alongside their hand-rolled default, docx/pdf are
Skills-only with no such default to fall back to.

## Tests

`tests/test_zc_word_pdf.py` (new, 12 tests): both modules' upload
path (called once, only when an input file is given), upload-failure and
missing-file-id exit paths, container-id reuse across turns, the
API-error path not crashing the loop, generated-file download, and a
check that each module sends the right skill name (`["docx"]` /
`["pdf"]"`) rather than copy-pasting the other's.

`tests/test_cli_wiring.py` (+11 tests): flag parsing for both new flags
(with a file, with the bare flag, defaulting to `None` when omitted),
and dispatch-level checks — monkeypatched `cmd_docx_chat` /
`cmd_pdf_chat` — that `--docx-native FILE --docx-output OUT` and the
`--pdf-native` equivalent actually reach the new modules with the right
arguments, including the bare-flag-passes-`None`-input-path case. The
existing `test_every_cmd_function_is_referenced_in_main` parametrized
test picked up `zc_word.py` and `zc_pdf.py` automatically (it
globs `zc_*.py`) — no changes needed there, and it passed on the
first run, confirming both new `cmd_*` functions were wired correctly
before any dedicated test was even written for them.

Full suite: **416 tests, regression-clean** (`tests/test_webapp_server.py`
still needs an installed-but-incomplete `fastapi`/`starlette` stack in
this environment — `starlette.testclient` additionally requires a
package called `httpx2`, not installed — a local dependency gap, not a
code issue; excluded from the count, same convention as prior cycles).

## Scope note: not touched

- **Custom Skills** (an account's own, not the four pre-built ones) —
  `SkillRef(type="custom", ...)` already supports the wire format;
  nothing about this cycle's two new modules is pptx/xlsx/docx/pdf-
  specific at the client level. Adding a CLI path to attach a custom
  skill_id to an arbitrary prompt is a different feature (no natural
  "chat loop" shape — it depends entirely on what the custom Skill
  does) and wasn't part of what this cycle set out to close.
- **A hand-rolled docx/pdf fallback** — could be built the way
  `zc_excel.py` reimplements xlsx by hand with pandas/openpyxl. Not
  attempted here: this cycle's gap was specifically "a documented API
  capability with zero CLI access," not "give these formats a second,
  Skills-independent implementation." Worth a future `ROADMAP.md` entry
  if someone needs docx/pdf generation without Skills access on their
  account; not invented here.
