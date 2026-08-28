# v1.29.0 — Textual TUI + web console streaming/sessions/theme upgrade

**Scope requested:** "Advanced Professional TUI / Frontend / Backend" —
a deep-dive across all three of wire's non-argparse front ends: a new
terminal TUI, and an upgrade to the existing web console's frontend and
backend (added in v1.28.0).

This was a feature deep-dive, not a `platform.zc.com/docs` gap-audit
cycle — no new Anthropic API surface is involved here beyond what
`coder.py`/`zc_stream.py` already wrapped. `ROADMAP.md`'s "last
audited" date is unchanged.

## 1. CLI TUI — `tui.py` (new)

Built on [Textual](https://textual.textualize.io/), chosen (over `rich`
or `prompt_toolkit`) because the ask was a full interactive TUI app, not
just styled output or input completion — Textual is the only one of the
three that gives a real widget/layout/event model.

**What it reuses, unchanged:**
- `coder.Coder` — non-streaming path (`--stream` switch off)
- `personalities.PersonalityManager`, `skills.SkillManager`
- `zc_models.MODEL_CATALOG`
- `main.AGENT_SYSTEM_PROMPTS` (imported lazily inside a function, not at
  module scope — `main.py` imports `tui.py` for `--tui`, so a top-level
  `from main import ...` in `tui.py` would be circular)

**What's new:** the streaming path doesn't go through `coder.Coder`
(which is non-streaming only) or `zc_stream.StreamCoder` (which
prints to stdout, wrong for a TUI widget) — `tui.py` has its own
`_stream_reply()` using the `zc` SDK directly, structurally
identical to `StreamCoder.stream()`'s `content_block_delta`/`text_delta`
event handling, but pushing each delta into a `ChatMessage` widget via
`call_from_thread()` instead of `print()`. Generation runs on a Textual
`@work(thread=True)` worker so a long response never blocks the event
loop (input, scrolling, and the footer keybindings all stay live mid-
stream).

**Optional dependency handling:** `textual>=0.80.0` is commented into
`requirements.txt` the same way `pandas`/`python-pptx` are for
`--excel`/`--pptx` — not required for the rest of the CLI. Importing
`tui.py` without `textual` installed raises `ImportError` with an exact
`pip install` command, not a traceback; `tests/test_tui.py` covers this
via `pytest.importorskip` (whole file skips cleanly) plus one test that
simulates the missing-package path directly by clearing `sys.modules`.

**Naming collision caught during testing:** `ChatMessage` (subclassing
Textual's `Static`) originally named its own render-string helper
`_render()`. `Static` already has an internal `_render()` Textual calls
during layout — the override broke on the very first mount with
`TypeError: _render() missing 2 required positional arguments`. Renamed
to `_format()`. Caught by `tests/test_tui.py`'s headless
`App.run_test()` run, not by `py_compile` (which can't catch a method-
signature collision with a base class).

**Also caught during testing:** `self.dark = not self.dark` — the
boolean `dark` attribute this pattern is commonly written with is gone
in the installed `textual==8.2.8`; toggling now goes through the
`theme` string property (`action_toggle_dark` swaps between
`"textual-dark"`/`"textual-light"`).

## 2. Web console backend — `webapp/backend/server.py`

- **`POST /api/chat/stream`** — SSE. `data:` lines are
  `{"type": "token"|"done"|"error", ...}`; a client that only
  concatenates `token.text` reconstructs the same string
  `/api/chat`'s `response` field would return. Session history is
  written to the same `_sessions` dict `/api/chat` uses, so switching
  between streaming and non-streaming mid-conversation (the frontend's
  toggle) works across turns.
- **`GET /api/sessions`** — index over `_sessions`: id, turn count, and
  an 80-char preview of the first user message. Existing
  `GET/DELETE /api/sessions/{id}` untouched.
- **Validation** — `ChatRequest` gained three `field_validator`s:
  `temperature` in `[0.0, 1.0]`, `max_tokens` in `[1, 64000]`, `prompt`
  under 200k chars. Previously any float/int went straight into the
  Messages API payload and surfaced as an opaque 400 from ZaiCoder;
  now it's a same-process 422 with a field-level message.
- **Rate limiting** — `_check_rate_limit()`, a fixed-window counter
  keyed by `request.client.host`, 30 req/min, 429 past that. In-memory
  and process-local, explicitly *not* meant to survive a restart or
  span multiple processes — same scope as the existing session store.
  Guards the API key/quota behind the console from a runaway client
  loop, not from a determined attacker; a real deployment behind
  multiple workers would need a shared store (Redis, etc.) instead.

## 3. Web console frontend — `webapp/frontend/`

- **Streaming UI** — `EventSource` can't send a POST body, so
  streaming goes through `fetch()` + `ReadableStream` + manual SSE
  `data:` framing in `app.js`'s `sendStreaming()`. A blinking cursor
  span tracks the in-progress reply; markdown re-renders on every
  token (cheap enough at chat-response lengths, avoids maintaining a
  separate "append raw text" vs "render markdown" code path).
- **Lite markdown** — `renderMarkdownLite()` handles exactly two
  constructs: fenced code blocks (```lang ... ```) and inline
  `` `code` ``. Deliberately not a full CommonMark parser — no new
  dependency, and a coding assistant's replies rarely use anything
  markdown offers beyond those two. Each code block gets a "copy"
  button (`navigator.clipboard.writeText`).
- **Sessions sidebar** — polls `GET /api/sessions` every 15s (health
  already polls every 20s) and on every chat completion; clicking an
  entry calls `GET /api/sessions/{id}` and replays its `history` into
  the transcript.
- **Theme toggle** — `html[data-theme="light"]` CSS variable block
  overriding the existing dark-theme tokens wholesale, not scattered
  per-component overrides; persisted via `localStorage` (wrapped in
  try/catch — private-browsing contexts can throw on `setItem`).

## 4. Makefile

New `tui` target (`python main.py --tui`) next to `run`. The web
console's `build`/`start`/`stop`/`restart`/`update`/`upgrade`/`status`/
`logs` lifecycle from v1.28.0 is unchanged — `--tui` runs in the
CLI's own environment, not the web console's `.web-venv/`.

## 5. Tests

- `tests/test_tui.py` — Textual's headless `App.run_test()` harness
  (`pytest-asyncio` added to `requirements-dev.txt`, `asyncio_mode =
  "auto"` set in `pyproject.toml`). Covers: sidebar/transcript mount,
  missing-API-key warning, a full submit → user+assistant message
  round trip (generation mocked via a fake `zc_sdk.ZaiCoder`),
  new-session reset, combined system-prompt building from
  agent+skill+personality, temperature-input fallback/clamping, and
  the missing-`textual` `ImportError` message.
- `tests/test_webapp_server.py` — FastAPI `TestClient`. Covers the
  new streaming/sessions endpoints, validation 422s, rate-limit 429,
  and (for streaming) a fake `zc` module injected via
  `monkeypatch.setitem(sys.modules, ...)` so no real SDK/network call
  happens.
- Full suite after this cycle: **248 tests, regression-clean.**

## Explicitly deferred

- **WebSocket transport** for the web console — SSE already covers
  the one-way (server→client) streaming need; a bidirectional
  protocol would add complexity (ping/pong, reconnect logic) with no
  corresponding requirement (the client never needs to push anything
  mid-stream).
- **Persistent session storage** — still in-memory/process-local, same
  as v1.28.0's original design. A real multi-worker deployment would
  need this, but it wasn't part of the current scope.
- **Full CommonMark rendering** — see "Lite markdown" above.

## Also fixed in passing

`pyproject.toml`'s `[project].version` had drifted to `1.20.0` while
`main.py`'s `VERSION` constant moved on through several cycles to
`1.28.0` — neither file's version had been the source of truth for the
other. Both now read `1.29.0`.
