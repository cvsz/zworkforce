"""
zc_tools.py — Tool Use (Function Calling)
AI Model Coder CLI v1.11.0

Full tool-use support:
  • Custom tool definitions (JSON Schema)
  • Parallel tool use
  • Strict tool use (validated inputs)
  • Tool runner (auto-executes registered Python callables)
  • Built-in server tools: web_search, web_fetch, code_execution, bash,
    text_editor, memory, tool_search
  • Programmatic tool calling (real implementation, not just a bullet
    point) — allowed_callers on your tool definitions + code_execution_
    20260120, so zAICoder can invoke your tools from code inside the
    sandbox instead of one round-trip per call
  • Tool Use Examples (input_examples) — worked examples of correct
    tool calls attached to a tool definition, for parameter accuracy
    on complex schemas
  • Memory tool (memory_20250818, GA) — client-side handler with
    path-traversal protection, wired into a dedicated agent loop
  • Context editing (context-management-2025-06-27 beta) — auto-clear
    stale tool results / thinking blocks on long agent runs
  • Compaction (compact-2026-01-12 beta) — server-side conversation
    summarization for effectively-unbounded agent sessions
  • Task budgets (task-budgets-2026-03-13 beta) — advisory token budget
    for a full agentic loop, model self-regulates against a countdown
  • Tool search tool (tool-search-tool-2025-10-19 beta) — on-demand tool
    discovery for large tool libraries, descriptor only (defer_loading
    marking on your own tool definitions is on you)

Version-string / beta-header notes (checked against platform.zc.com/docs
as of 2026-07-02 — re-verify before relying on this for production traffic,
the same caveat zc_models.py already carries for model IDs):
  • web_search bumped 20250305 -> 20260209 to match the current docs example.
  • code_execution bumped 20250522 -> 20260120 — this is documented as the
    minimum version for programmatic tool calling (adds REPL-state
    persistence) and is now GA (no beta header needed to adopt it).
  • Programmatic tool calling itself still needs the advanced-tool-use-
    2025-11-20 beta header per the public cookbook / engineering post as of
    this check; only add it when a tool actually sets allowed_callers.
  • Tool Use Examples (input_examples) also gates on advanced-tool-use-
    2025-11-20.
  • computer_use bumped default to computer-use-2025-11-24 for current
    models (Sonnet 5, Opus 4.8/4.7/4.6, Sonnet 4.6, Opus 4.5); older models
    (Sonnet 4.5, Haiku 4.5) still need computer-use-2025-01-24. See
    computer_use_tool_for_model().

CLI flags:
  --tool-use TOOL         Run with a named built-in tool
  --tool-file FILE        Load tool definitions from a JSON file
  --tool-run              Auto-run tool calls (tool runner mode)
  --parallel-tools        Enable parallel tool calling
  --strict-tools          Strict schema validation on tool inputs
  --memory-agent PROMPT   Run an agent loop backed by the native memory tool
  --memory-dir DIR        Where the memory tool's local files live
                          (default: ~/.ai-coder/memory)
  --context-management    Enable context editing (clear_tool_uses) on
                          --tool-agent / --server-tool calls
  --compaction            Enable server-side compaction on --server-tool
                          calls (compact_20260112)
  --task-budget N         Set an advisory task_budget (tokens) on
                          --server-tool calls (beta, Opus 4.7/4.8,
                          Fable 5, Mythos 5 only)
  --ptc                   With --server-tool code_execution: mark any
                          --tool-file custom tools as callable from code
                          (allowed_callers), enabling programmatic tool
                          calling instead of one round-trip per call
"""

import json
import urllib.error
import urllib.request
from typing import Callable, Optional, Any

from wire.exceptions import AICoderError
from wire.resilience import CircuitBreaker, retry, urlopen_json

# ── Built-in server tool descriptors ──────────────────────────────────────

SERVER_TOOLS: dict[str, dict[str, Any]] = {
    "web_search": {
        "type": "web_search_20260318",
        "name": "web_search",
    },
    "web_fetch": {
        "type": "web_fetch_20260318",
        "name": "web_fetch",
    },
    "code_execution": {
        "type": "code_execution_20260521",
        "name": "code_execution",
    },
    "bash": {
        "type": "bash_20250124",
        "name": "bash",
    },
    "text_editor": {
        "type": "text_editor_20250124",
        "name": "str_replace_based_edit_tool",
    },
    "computer_use": {
        "type": "computer_20251124",
        "name": "computer",
        "display_width_px":  1024,
        "display_height_px": 768,
    },
    "memory": {
        "type": "memory_20250818",
        "name": "memory",
    },
    "tool_search": {
        "type": "tool_search_tool_20251019",
        "name": "tool_search",
    },
}

# computer_use tool-version support is split by model generation. Current
# models (Sonnet 5, Opus 4.8/4.7/4.6, Sonnet 4.6, Opus 4.5) take the newer
# computer-use-2025-11-24 pairing; Sonnet 4.5 / Haiku 4.5 (and the retired
# Opus 4 / Sonnet 4) only support computer-use-2025-01-24. Sending the wrong
# pairing 400s with "does not support tool types: ...", per the docs.
COMPUTER_USE_TOOL_VERSIONS = {
    "2025-11-24": {"type": "computer_20251124", "beta": "computer-use-2025-11-24"},
    "2025-01-24": {"type": "computer_20250124", "beta": "computer-use-2025-01-24"},
}
_COMPUTER_USE_2025_01_24_MODELS = {
    "zc-sonnet-4-5", "zc-haiku-4-5", "zc-haiku-4-5-20251001",
    "zc-sonnet-4-20250514", "zc-sonnet-4-0",
    "zc-opus-4-20250514", "zc-opus-4-0",
}


# Tool-version equivalent of zc_models.py's RETIRED_MODELS /
# check_retired() pattern — the gap audit flagged that tool-type strings had
# no retirement tracking the way model IDs do. Old dated versions of a tool
# generally keep working until Anthropic actually retires them (unlike
# models, where retirement is a hard cutover), so this is advisory: it flags
# "there's a newer version with more capability" rather than "this will
# break". Entries only cover versions actually superseded per the Tool
# reference page's capability-keyed / model-keyed notes as of 2026-07-02 —
# add to this table rather than assuming silence means current.
RETIRED_TOOL_VERSIONS: dict = {
    "web_search_20250305": {
        "replacement": "web_search_20260318",
        "notes": "Still works. 20260209 added dynamic content filtering; "
                 "20260318 adds the response_inclusion param (drop a "
                 "consumed result's blocks from the response — see "
                 "programmatic tool calling).",
    },
    "web_search_20260209": {
        "replacement": "web_search_20260318",
        "notes": "Still works. 20260318 adds response_inclusion (v1.24.0).",
    },
    "web_fetch_20250910": {
        "replacement": "web_fetch_20260318",
        "notes": "Still works. 20260209 added dynamic content filtering, "
                 "20260309 added use_cache, 20260318 adds response_inclusion "
                 "(v1.24.0) — see Web fetch tool docs for the full chain.",
    },
    "web_fetch_20250124": {
        "replacement": "web_fetch_20260318",
        "notes": "Older than web_fetch_20250910 above — see that entry for "
                 "the full upgrade chain to 20260318.",
    },
    "code_execution_20250522": {
        "replacement": "code_execution_20260521",
        "notes": "Still works, but 20260120 is the minimum version for "
                 "programmatic tool calling (adds REPL-state persistence); "
                 "20260521 additionally discloses the sandbox's 90-second "
                 "per-cell wall-clock limit in the tool description "
                 "(v1.24.0), so zAICoder budgets long-running cells.",
    },
    "code_execution_20250825": {
        "replacement": "code_execution_20260521",
        "notes": "Both 20250522 and 20250825 are accepted interchangeably "
                 "in allowed_callers per the programmatic tool calling "
                 "docs; 20260521 is current as of v1.24.0.",
    },
    "code_execution_20260120": {
        "replacement": "code_execution_20260521",
        "notes": "Still works and is still the minimum version for "
                 "programmatic tool calling. 20260521 (v1.24.0) additionally "
                 "discloses the sandbox's 90-second per-cell wall-clock "
                 "limit in the tool description, so zAICoder budgets "
                 "long-running cells instead of writing one loop that "
                 "times out.",
    },
    "text_editor_20250124": {
        "replacement": "text_editor_20250728",
        "notes": "Model-keyed, not a strict upgrade: 20250124 is for pre-zAICoder-4 "
                 "models, 20250728 is for zAICoder 4 series. Use the one matching "
                 "your model, not automatically the newer string.",
    },
    "computer_20250124": {
        "replacement": "computer_20251124",
        "notes": "Model-keyed, see computer_use_tool_for_model() — current models "
                 "(Sonnet 5, Opus 4.5+) use 20251124, older models still need "
                 "20250124. Sending the wrong pairing 400s.",
    },
}


def check_retired_tool_version(tool_type: str) -> Optional[dict]:
    """Return the retirement/upgrade record for a dated tool-type string, or
    None if it isn't in RETIRED_TOOL_VERSIONS. Mirrors
    zc_models.check_retired() — an unmatched string is just not tracked
    here, not necessarily current."""
    return RETIRED_TOOL_VERSIONS.get(tool_type)

def computer_use_tool_for_model(model: str, width: int = 1024, height: int = 768):
    """Return (tool_descriptor, beta_header_or_None) for the computer_use
    tool version this model actually supports. Defaults to the newer
    2025-11-24 pairing; falls back to 2025-01-24 for the older model IDs
    known to require it. Re-verify against the Tool reference page if you're
    on a model not listed here."""
    key = "2025-01-24" if model in _COMPUTER_USE_2025_01_24_MODELS else "2025-11-24"
    v = COMPUTER_USE_TOOL_VERSIONS[key]
    tool = {"type": v["type"], "name": "computer",
            "display_width_px": width, "display_height_px": height}
    return tool, v["beta"]


# Beta headers required per server tool. Tools not listed here (web_search,
# web_fetch, memory, code_execution as of 2026-07-02 — GA, no header needed)
# omit the key. code_execution_20260120 dropped its beta requirement per the
# platform release notes ("no beta header is required" to adopt it); it's
# still needed if you deliberately pin an older code_execution_2025xxxx type.
# Previously this was collapsed to a single "computer-use-2025-01-24" check
# covering bash/text_editor/computer_use/code_execution, which was wrong for
# code_execution (its own beta line) — split out per-tool here.
SERVER_TOOL_BETAS = {
    "bash":          "computer-use-2025-01-24",
    "text_editor":   "computer-use-2025-01-24",
    "computer_use":  "computer-use-2025-11-24",
    "tool_search":   "tool-search-tool-2025-10-19",
}

# context_management requires this beta header regardless of which edit
# types are used (clear_tool_uses_20250919, clear_thinking_20251015,
# compact_20260112 ...).
CONTEXT_MANAGEMENT_BETA = "context-management-2025-06-27"

# Compaction is its own edit type inside context_management.edits, but it's
# gated by a *different* beta header than plain context editing.
COMPACTION_BETA = "compact-2026-01-12"

# Task budgets — advisory token budget for a whole agentic loop. Beta on
# zAICoder Fable 5, zAICoder Mythos 5, Opus 4.8, and Opus 4.7 only; not supported
# on zAICoder or Cowork surfaces, Messages API only.
TASK_BUDGET_BETA = "task-budgets-2026-03-13"
TASK_BUDGET_MODELS = {
    "zc-fable-5", "zc-mythos-5",
    "zc-opus-4-8", "zc-opus-4-7",
}

# Programmatic Tool Calling (allowed_callers) and Tool Use Examples
# (input_examples) — the two "advanced tool use" features that were still
# just docstring bullets before this pass. Both gate on the same beta header
# per the public cookbook / engineering announcement.
ADVANCED_TOOL_USE_BETA = "advanced-tool-use-2025-11-20"


def build_context_management(
    clear_tool_uses: bool = True,
    clear_tool_uses_trigger_tokens: int = 30000,
    keep_last_n_tool_uses: int = 3,
    clear_thinking: bool = False,
    keep_last_n_thinking_turns: int = 2,
    compact: bool = False,
    compact_trigger_tokens: int = 150000,
    compact_instructions: Optional[str] = None,
    compact_pause_after: bool = False,
) -> dict:
    """Build a context_management payload for long agent loops.

    clear_tool_uses/clear_thinking: auto-clears stale tool_result content
    (and optionally old thinking blocks) once the conversation crosses
    clear_tool_uses_trigger_tokens, keeping the most recent N tool uses
    intact. Requires CONTEXT_MANAGEMENT_BETA.

    compact: adds the compact_20260112 edit (server-side conversation
    summarization — distinct from clearing: clearing *drops* old tool
    results, compaction *summarizes* the whole conversation once it nears
    the context limit). Requires COMPACTION_BETA in addition to
    CONTEXT_MANAGEMENT_BETA. When compact_pause_after is True, the API
    returns stop_reason:"compaction" after generating the summary so you
    can inject extra content before continuing — see resume_after_compaction().

    Callers using generate_with_server_tools() get the right beta headers
    added automatically based on which edits are present here."""
    edits = []
    if clear_tool_uses:
        edits.append({
            "type": "clear_tool_uses_20250919",
            "trigger": {"type": "input_tokens", "value": clear_tool_uses_trigger_tokens},
            "keep": {"type": "tool_uses", "value": keep_last_n_tool_uses},
        })
    if clear_thinking:
        edits.append({
            "type": "clear_thinking_20251015",
            "keep": {"type": "thinking_turns", "value": keep_last_n_thinking_turns},
        })
    if compact:
        edit: dict[str, Any] = {
            "type": "compact_20260112",
            "trigger": {"type": "input_tokens", "value": compact_trigger_tokens},
        }
        if compact_instructions:
            edit["instructions"] = compact_instructions
        if compact_pause_after:
            edit["pause_after_compaction"] = True
        edits.append(edit)
    return {"edits": edits}


def resume_after_compaction(messages: list, compaction_response: dict,
                             extra_content: Optional[list] = None) -> list:
    """After a call made with compact_pause_after=True returns
    stop_reason:"compaction", the API expects the compaction block appended
    as an assistant turn before you continue. extra_content lets you inject
    additional content blocks (e.g. a reminder message) right after it, per
    the documented pause_after_compaction pattern."""
    content = list(compaction_response.get("content", []))
    if extra_content:
        content = content + extra_content
    return messages + [{"role": "assistant", "content": content}]


def build_task_budget(budget_tokens: int) -> dict:
    """Build the task_budget payload. Advisory only — the model sees a
    running countdown and self-regulates; it isn't a hard cap the way
    max_tokens is. Requires TASK_BUDGET_BETA and a model in
    TASK_BUDGET_MODELS. Set once on the initial request and don't mutate it
    client-side turn-over-turn — doing so invalidates prompt cache prefixes
    that include it, per the documented caching note."""
    return {"budget_tokens": budget_tokens}


def with_input_examples(tool_def: dict, examples: list[dict]) -> dict:
    """Attach Tool Use Examples (input_examples) to a tool definition —
    worked examples of correct calls, shown in Anthropic's own testing to
    raise complex-parameter accuracy from 72% to 90%. Each example is a
    dict matching the tool's input_schema, e.g.
    [{"location": "San Francisco, CA", "units": "imperial"}]. Requires
    ADVANCED_TOOL_USE_BETA. Adds tokens to your tool definitions — most
    valuable on tools with several optional/interacting parameters, not
    every tool in your library."""
    out = dict(tool_def)
    out["input_examples"] = examples
    return out


def with_allowed_callers(tool_def: dict, callers: Optional[list[str]] = None) -> dict:
    """Mark a custom tool definition as callable from Programmatic Tool
    Calling — zAICoder can then invoke it directly from Python code running
    inside the code_execution sandbox instead of a full model round-trip
    per call. callers defaults to ["code_execution_20260120"], matching the
    code_execution version in SERVER_TOOLS. Requires the code_execution
    server tool to be present in the same request's tools array, and
    (pending full GA) ADVANCED_TOOL_USE_BETA."""
    out = dict(tool_def)
    out["allowed_callers"] = callers or [SERVER_TOOLS["code_execution"]["type"]]
    return out


class MemoryToolHandler:
    """Client-side handler for the memory_20250818 server tool. The memory
    tool is server-declared but client-executed: zAICoder emits tool_use
    blocks with a `command` field (view/create/str_replace/insert/delete/
    rename), and this class carries them out against a local directory,
    returning tool_result content for the next turn.

    All paths are confined to base_dir — every command's `path` argument is
    resolved and checked to still be inside base_dir before touching disk,
    per Anthropic's documented path-traversal-protection requirement for
    memory tool implementations."""

    def __init__(self, base_dir: str = "~/.ai-coder/memory"):
        import os
        self.base_dir = os.path.abspath(os.path.expanduser(base_dir))
        os.makedirs(self.base_dir, exist_ok=True)

    def _resolve(self, rel_path: str) -> str:
        import os
        # Memory tool paths are always given relative to /memories.
        rel_path = rel_path.lstrip("/")
        if rel_path == "memories":
            rel_path = ""
        elif rel_path.startswith("memories/"):
            rel_path = rel_path[len("memories/"):]
        full = os.path.abspath(os.path.join(self.base_dir, rel_path))
        if not (full == self.base_dir or full.startswith(self.base_dir + os.sep)):
            raise PermissionError(f"Path escapes memory directory: {rel_path}")
        return full

    def handle(self, command_input: dict) -> str:
        import os
        cmd = command_input.get("command")
        try:
            if cmd == "view":
                path = self._resolve(command_input.get("path", "/memories"))
                if os.path.isdir(path):
                    entries = sorted(os.listdir(path))
                    return "\n".join(entries) if entries else "(empty directory)"
                with open(path) as f:
                    return f.read()
            elif cmd == "create":
                path = self._resolve(command_input["path"])
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    f.write(command_input.get("file_text", ""))
                return f"Created {command_input['path']}"
            elif cmd == "str_replace":
                path = self._resolve(command_input["path"])
                with open(path) as f:
                    content = f.read()
                old, new = command_input["old_str"], command_input.get("new_str", "")
                if content.count(old) != 1:
                    return f"[ERROR] old_str must match exactly once, found {content.count(old)}"
                with open(path, "w") as f:
                    f.write(content.replace(old, new, 1))
                return f"Edited {command_input['path']}"
            elif cmd == "insert":
                path = self._resolve(command_input["path"])
                with open(path) as f:
                    lines = f.readlines()
                idx = command_input.get("insert_line", len(lines))
                lines.insert(idx, command_input.get("insert_text", "") + "\n")
                with open(path, "w") as f:
                    f.writelines(lines)
                return f"Inserted into {command_input['path']} at line {idx}"
            elif cmd == "delete":
                path = self._resolve(command_input["path"])
                if os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                return f"Deleted {command_input['path']}"
            elif cmd == "rename":
                src = self._resolve(command_input["old_path"])
                dst = self._resolve(command_input["new_path"])
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                os.rename(src, dst)
                return f"Renamed {command_input['old_path']} -> {command_input['new_path']}"
            else:
                return f"[ERROR] Unknown memory command: {cmd}"
        except FileNotFoundError:
            return f"[ERROR] Not found: {command_input.get('path')}"
        except PermissionError as e:
            return f"[ERROR] {e}"
        except Exception as e:
            return f"[ERROR] {e}"


# ── ToolRegistry ──────────────────────────────────────────────────────────

class ToolRegistry:
    """Register Python functions as zAICoder tools with auto-generated schemas."""

    def __init__(self):
        self._tools: dict[str, dict[str, Any]] = {}   # name → definition
        self._funcs: dict[str, Callable[..., Any]] = {}   # name → callable

    def register(self, name: str, description: str, parameters: dict[str, Any],
                 func: Callable[..., Any], strict: bool = False) -> None:
        defn: dict[str, Any] = {
            "name":         name,
            "description":  description,
            "input_schema": parameters,
        }
        if strict:
            defn["strict"] = True
        self._tools[name] = defn
        self._funcs[name] = func

    def definitions(self) -> list[dict]:
        return list(self._tools.values())

    def execute(self, name: str, inputs: dict):
        if name not in self._funcs:
            return f"[ERROR] Unknown tool: {name}"
        try:
            return self._funcs[name](**inputs)
        except Exception as e:
            return f"[TOOL ERROR] {e}"


# ── ToolCoder ─────────────────────────────────────────────────────────────

class ToolCoder:
    """zAICoder client with full tool-use support."""

    ENDPOINT = "https://api.anthropic.com/v1/messages"
    _breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)

    def __init__(self, api_key: str, model: str = "zc-xxx",
                 max_tokens: int = 4096):
        self.api_key    = api_key
        self.model      = model
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, req: "urllib.request.Request") -> dict:
        return urlopen_json(req, timeout=120)

    def _post(self, payload: dict) -> dict:
        headers = {
            "Content-Type":    "application/json",
            "x-api-key":       self.api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(
            self.ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        try:
            return self._call(req)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    # ── Single call with tools ────────────────────────────────────────────

    def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        system: Optional[str] = None,
        parallel: bool = True,
        strict: bool = False,
    ) -> dict:
        """Call zAICoder with tools. Returns raw response dict."""
        if strict:
            tools = [dict(t, **{"strict": True}) for t in tools]

        messages = [{"role": "user", "content": prompt}]
        payload: dict = {
            "model":      self.model,
            "max_tokens": self.max_tokens,
            "messages":   messages,
            "tools":      tools,
        }
        if not parallel:
            payload["parallel_tool_use"] = False
        if system:
            payload["system"] = system

        return self._post(payload)

    # ── Agentic tool runner ───────────────────────────────────────────────

    def run_agent(
        self,
        prompt: str,
        registry: ToolRegistry,
        system: Optional[str] = None,
        max_turns: int = 10,
        verbose: bool = True,
    ) -> str:
        """
        Full agentic loop: zAICoder calls tools, we execute them and return
        results, repeat until stop_reason == 'end_turn'.
        """
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        tools    = registry.definitions()
        turn     = 0

        while turn < max_turns:
            payload: dict = {
                "model":      self.model,
                "max_tokens": self.max_tokens,
                "messages":   messages,
                "tools":      tools,
            }
            if system:
                payload["system"] = system

            data = self._post(payload)
            if "error" in data:
                return f"[ERROR] {data['error']}"

            stop_reason = data.get("stop_reason", "")
            content     = data.get("content", [])

            # Append assistant turn
            messages.append({"role": "assistant", "content": content})

            if stop_reason == "end_turn":
                # Extract final text
                return "".join(
                    b.get("text", "") for b in content
                    if b.get("type") == "text"
                )

            if stop_reason != "tool_use":
                return f"[UNEXPECTED stop_reason={stop_reason}]"

            # Execute tool calls
            tool_results = []
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                tool_name = block["name"]
                tool_id   = block["id"]
                tool_input = block.get("input", {})

                if verbose:
                    print(f"\033[90m  [tool] {tool_name}({json.dumps(tool_input)[:80]})\033[0m")

                result = registry.execute(tool_name, tool_input)
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": tool_id,
                    "content":     str(result),
                })

            messages.append({"role": "user", "content": tool_results})
            turn += 1

        return "[MAX TURNS REACHED]"

    # ── With server tools ──────────────────────────────────────────────────

    def generate_with_server_tools(
        self,
        prompt: str,
        tool_names: list[str],
        system: Optional[str] = None,
        context_management: Optional[dict] = None,
        task_budget: Optional[dict] = None,
        extra_tools: Optional[list[dict]] = None,
        response_inclusion: Optional[str] = None,
    ) -> str:
        """Use Anthropic-hosted server tools (web_search, code_execution,
        memory, tool_search, etc.). Pass context_management (see
        build_context_management()) to auto-clear stale tool results /
        summarize via compaction on long-running calls, task_budget (see
        build_task_budget()) to give the model an advisory token countdown,
        and extra_tools for your own custom tool definitions — including
        ones built with with_input_examples()/with_allowed_callers() for
        Tool Use Examples / Programmatic Tool Calling. Beta headers are
        assembled automatically from whichever of these are actually used.

        `response_inclusion` (v1.24.0; requires web_search_20260318 /
        web_fetch_20260318, both defaults as of this version) is applied
        to any "web_search"/"web_fetch" entries in tool_names when given.
        Currently the only documented value is "excluded", which drops a
        *consumed* result's nested server_tool_use/result block pair from
        the response entirely — only meaningful when that result was
        consumed by a code_execution call in the same turn (the
        programmatic-tool-calling pattern). Omitted by default: no
        regression to the pre-v1.24.0 tool dict shape."""
        tools = []
        betas = []
        for name in tool_names:
            if name not in SERVER_TOOLS:
                raise ValueError(f"Unknown server tool: {name}. Available: {list(SERVER_TOOLS)}")
            if name == "computer_use":
                tool, beta = computer_use_tool_for_model(self.model)
                tools.append(tool)
                if beta:
                    betas.append(beta)
                continue
            tool = dict(SERVER_TOOLS[name])
            if response_inclusion is not None and name in ("web_search", "web_fetch"):
                tool["response_inclusion"] = response_inclusion
            tools.append(tool)
            beta = SERVER_TOOL_BETAS.get(name)
            if beta:
                betas.append(beta)

        for t in (extra_tools or []):
            tools.append(t)
            if "input_examples" in t or "allowed_callers" in t:
                betas.append(ADVANCED_TOOL_USE_BETA)

        headers_extra = {}
        payload: dict = {
            "model":      self.model,
            "max_tokens": self.max_tokens,
            "messages":   [{"role": "user", "content": prompt}],
            "tools":      tools,
        }
        if system:
            payload["system"] = system
        if context_management is not None:
            payload["context_management"] = context_management
            betas.append(CONTEXT_MANAGEMENT_BETA)
            if any(e.get("type") == "compact_20260112" for e in context_management.get("edits", [])):
                betas.append(COMPACTION_BETA)
        if task_budget is not None:
            if self.model not in TASK_BUDGET_MODELS:
                print(f"\033[93m⚠ task_budget requested but {self.model} isn't in "
                      f"TASK_BUDGET_MODELS ({sorted(TASK_BUDGET_MODELS)}) — sending anyway, "
                      f"the API will reject it if unsupported.\033[0m")
            payload["task_budget"] = task_budget
            betas.append(TASK_BUDGET_BETA)
        if betas:
            headers_extra["anthropic-beta"] = ",".join(sorted(set(betas)))

        headers = {
            "Content-Type":      "application/json",
            "x-api-key":         self.api_key,
            "anthropic-version": "2023-06-01",
            **headers_extra,
        }
        req = urllib.request.Request(
            self.ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        try:
            data = self._call(req)
        except AICoderError as e:
            return f"[API ERROR {getattr(e, 'status_code', '')}] {e.message}"

        return "".join(
            b.get("text", "") for b in data.get("content", [])
            if b.get("type") == "text"
        )

    # ── Memory-tool agent loop ───────────────────────────────────────────

    def run_agent_with_memory(
        self,
        prompt: str,
        memory: "MemoryToolHandler",
        extra_tools: Optional[list[dict]] = None,
        system: Optional[str] = None,
        max_turns: int = 10,
        use_context_management: bool = True,
        verbose: bool = True,
    ) -> str:
        """Agentic loop wired to the native memory tool: any tool_use block
        named 'memory' is dispatched to MemoryToolHandler instead of a
        registry lookup, so the memory directory persists across calls
        without the caller having to hand-roll the command dispatch."""
        tools = [dict(SERVER_TOOLS["memory"])] + (extra_tools or [])
        betas = [CONTEXT_MANAGEMENT_BETA] if use_context_management else []
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        turn = 0

        while turn < max_turns:
            payload: dict = {
                "model":      self.model,
                "max_tokens": self.max_tokens,
                "messages":   messages,
                "tools":      tools,
            }
            if system:
                payload["system"] = system
            if use_context_management:
                payload["context_management"] = build_context_management()

            headers = {
                "Content-Type":      "application/json",
                "x-api-key":         self.api_key,
                "anthropic-version": "2023-06-01",
            }
            if betas:
                headers["anthropic-beta"] = ",".join(sorted(set(betas)))
            req = urllib.request.Request(
                self.ENDPOINT, data=json.dumps(payload).encode(),
                headers=headers, method="POST",
            )
            try:
                data = self._call(req)
            except AICoderError as e:
                return f"[API ERROR {getattr(e, 'status_code', '')}] {e.message}"

            stop_reason = data.get("stop_reason", "")
            content     = data.get("content", [])
            messages.append({"role": "assistant", "content": content})

            if stop_reason == "end_turn":
                return "".join(b.get("text", "") for b in content if b.get("type") == "text")
            if stop_reason != "tool_use":
                return f"[UNEXPECTED stop_reason={stop_reason}]"

            tool_results = []
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                if verbose:
                    print(f"\033[90m  [memory:{block['input'].get('command')}] "
                          f"{block['input'].get('path', '')}\033[0m")
                result = memory.handle(block.get("input", {}))
                tool_results.append({
                    "type": "tool_result", "tool_use_id": block["id"], "content": str(result),
                })
            messages.append({"role": "user", "content": tool_results})
            turn += 1

        return "[MAX TURNS REACHED]"


# ── Pre-built tool examples ────────────────────────────────────────────────

def build_code_tools_registry() -> ToolRegistry:
    """Example registry with useful coding tools."""
    reg = ToolRegistry()

    def run_python(code: str) -> str:
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=30
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        if err:
            return f"STDOUT:\n{out}\nSTDERR:\n{err}" if out else f"ERROR:\n{err}"
        return out or "(no output)"

    def read_file(path: str) -> str:
        try:
            with open(path) as f:
                return f.read()
        except Exception as e:
            return f"[ERROR] {e}"

    def write_file(path: str, content: str) -> str:
        try:
            with open(path, "w") as f:
                f.write(content)
            return f"Written {len(content)} chars to {path}"
        except Exception as e:
            return f"[ERROR] {e}"

    def list_files(directory: str = ".") -> str:
        import os
        try:
            return "\n".join(sorted(os.listdir(directory)))
        except Exception as e:
            return f"[ERROR] {e}"

    reg.register("run_python", "Execute Python code and return output",
        {"type": "object", "properties": {"code": {"type": "string", "description": "Python code to execute"}},
         "required": ["code"]}, run_python)

    reg.register("read_file", "Read a file from disk",
        {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        read_file)

    reg.register("write_file", "Write content to a file",
        {"type": "object", "properties": {
            "path":    {"type": "string"},
            "content": {"type": "string"}
        }, "required": ["path", "content"]}, write_file)

    reg.register("list_files", "List files in a directory",
        {"type": "object", "properties": {"directory": {"type": "string", "default": "."}},
         "required": []}, list_files)

    return reg


# ── CLI entry points ───────────────────────────────────────────────────────

def cmd_tool_agent(prompt: str, api_key: str, model: str,
                   system: Optional[str] = None, max_turns: int = 10):
    """Run agentic tool loop with code tools."""
    print(f"\033[94mℹ Agentic tool runner | max_turns={max_turns}\033[0m\n")
    tc  = ToolCoder(api_key=api_key, model=model)
    reg = build_code_tools_registry()
    result = tc.run_agent(prompt, reg, system=system, max_turns=max_turns)
    print(result)
    return result


def cmd_server_tool(prompt: str, tools: list[str], api_key: str, model: str,
                    use_context_management: bool = False,
                    use_compaction: bool = False,
                    task_budget_tokens: Optional[int] = None,
                    use_ptc: bool = False,
                    extra_tool_defs: Optional[list[dict]] = None):
    """Call with Anthropic server tools. use_compaction and
    task_budget_tokens are independent of use_context_management — compaction
    rides inside the same context_management payload as clear_tool_uses, but
    either can be enabled alone. use_ptc marks any extra_tool_defs (e.g. from
    --tool-file) as callable from code_execution via allowed_callers; it's a
    no-op unless "code_execution" is also in tools."""
    print(f"\033[94mℹ Server tools: {', '.join(tools)}\033[0m\n")
    tc = ToolCoder(api_key=api_key, model=model)
    cm = None
    if use_context_management or use_compaction:
        cm = build_context_management(
            clear_tool_uses=use_context_management,
            compact=use_compaction,
        )
    tb = build_task_budget(task_budget_tokens) if task_budget_tokens else None

    extra_tools = []
    for t in (extra_tool_defs or []):
        if use_ptc and "code_execution" in tools:
            t = with_allowed_callers(t)
        extra_tools.append(t)

    result = tc.generate_with_server_tools(
        prompt, tools, context_management=cm, task_budget=tb,
        extra_tools=extra_tools or None,
    )
    print(result)
    return result


def cmd_memory_agent(prompt: str, api_key: str, model: str,
                     memory_dir: str = "~/.ai-coder/memory", max_turns: int = 10):
    """Run an agent loop backed by the native memory tool."""
    print(f"\033[94mℹ Memory-tool agent | dir={memory_dir}\033[0m\n")
    tc     = ToolCoder(api_key=api_key, model=model)
    memory = MemoryToolHandler(base_dir=memory_dir)
    result = tc.run_agent_with_memory(prompt, memory, max_turns=max_turns)
    print(result)
    return result


def cmd_list_server_tools():
    print("\nAvailable server tools:")
    descs = {
        "web_search":     "Search the web for real-time information (GA)",
        "web_fetch":      "Fetch and read a specific URL (GA)",
        "code_execution": "Execute Python/bash in a secure sandbox (GA, code_execution_20260120 "
                           "— minimum version for programmatic tool calling)",
        "bash":           "Run bash commands (computer use)",
        "text_editor":    "Read and edit files (computer use)",
        "computer_use":   "Control a virtual desktop — version auto-selected per model, "
                           "see computer_use_tool_for_model()",
        "memory":         "Persistent file-based memory across conversations (GA)",
        "tool_search":    "On-demand tool discovery for large tool libraries (beta)",
    }
    for name, desc in descs.items():
        beta = SERVER_TOOL_BETAS.get(name)
        tag = f" [beta: {beta}]" if beta else ""
        tool_type = SERVER_TOOLS.get(name, {}).get("type", "")
        retired = check_retired_tool_version(tool_type)
        if retired:
            tag += f" [note: newer version {retired['replacement']} available — {retired['notes']}]"
        print(f"  {name:<18} — {desc}{tag}")
    print("\n  Also available on custom tool definitions (--tool-file), not server tools:")
    print("    input_examples   — Tool Use Examples, worked examples of a correct call.")
    print(f"                       Use with_input_examples(). [beta: {ADVANCED_TOOL_USE_BETA}]")
    print("    allowed_callers  — Programmatic Tool Calling: callable from code_execution")
    print("                       instead of one round-trip per call. Use")
    print(f"                       with_allowed_callers(). [beta: {ADVANCED_TOOL_USE_BETA}]")
    print("\n  Context/budget controls, not tools but combine with any of the above:")
    print("    context_management compact edit — server-side conversation summarization.")
    print(f"                       Use build_context_management(compact=True). [beta: {COMPACTION_BETA}]")
    print("    task_budget        — advisory token countdown for a full agentic loop.")
    print(f"                       Use build_task_budget(). [beta: {TASK_BUDGET_BETA}, "
          f"models: {sorted(TASK_BUDGET_MODELS)}]")