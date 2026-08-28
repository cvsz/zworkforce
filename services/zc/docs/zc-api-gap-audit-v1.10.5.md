# AI Model Coder CLI v1.10.5 — Gap Audit vs. Current zAICoder API (checked 2026-07-02)

This project is unusually well-maintained for this kind of audit: `docs/19–23_upgrade_*.md`
already record a running self-audit history, and `zc_models.py` / `zc_fable5.py` /
`zc_cost_optimizer.py` explicitly timestamp their data against `platform.zc.com/docs`
as of 2026-07-02. The gaps below are everything **still missing or stale** after that history,
found by cross-checking every module against the current zAICoder Platform docs.

## 1. Missing entirely (no module, no flag, no code)

| Feature | What it is | Where it should live |
|---|---|---|
| **Advisor tool** (`advisor_20260301`, beta `advisor-tool-2026-03-01`) | Server tool that pairs a fast executor model with a stronger advisor model consulted mid-generation at decision points (`server_tool_use` → `advisor_tool_result`, `pause_turn` resume flow, per-iteration billing at the advisor model's rate). Supported executors: Opus 4.6+, Sonnet 4.6+, Haiku 4.5, Fable 5. Not available on Bedrock/Vertex/Foundry. | New `zc_advisor.py`; add to `SERVER_TOOLS` in `zc_tools.py` |
| **Task budgets** (beta `task-budgets-2026-03-13`) | Advisory token budget for a full agentic loop (thinking + tool calls + tool results + output); zAICoder sees a running countdown and prioritizes/wraps up as it depletes. GA on Opus 4.7 and 4.8. | `zc_tools.py` or `zc_code.py` agent loop |
| **Tool Use Examples** (`input_examples` field on tool defs, beta `advanced-tool-use-2025-11-20`) | Third feature from the same Nov 2025 "advanced tool use" release as Tool Search Tool and Programmatic Tool Calling — worked examples of correct tool calls, shown by Anthropic to raise complex-parameter accuracy from 72%→90%. Expands automatically when a deferred tool is discovered via tool search. | `zc_tools.py`, `ToolCoder` tool-definition builder |
| **Programmatic Tool Calling — actual implementation** | `zc_tools.py`'s docstring claims this, but there's no `allowed_callers` field, no `code_execution_20260120` (the minimum version, now **GA, no beta header**), no handling of the `caller` field on `tool_use` blocks. It's a bullet point, not code. | `zc_tools.py` |
| **Embeddings** | No module at all. `zc_memory.py` even says "swap in embeddings for larger stores" and never does. | New `zc_embeddings.py` |
| **MCP tunnels** (research preview, `mcp-tunnels-2026-06-22`, `/v1/tunnels`) | New surface for exposing local MCP servers remotely; moved off the Admin API in the last couple of months. | `zc_agents_sdk.py` |
| **Compaction** (automatic context-window summarization) | Distinct from `zc_tools.py`'s `context_management`/`clear_tool_uses_20250919` (which *clears* stale content) — compaction *summarizes* the conversation when nearing the limit. Listed as its own doc page alongside, not instead of, context editing. | `zc_sessions.py` or `zc_tools.py` |
| **Fine-grained tool streaming** | Stream `tool_use` JSON input without server-side buffering, for latency-sensitive apps. | `zc_stream.py` |
| **`stop_details` on refusals** | Refusal responses now carry a documented `category` (`cyber`/`bio`/`null`) + explanation, no beta header needed — lets you route different refusal classes differently. `zc_fable5.py` handles `stop_reason=="refusal"` but never reads `stop_details`. | `zc_fable5.py` |
| **Refusal billing exemption** | Requests that return `stop_reason:"refusal"` with no generated output are no longer billed. Not reflected in `zc_cost_optimizer.py` or `zc_metrics.py`'s cost tracking. | `zc_cost_optimizer.py`, `zc_metrics.py` |

## 2. Present but stale (tool/model version strings)

`zc_tools.py`, `zc_code_exec.py`, and `zc_models.py` pin dated tool-type strings
that are now behind the current defaults:

- `web_search_20250305` → docs' current example uses `web_search_20260209`
- `code_execution_20250522` (two places) → should be `code_execution_20260120` at minimum to
  even support Programmatic Tool Calling (REPL-state persistence requirement)
- `computer_20250124` / `bash_20250124` / `text_editor_20250124` → worth re-checking against
  the current per-model computer-use version table before assuming these are still the latest
  zAICoder Sonnet 5 / Opus 4.8 pairings support

None of these are hard failures (old versions still work until Anthropic retires them), but
`zc_models.py`'s own retirement-scanner pattern (`check_retired`/`RETIRED_MODELS`) has no
equivalent for *tool* version strings — worth a `RETIRED_TOOL_VERSIONS` table for the same
reason it exists for models.

## 3. Already flagged by the project itself, still open

From `docs/23_upgrade_v1.10.5.md`'s own "What was NOT changed" section:

> Programmatic Tool Calling and Tool Use Examples (the other two features from the same
> "advanced tool use" announcement as the tool search tool) — noted but not implemented this
> pass; flagging for a future round if wanted.

Both are now confirmed still open per the analysis above (§1), plus Advisor tool and Task
budgets, which the project hasn't flagged yet at all.

## 4. Not gaps (verified correctly implemented)

For completeness — these were checked and are in good shape, no action needed:
- Memory tool (`memory_20250818`), context editing (`clear_tool_uses_20250919`,
  `clear_thinking_20251015`), tool search tool — all added in v1.10.5, correct.
- Model catalog (`zc_models.py`) — Sonnet 5 / Opus 4.8 / Haiku 4.5 / Fable 5 / Mythos 5
  entries, retired-model registry, deprecation scanner — accurate and current.
- MCP server connector (stdio/SSE/HTTP) in `zc_agents_sdk.py` / `zc_code.py` — this
  is the standing Messages API `mcp_servers` feature, correctly separate from the newer MCP
  tunnels feature above.
- Citations / search-result content blocks (`zc_citations.py`) — correct GA usage.
- Structured outputs, prompt caching, batch API, Files API, vision, sandboxed bash — all
  present and aligned with current docs.

## Suggested upgrade order

1. **Advisor tool** and **Programmatic Tool Calling** (real implementation) — biggest capability
   gaps, both cost/latency-relevant, both have public cookbook examples to build against.
2. **Tool Use Examples** — cheap to add (`input_examples` on existing tool defs), pairs directly
   with #1's PTC tool definitions.
3. Tool version string bump (`web_search`, `code_execution`) + `RETIRED_TOOL_VERSIONS` table —
   low effort, unblocks PTC's REPL-state requirement.
4. Task budgets, compaction, fine-grained streaming, `stop_details`, refusal billing — smaller,
   independent additions.
5. Embeddings module, MCP tunnels — lowest priority unless a concrete use case needs them.
