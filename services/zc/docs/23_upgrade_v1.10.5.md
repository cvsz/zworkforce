# v1.10.5 — Native memory tool, context editing, tool search tool

Prompted by a direct audit request: "what's missing, relative to zAICoder's
actual current API capabilities?" Three concrete gaps found in
`zc_tools.py` and closed in this pass.

## What was missing

`zc_tools.py`'s `SERVER_TOOLS` covered web_search, web_fetch,
code_execution, bash, text_editor, and computer_use — but not:

1. **The memory tool** (`memory_20250818`) — GA since 2025-09-29, no beta
   header required. This project already has `zc_memory.py`, but
   that's a custom database-backed memory system this CLI invented, not
   ZaiCoder's server-declared/client-executed memory tool. Different
   thing, same name is coincidental.
2. **Context editing** (`context-management-2025-06-27` beta) — automatic
   clearing of stale tool results (`clear_tool_uses_20250919`) and old
   thinking blocks (`clear_thinking_20251015`) on long agent runs, so a
   multi-hour tool-heavy session doesn't silently degrade as old content
   piles up in the transcript.
3. **The tool search tool** (`tool-search-tool-2025-10-19` beta) — lets
   zAICoder discover tools on demand instead of loading every definition
   upfront, relevant once a tool library gets into the dozens/hundreds
   range.

## What changed

**`zc_tools.py`**

- `SERVER_TOOLS` — added `memory` and `tool_search` entries.
- New `SERVER_TOOL_BETAS` dict replaces the old single membership check
  (`if name in ("bash", "text_editor", "computer_use", "code_execution")`)
  that applied one beta header to four tools. That check was wrong for
  `code_execution`, which needs its own `code-execution-2025-05-22` line,
  not `computer-use-2025-01-24` — found and fixed while wiring in the new
  tools' beta requirements alongside it.
- New `build_context_management()` — builds the `context_management`
  request payload for `clear_tool_uses_20250919` (+ optional
  `clear_thinking_20251015`), with sane defaults (30k input-token
  trigger, keep last 3 tool uses).
- New `MemoryToolHandler` class — the client-side implementation the
  memory tool requires (it's server-declared, client-executed: zAICoder
  emits `tool_use` blocks with a `command` field, your application
  carries them out). Supports view/create/str_replace/insert/delete/rename
  against a local directory. Every path is resolved via `_resolve()` and
  checked to stay inside the configured base directory before any disk
  access — including bare `/memories` and `../` traversal attempts —
  matching ZaiCoder's documented path-traversal-protection requirement.
- New `ToolCoder.run_agent_with_memory()` — a full tool-use agent loop
  wired specifically to `MemoryToolHandler`, so `memory` tool_use blocks
  get dispatched automatically instead of requiring the caller to
  hand-roll the command routing every time. Uses context management by
  default (long memory-backed sessions are exactly the case context
  editing is for).
- `generate_with_server_tools()` gained an optional `context_management`
  parameter and now builds its beta-header list from `SERVER_TOOL_BETAS`
  per-tool instead of the old blanket check.
- `cmd_list_server_tools()` now tags each tool with its required beta
  header (or nothing, for the three that are GA).
- New `cmd_memory_agent()` CLI entry point.

**`main.py`** — new `--memory-agent PROMPT` (+ `--memory-dir DIR`,
default `~/.ai-coder/memory`) and `--context-management` flag (applies to
`--server-tool`).

## What was NOT changed

- `zc_memory.py` — left as-is. It's a legitimately different feature
  (this CLI's own tagged/namespaced memory store with importance and
  retention fields) and isn't a duplicate of the native memory tool; the
  two can coexist, they just shouldn't be confused for each other.
- Programmatic Tool Calling and Tool Use Examples (the other two features
  from the same "advanced tool use" announcement as the tool search tool)
  — noted but not implemented this pass; flagging for a future round if
  wanted.

## Verification

- `python3 -m py_compile *.py` — all modules compile after the edits.
- `--list-server-tools` smoke-tested — correctly shows `memory` and
  `tool_search` with the right beta tags (`memory` untagged/GA,
  `tool_search` tagged `tool-search-tool-2025-10-19`).
- `MemoryToolHandler` smoke-tested standalone (no API key needed):
  create → view → str_replace → view round-trip works; a `../../etc/passwd`
  traversal attempt through `/memories/../../etc/passwd` is correctly
  rejected; bare `/memories` (no trailing slash) correctly resolves to
  the handler's root directory after a resolution bug was caught and
  fixed during testing.
