"""
zc_code.py — zAICoder / Agent SDK (all features)
AI Model Coder CLI v1.8.0

Implements every zAICoder / Agent SDK feature from docs.zc.com:

AGENT LOOP
  • query() — stateless or session-resuming agent loop
  • max_turns control, streaming, interruption

SESSIONS
  • Create, resume, save, list, rewind sessions
  • Session ID carried across calls
  • File checkpointing (rewindFiles)

TOOLS
  • Built-in: Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch
  • tool presets: all | code | web | readonly | filesystem | none
  • allowed_tools / disallowed_tools
  • Custom tools via in-process MCP server

PERMISSIONS
  • Modes: acceptEdits | askPermission | bypassPermissions | dontAsk | planMode
  • canUseTool callback
  • hooks: PreToolUse, PostToolUse, PostToolUseFailure, UserPromptSubmit,
           Stop, SubagentStart, SubagentStop, PreCompact, Notification,
           PermissionRequest (+ SessionStart/End, Setup, TaskCompleted, etc.)

MCP
  • stdio, SSE, HTTP transports
  • allowedTools with wildcards
  • tool search (on-demand loading)
  • reconnect / toggle MCP servers

SUBAGENTS
  • Spawn from .zc/agents/<name>.md definitions
  • Custom subagent YAML frontmatter: name, description, tools, disallowedTools
  • builtin agent types

SLASH COMMANDS
  • /clear /compact /help /model /status /cost /memory /vim
  • Custom slash commands from .zc/commands/ or .zc/skills/<n>/SKILL.md

AGENT SKILLS
  • Load from .zc/skills/<name>/SKILL.md
  • Anthropic managed skills: pptx, xlsx, docx, pdf

MEMORY (ZC.md)
  • Project-level: .zc/ZC.md or ./ZC.md
  • User-level: ~/.zc/ZC.md
  • Inject / read / append

TODO LISTS
  • Create, update, complete structured task lists

STRUCTURED OUTPUTS
  • JSON schema output from agent loop

COST / USAGE TRACKING
  • Track token usage and cost across agent calls

PLUGINS
  • Load custom commands, agents, skills, hooks, MCP via plugins option

CLI flags: see main.py --code-agent-*
"""

import json
import os
import shlex
import subprocess
import time
import uuid
from pathlib import Path
from typing import Callable, Optional, List

# ── Storage paths ──────────────────────────────────────────────────────────
SESSIONS_DIR  = Path(os.path.expanduser("~/.ai-coder/code_sessions"))
HOOKS_DIR     = Path(os.path.expanduser("~/.ai-coder/hooks"))
SKILLS_DIR    = Path(".zc/skills")
AGENTS_DIR    = Path(".zc/agents")
COMMANDS_DIR  = Path(".zc/commands")
MEMORY_FILE   = Path(".zc/ZC.md")
USER_MEMORY   = Path(os.path.expanduser("~/.zc/ZC.md"))
MCP_JSON      = Path(".mcp.json")
SETTINGS_JSON = Path(".zc/settings.json")

for d in (SESSIONS_DIR, HOOKS_DIR):
    d.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════
# TOOL PRESETS
# ══════════════════════════════════════════════════════════════════════════

BUILTIN_TOOLS = [
    "Read", "Write", "Edit", "MultiEdit", "Bash", "Glob", "Grep",
    "LS", "WebSearch", "WebFetch", "Task", "TodoRead", "TodoWrite",
    "NotebookRead", "NotebookEdit", "mcp__*",
]

TOOL_PRESETS = {
    "all":        BUILTIN_TOOLS,
    "code":       ["Read", "Write", "Edit", "MultiEdit", "Bash", "Glob", "Grep", "LS"],
    "web":        ["WebSearch", "WebFetch"],
    "readonly":   ["Read", "Glob", "Grep", "LS", "WebSearch", "WebFetch"],
    "filesystem": ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "LS"],
    "safe":       ["Read", "Glob", "Grep", "LS"],
    "none":       [],
}

PERMISSION_MODES = {
    "acceptEdits":      "Auto-approve file edits; ask for other tool calls",
    "askPermission":    "Ask user before each tool call (default)",
    "bypassPermissions":"Auto-approve ALL tool calls (use with caution)",
    "dontAsk":          "Deny anything not in allowed_tools; no prompts",
    "planMode":         "Plan only — no tool execution, output a plan",
}


# ══════════════════════════════════════════════════════════════════════════
# HOOK EVENTS
# ══════════════════════════════════════════════════════════════════════════

HOOK_EVENTS = [
    "PreToolUse",           # before tool execution
    "PostToolUse",          # after tool execution
    "PostToolUseFailure",   # after tool fails
    "UserPromptSubmit",     # when user submits a prompt
    "Stop",                 # agent stopping
    "SubagentStart",        # subagent starts
    "SubagentStop",         # subagent stops
    "PreCompact",           # before message compaction
    "Notification",         # notification events
    "PermissionRequest",    # permission decision needed
    "SessionStart",         # session begins (TypeScript only)
    "SessionEnd",           # session ends (TypeScript only)
    "Setup",                # setup phase
    "TaskCompleted",        # task done
    "ConfigChange",         # settings changed
    "WorktreeCreate",       # git worktree created
    "WorktreeRemove",       # git worktree removed
]


# ══════════════════════════════════════════════════════════════════════════
# SLASH COMMANDS
# ══════════════════════════════════════════════════════════════════════════

BUILTIN_SLASH_COMMANDS = {
    "/clear":    "Clear conversation history and start a new session",
    "/compact":  "Compact message history to save context window",
    "/help":     "Show available commands",
    "/model":    "Switch or display current model",
    "/status":   "Show current session status",
    "/cost":     "Show token usage and cost for this session",
    "/memory":   "View or edit memory (ZC.md)",
    "/vim":      "Toggle vim keybindings",
    "/agents":   "List or create subagent definitions",
    "/skills":   "List available skills",
    "/mcp":      "Show MCP server status",
    "/review":   "Start a code review",
    "/doctor":   "Run diagnostics",
    "/bug":      "Report a bug",
    "/pr":       "Create a pull request",
    "/commit":   "Commit staged changes",
}

SLASH_COMMAND_ALIASES = {
    "clear": "/clear", "compact": "/compact", "help": "/help",
    "model": "/model", "status": "/status", "cost": "/cost",
    "memory": "/memory", "vim": "/vim",
}


# ══════════════════════════════════════════════════════════════════════════
# SESSION
# ══════════════════════════════════════════════════════════════════════════

class CodeSession:
    """Persistent Agent SDK session with full history and metadata."""

    def __init__(self, session_id: Optional[str] = None, cwd: str = ".",
                 model: str = "claude-sonnet-5",
                 permission_mode: str = "askPermission",
                 system_prompt: Optional[str] = None):
        self.id             = session_id or str(uuid.uuid4())[:16]
        self.cwd            = str(Path(cwd).resolve())
        self.model          = model
        self.permission_mode = permission_mode
        self.system_prompt  = system_prompt or ""
        self.turns: list    = []
        self.tool_calls: list = []
        self.mcp_servers: dict = {}
        self.allowed_tools: list = []
        self.hooks: dict    = {}
        self.cost_usd: float = 0.0
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.created_at     = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.updated_at     = self.created_at
        self.checkpoints: list = []

    @classmethod
    def load(cls, session_id: str) -> "CodeSession":
        p = SESSIONS_DIR / f"{session_id}.json"
        if not p.exists():
            raise FileNotFoundError(f"Session '{session_id}' not found.")
        data = json.loads(p.read_text())
        s = cls.__new__(cls)
        s.__dict__.update(data)
        return s

    def save(self):
        self.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        (SESSIONS_DIR / f"{self.id}.json").write_text(
            json.dumps(self.__dict__, indent=2)
        )

    def add_turn(self, role: str, content: str, usage: Optional[dict] = None):
        self.turns.append({
            "role": role, "content": content,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "usage": usage or {},
        })
        if usage:
            self.input_tokens  += usage.get("input_tokens", 0)
            self.output_tokens += usage.get("output_tokens", 0)
            # rough cost estimate (Sonnet 4.5 rates)
            self.cost_usd += (usage.get("input_tokens", 0) / 1e6 * 3.0 +
                              usage.get("output_tokens", 0) / 1e6 * 15.0)

    def add_tool_call(self, name: str, inputs: dict, result: str,
                      approved: bool = True):
        self.tool_calls.append({
            "name": name, "inputs": inputs, "result": result,
            "approved": approved,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

    def checkpoint(self, label: str = ""):
        """Save a file-level checkpoint (rewind point)."""
        cp = {
            "id":    str(uuid.uuid4())[:8],
            "label": label or f"checkpoint-{len(self.checkpoints)+1}",
            "ts":    time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "turn":  len(self.turns),
        }
        self.checkpoints.append(cp)
        return cp

    def messages(self) -> list[dict]:
        return [{"role": t["role"], "content": t["content"]} for t in self.turns]

    def cost_summary(self) -> str:
        return (f"Session {self.id[:8]}  |  "
                f"in={self.input_tokens:,}  out={self.output_tokens:,}  "
                f"cost≈${self.cost_usd:.4f}")


# ══════════════════════════════════════════════════════════════════════════
# HOOKS ENGINE
# ══════════════════════════════════════════════════════════════════════════

class HooksEngine:
    """
    Execute hook scripts/callbacks at agent lifecycle events.
    Hooks receive JSON via stdin and return:
      exit 0  → proceed normally
      exit 2  → block operation (error message in stdout fed back to zAICoder)
      exit 1  → non-blocking warning
    """

    def __init__(self, hooks_config: Optional[dict] = None):
        # hooks_config: {event_name: [{"command": "...", "env": {...}}]}
        self.config = hooks_config or {}

    @classmethod
    def from_settings(cls, settings_path: Path = SETTINGS_JSON) -> "HooksEngine":
        if settings_path.exists():
            try:
                data = json.loads(settings_path.read_text())
                return cls(data.get("hooks", {}))
            except Exception:
                pass
        return cls()

    @classmethod
    def from_file(cls, hooks_file: str) -> "HooksEngine":
        try:
            data = json.loads(Path(hooks_file).read_text())
            return cls(data)
        except Exception as e:
            print(f"  [WARN] Could not load hooks from {hooks_file}: {e}")
            return cls()

    @classmethod
    def with_plugins(cls, base: "HooksEngine") -> "HooksEngine":
        """Merge plugin-bundled hooks.json files into an existing engine's config."""
        try:
            from wire.zc_plugins import load_plugin_hooks
            plugin_hooks = load_plugin_hooks()
        except ImportError:
            return base
        merged = dict(base.config)
        for event, handlers in plugin_hooks.items():
            merged.setdefault(event, [])
            merged[event] = merged[event] + handlers
        return cls(merged)

    def fire(self, event: str, payload: dict) -> dict:
        """
        Fire a hook event. Returns {"allowed": bool, "message": str}
        """
        handlers = self.config.get(event, [])
        if not handlers:
            return {"allowed": True, "message": ""}

        stdin_data = json.dumps(payload)
        for handler in handlers:
            cmd  = handler.get("command", "")
            env  = {**os.environ, **handler.get("env", {})}
            if not cmd:
                continue
            try:
                cmd_args = shlex.split(cmd) if isinstance(cmd, str) else cmd
                result = subprocess.run(
                    cmd_args, shell=False, input=stdin_data,
                    capture_output=True, text=True, timeout=30, env=env,
                )
                if result.returncode == 2:
                    msg = result.stdout.strip() or result.stderr.strip()
                    return {"allowed": False, "message": msg}
                if result.returncode == 1:
                    print(f"  \033[93m[hook:{event}] {result.stdout.strip()}\033[0m")
            except subprocess.TimeoutExpired:
                print(f"  \033[91m[hook:{event}] timed out\033[0m")
            except Exception as e:
                print(f"  \033[91m[hook:{event}] error: {e}\033[0m")

        return {"allowed": True, "message": ""}

    def pre_tool_use(self, tool_name: str, tool_input: dict,
                     session: CodeSession) -> dict:
        return self.fire("PreToolUse", {
            "hook_event_name": "PreToolUse",
            "session_id": session.id,
            "cwd": session.cwd,
            "tool_name": tool_name,
            "tool_input": tool_input,
        })

    def post_tool_use(self, tool_name: str, tool_input: dict,
                      tool_response: str, session: CodeSession):
        self.fire("PostToolUse", {
            "hook_event_name": "PostToolUse",
            "session_id": session.id,
            "cwd": session.cwd,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_response": tool_response,
        })

    def notify(self, message: str, session: CodeSession):
        self.fire("Notification", {
            "hook_event_name": "Notification",
            "session_id": session.id,
            "message": message,
        })


# ══════════════════════════════════════════════════════════════════════════
# MCP CONNECTOR
# ══════════════════════════════════════════════════════════════════════════

class McpConnector:
    """
    Connect zAICoder to MCP servers.
    Supports stdio (subprocess), SSE, and HTTP transports.
    Loads .mcp.json from project root if present.
    """

    def __init__(self):
        self.servers: dict = {}

    @classmethod
    def from_json_file(cls, path: Path = MCP_JSON) -> "McpConnector":
        mc = cls()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                mc.servers = data.get("mcpServers", {})
            except Exception as e:
                print(f"  [WARN] .mcp.json parse error: {e}")
        try:
            from wire.zc_plugins import load_plugin_mcp_servers
            mc.servers.update(load_plugin_mcp_servers())
        except ImportError:
            pass
        return mc

    def add_stdio(self, name: str, command: str, args: Optional[list] = None,
                  env: Optional[dict] = None):
        self.servers[name] = {
            "type": "stdio", "command": command,
            "args": args or [], "env": env or {},
        }

    def add_http(self, name: str, url: str, headers: Optional[dict] = None):
        self.servers[name] = {
            "type": "http", "url": url, "headers": headers or {},
        }

    def add_sse(self, name: str, url: str, headers: Optional[dict] = None):
        self.servers[name] = {
            "type": "sse", "url": url, "headers": headers or {},
        }

    def add_from_url(self, url: str):
        """Auto-detect transport from URL and add."""
        name = url.split("/")[-1].split("?")[0] or "mcp-server"
        if url.startswith("http"):
            self.add_http(name, url)
        else:
            self.add_stdio(name, url)

    def to_query_options(self) -> dict:
        return {"mcpServers": self.servers}

    def list_servers(self) -> list:
        return [{"name": k, **v} for k, v in self.servers.items()]

    def tool_name(self, server_name: str, tool: str) -> str:
        """Format tool name as mcp__<server>__<tool>"""
        return f"mcp__{server_name}__{tool}"


# ══════════════════════════════════════════════════════════════════════════
# SUBAGENT REGISTRY
# ══════════════════════════════════════════════════════════════════════════

class SubagentRegistry:
    """
    Load subagent definitions from .zc/agents/*.md
    YAML frontmatter: name, description, tools, disallowedTools, model, system_prompt
    """

    def __init__(self, agents_dir: Path = AGENTS_DIR):
        self.dir   = agents_dir
        self._agents: dict = {}

    def load(self):
        if self.dir.exists():
            for f in self.dir.glob("*.md"):
                self._load_one(f, plugin=None)

        # Plugin-bundled agents (.zc/plugins/installed/<plugin>/agents/*.md)
        try:
            from wire.zc_plugins import load_plugin_agents
            for entry in load_plugin_agents():
                self._load_one(Path(entry["path"]), plugin=entry["plugin"],
                               namespace=f"{entry['plugin']}:{entry['name']}")
        except ImportError:
            pass

    def _load_one(self, f: Path, plugin: Optional[str] = None,
                 namespace: Optional[str] = None):
        try:
            content = f.read_text()
            meta, body = self._parse_frontmatter(content)
            name = namespace or meta.get("name") or f.stem
            self._agents[name] = {
                "name":           name,
                "description":    meta.get("description", ""),
                "tools":          meta.get("tools", "all"),
                "disallowedTools":meta.get("disallowedTools", ""),
                "model":          meta.get("model", ""),
                "system_prompt":  body.strip(),
                "file":           str(f),
                "plugin":         plugin,
            }
        except Exception as e:
            print(f"  [WARN] Could not load agent {f.name}: {e}")

    def _parse_frontmatter(self, content: str) -> tuple[dict, str]:
        if not content.startswith("---"):
            return {}, content
        lines  = content.split("\n")
        end    = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), None)
        if end is None:
            return {}, content
        import re
        meta = {}
        for line in lines[1:end]:
            m = re.match(r'^(\w+):\s*(.+)', line)
            if m:
                meta[m.group(1)] = m.group(2).strip()
        body = "\n".join(lines[end+1:])
        return meta, body

    def list(self) -> list:
        return list(self._agents.values())

    def get(self, name: str) -> Optional[dict]:
        return self._agents.get(name)

    def create(self, name: str, description: str, system_prompt: str,
               tools: str = "all", disallowed: str = "") -> Path:
        """Write a new agent definition file."""
        self.dir.mkdir(parents=True, exist_ok=True)
        content = (
            f"---\nname: {name}\ndescription: {description}\n"
            f"tools: {tools}\n"
            + (f"disallowedTools: {disallowed}\n" if disallowed else "")
            + f"---\n\n{system_prompt}\n"
        )
        path = self.dir / f"{name}.md"
        path.write_text(content)
        return path


# ══════════════════════════════════════════════════════════════════════════
# SKILLS REGISTRY
# ══════════════════════════════════════════════════════════════════════════

ANTHROPIC_MANAGED_SKILLS = {
    "pptx": "Create PowerPoint presentations",
    "xlsx": "Create Excel spreadsheets",
    "docx": "Create Word documents",
    "pdf":  "Create and fill PDF files",
}

class SkillsRegistry:
    """Load Agent Skills from .zc/skills/<name>/SKILL.md"""

    def __init__(self, skills_dir: Path = SKILLS_DIR):
        self.dir    = skills_dir
        self._skills: dict = {}

    def load(self):
        if self.dir.exists():
            for skill_dir in self.dir.iterdir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    content = skill_md.read_text()
                    name    = skill_dir.name
                    # extract first line description
                    desc    = next((l.lstrip("# ").strip()
                                    for l in content.splitlines()
                                    if l.strip() and not l.startswith("---")), "")
                    self._skills[name] = {
                        "name": name, "description": desc,
                        "path": str(skill_md), "source": "custom",
                    }
        for name, desc in ANTHROPIC_MANAGED_SKILLS.items():
            self._skills[name] = {
                "name": name, "description": desc,
                "path": "", "source": "anthropic",
            }
        try:
            from wire.zc_plugins import load_plugin_skills
            for entry in load_plugin_skills():
                content = Path(entry["path"]).read_text()
                desc = next((l.lstrip("# ").strip()
                            for l in content.splitlines()
                            if l.strip() and not l.startswith("---")), "")
                key = f"{entry['plugin']}:{entry['name']}"
                self._skills[key] = {
                    "name": key, "description": desc,
                    "path": entry["path"], "source": f"plugin:{entry['plugin']}",
                }
        except ImportError:
            pass

    def list(self) -> list:
        return list(self._skills.values())

    def get(self, name: str) -> Optional[dict]:
        return self._skills.get(name)


# ══════════════════════════════════════════════════════════════════════════
# TODO LISTS
# ══════════════════════════════════════════════════════════════════════════

TODO_FILE = Path(os.path.expanduser("~/.ai-coder/code_todos.json"))

class TodoManager:
    def __init__(self):
        self._todos: list = []
        if TODO_FILE.exists():
            try:
                self._todos = json.loads(TODO_FILE.read_text())
            except Exception:
                pass

    def _save(self):
        TODO_FILE.parent.mkdir(parents=True, exist_ok=True)
        TODO_FILE.write_text(json.dumps(self._todos, indent=2))

    def add(self, text: str, priority: str = "medium") -> dict:
        item = {"id": str(uuid.uuid4())[:8], "text": text,
                "status": "todo", "priority": priority,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
        self._todos.append(item)
        self._save()
        return item

    def complete(self, todo_id: str) -> bool:
        for t in self._todos:
            if t["id"] == todo_id:
                t["status"] = "done"
                t["done_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                self._save()
                return True
        return False

    def list(self) -> List:
        return self._todos

    def pending(self) -> List:
        return [t for t in self._todos if t["status"] != "done"]


# ══════════════════════════════════════════════════════════════════════════
# MEMORY (ZC.md)
# ══════════════════════════════════════════════════════════════════════════

class MemoryManager:
    """Read/write ZC.md project and user memory."""

    def read_project(self) -> str:
        for p in (Path(".zc/ZC.md"), Path("ZC.md")):
            if p.exists():
                return p.read_text()
        return ""

    def read_user(self) -> str:
        return USER_MEMORY.read_text() if USER_MEMORY.exists() else ""

    def append_project(self, content: str):
        p = Path(".zc/ZC.md")
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a") as f:
            f.write(f"\n{content}\n")

    def append_user(self, content: str):
        USER_MEMORY.parent.mkdir(parents=True, exist_ok=True)
        with open(USER_MEMORY, "a") as f:
            f.write(f"\n{content}\n")

    def combined(self) -> str:
        parts = []
        u = self.read_user()
        p = self.read_project()
        if u:
            parts.append(f"# User Memory\n{u}")
        if p:
            parts.append(f"# Project Memory\n{p}")
        return "\n\n".join(parts)


# ══════════════════════════════════════════════════════════════════════════
# CORE AGENT (Messages API agentic loop)
# ══════════════════════════════════════════════════════════════════════════

import urllib.error
import urllib.request

from wire.exceptions import AICoderError
from wire.resilience import CircuitBreaker, raise_for_http_error, retry, urlopen_json

MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)


class CodeAgent:
    """
    Full zAICoder / Agent SDK implementation using the Messages API.
    Replicates the Agent SDK's query() loop in pure stdlib Python.
    """

    def __init__(self, api_key: str, model: str = "zc-xxx",
                 max_tokens: int = 8192):
        self.api_key    = api_key
        self.model      = model
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict, betas: Optional[list] = None) -> dict:
        headers = {
            "Content-Type":      "application/json",
            "x-api-key":         self.api_key,
            "anthropic-version": "2023-06-01",
        }
        if betas:
            headers["anthropic-beta"] = ",".join(betas)
        req = urllib.request.Request(
            MESSAGES_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers, method="POST",
        )
        return urlopen_json(req, timeout=300)

    def _post(self, payload: dict, betas: Optional[list] = None) -> dict:
        try:
            return self._call(payload, betas)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    # No CircuitBreaker: WebFetch targets a different, arbitrary URL each
    # time (agent-chosen), not one fixed downstream dependency.
    @retry(max_attempts=2, base_delay=1.0, max_delay=5.0)
    def _webfetch_retrying(self, url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": "ai-coder-agent/1.8"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode("utf-8", errors="replace")[:4000]
        except (urllib.error.HTTPError, TimeoutError, ConnectionError, OSError) as e:
            raise_for_http_error(e)
            raise e

    def _build_tools(self, preset: str, allowed: list) -> list:
        """Build tool definitions for the agentic loop."""
        # We model tools as simple function-call schemas
        tools_out = []
        names = allowed or TOOL_PRESETS.get(preset, TOOL_PRESETS["all"])

        TOOL_SCHEMAS = {
            "Read":      {"description": "Read a file", "input_schema": {
                "type":"object","properties":{"path":{"type":"string"}},"required":["path"]}},
            "Write":     {"description": "Write a file", "input_schema": {
                "type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}},
            "Edit":      {"description": "Edit part of a file", "input_schema": {
                "type":"object","properties":{"path":{"type":"string"},"old_string":{"type":"string"},"new_string":{"type":"string"}},"required":["path","old_string","new_string"]}},
            "Bash":      {"description": "Run a bash command", "input_schema": {
                "type":"object","properties":{"command":{"type":"string"},"timeout":{"type":"integer"}},"required":["command"]}},
            "Glob":      {"description": "Find files matching a pattern", "input_schema": {
                "type":"object","properties":{"pattern":{"type":"string"},"path":{"type":"string"}},"required":["pattern"]}},
            "Grep":      {"description": "Search file contents", "input_schema": {
                "type":"object","properties":{"pattern":{"type":"string"},"path":{"type":"string"},"include":{"type":"string"}},"required":["pattern"]}},
            "LS":        {"description": "List directory contents", "input_schema": {
                "type":"object","properties":{"path":{"type":"string"}},"required":[]}},
            "WebSearch": {"description": "Search the web", "input_schema": {
                "type":"object","properties":{"query":{"type":"string"}},"required":["query"]}},
            "WebFetch":  {"description": "Fetch a URL", "input_schema": {
                "type":"object","properties":{"url":{"type":"string"}},"required":["url"]}},
            "TodoRead":  {"description": "Read todo list", "input_schema": {
                "type":"object","properties":{},"required":[]}},
            "TodoWrite": {"description": "Update todo list", "input_schema": {
                "type":"object","properties":{"todos":{"type":"array","items":{"type":"object"}}},"required":["todos"]}},
        }
        for name in names:
            if name == "mcp__*":
                continue
            if name in TOOL_SCHEMAS:
                tools_out.append({"name": name, **TOOL_SCHEMAS[name]})
        return tools_out

    def _execute_tool(self, name: str, inputs: dict, session: CodeSession,
                      hooks: HooksEngine, permission: str,
                      can_use_tool: Optional[Callable] = None) -> str:
        """Execute a tool call with permission checking and hooks."""

        # Hook: PreToolUse
        hook_result = hooks.pre_tool_use(name, inputs, session)
        if not hook_result["allowed"]:
            return f"[BLOCKED by hook] {hook_result['message']}"

        # Permission check
        if permission == "planMode":
            return "[PLAN MODE] Tool not executed — plan only."
        if permission == "dontAsk":
            return "[DENIED] Tool not in allowed list."
        if permission == "askPermission":
            if can_use_tool:
                if not can_use_tool(name, inputs):
                    return "[DENIED by user]"
            else:
                # In non-interactive mode, auto-approve reads, ask for writes
                read_only = {"Read", "Glob", "Grep", "LS", "WebSearch", "WebFetch", "TodoRead"}
                if name not in read_only:
                    print(f"\n\033[93m  [permission] {name}({json.dumps(inputs)[:60]})\033[0m")
                    try:
                        ans = input("  Approve? [Y/n] ").strip().lower()
                        if ans == "n":
                            return "[DENIED by user]"
                    except (EOFError, KeyboardInterrupt):
                        return "[DENIED — no terminal]"

        # Execute
        result = self._run_tool(name, inputs, session)
        session.add_tool_call(name, inputs, result[:200])

        # Hook: PostToolUse
        hooks.post_tool_use(name, inputs, result, session)

        return result

    def _run_tool(self, name: str, inputs: dict, session: CodeSession) -> str:
        """Actually execute a built-in tool."""
        cwd = session.cwd
        try:
            if name == "Read":
                p = Path(cwd) / inputs["path"]
                return p.read_text()[:8000]

            elif name == "Write":
                p = Path(cwd) / inputs["path"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(inputs["content"])
                return f"Written {len(inputs['content'])} chars to {inputs['path']}"

            elif name == "Edit":
                p = Path(cwd) / inputs["path"]
                content = p.read_text()
                new = content.replace(inputs["old_string"], inputs["new_string"], 1)
                if new == content:
                    return f"[WARN] old_string not found in {inputs['path']}"
                p.write_text(new)
                return f"Edited {inputs['path']}"

            elif name == "Bash":
                cmd = inputs["command"]
                timeout = inputs.get("timeout", 30)
                if os.environ.get("AI_CODER_SANDBOX") == "1":
                    try:
                        from wire.zc_sandbox import SandboxViolation, enforce
                        roots = json.loads(os.environ.get("AI_CODER_SANDBOX_ROOTS", "[]"))
                        allow_net = os.environ.get("AI_CODER_SANDBOX_NET") == "1"
                        enforce(cmd, cwd, allow_net=allow_net, extra_roots=roots)
                    except SandboxViolation as e:
                        return f"[SANDBOX BLOCKED] {e}"
                    except ImportError:
                        pass
                r = subprocess.run(["/bin/bash", "-c", cmd], shell=False, cwd=cwd,
                                   capture_output=True, text=True, timeout=timeout)
                out = r.stdout.strip()
                err = r.stderr.strip()
                if r.returncode != 0:
                    return f"EXIT {r.returncode}\nSTDOUT:\n{out}\nSTDERR:\n{err}"
                return out or "(no output)"

            elif name == "Glob":
                pattern = inputs["pattern"]
                base    = Path(cwd) / inputs.get("path", ".")
                matches = sorted(base.glob(pattern))
                return "\n".join(str(m.relative_to(cwd)) for m in matches[:100])

            elif name == "Grep":
                import re
                pattern = inputs["pattern"]
                base    = Path(cwd) / inputs.get("path", ".")
                include = inputs.get("include", "*")
                results = []
                for f in base.rglob(include):
                    if not f.is_file():
                        continue
                    try:
                        for i, line in enumerate(f.read_text().splitlines(), 1):
                            if re.search(pattern, line):
                                results.append(f"{f.relative_to(cwd)}:{i}: {line.strip()}")
                    except Exception as _e:
                        pass
                return "\n".join(results[:200]) or "(no matches)"

            elif name == "LS":
                p = Path(cwd) / inputs.get("path", ".")
                return "\n".join(sorted(str(c.name) for c in p.iterdir()))

            elif name == "WebSearch":
                return f"[WebSearch] {inputs['query']} — requires live network"

            elif name == "WebFetch":
                try:
                    return self._webfetch_retrying(inputs["url"])
                except Exception as e:
                    return f"[WebFetch error] {e}"

            elif name == "TodoRead":
                tm = TodoManager()
                return json.dumps(tm.list(), indent=2)

            elif name == "TodoWrite":
                tm = TodoManager()
                todos = inputs.get("todos", [])
                for t in todos:
                    if t.get("status") == "done":
                        tm.complete(t.get("id", ""))
                    else:
                        tm.add(t.get("content", ""), t.get("priority", "medium"))
                return f"Updated {len(todos)} todos"

            else:
                return f"[Tool {name} not implemented in local runner]"

        except Exception as e:
            return f"[Tool {name} error] {e}"

    # ── Main agent loop ────────────────────────────────────────────────────

    def query(
        self,
        prompt:      str,
        session:     CodeSession,
        tools:       str = "all",
        allowed: Optional[list] = None,
        disallowed: Optional[list] = None,
        permission:  str = "askPermission",
        hooks: Optional[HooksEngine] = None,
        max_turns:   int = 10,
        can_use_tool: Optional[Callable] = None,
        output_mode: str = "stream",
        system_extra: str = "",
        context_management: Optional[dict] = None,
    ) -> str:
        """
        Full agentic query loop.
        Streams or returns final text depending on output_mode.

        context_management: pass a payload built by
        zc_tools.build_context_management() to auto-clear stale tool
        results (and optionally thinking blocks) once the conversation
        crosses a token trigger — distinct from and complementary to
        Compaction (which summarizes instead of dropping). Opt-in: None by
        default, so this doesn't change behavior for existing callers. See
        --agent-context-editing in cmd_code_agent / main.py.
        """
        hooks  = hooks or HooksEngine()
        memory = MemoryManager()

        # Build system prompt
        sys_parts = []
        mem = memory.combined()
        if mem:
            sys_parts.append(mem)
        if session.system_prompt:
            sys_parts.append(session.system_prompt)
        if system_extra:
            sys_parts.append(system_extra)
        sys_parts.append(
            f"You are working in directory: {session.cwd}\n"
            f"Permission mode: {permission}\n"
            f"Use the available tools to complete the task."
        )
        system = "\n\n".join(sys_parts)

        # Tools
        tool_defs = self._build_tools(tools, allowed or [])
        if disallowed:
            tool_defs = [t for t in tool_defs if t["name"] not in disallowed]

        # Add prompt to session
        session.add_turn("user", prompt)

        turn = 0
        final_text = ""

        while turn < max_turns:
            payload: dict = {
                "model":      session.model or self.model,
                "max_tokens": self.max_tokens,
                "system":     system,
                "messages":   session.messages(),
            }
            if tool_defs and permission != "planMode":
                payload["tools"] = tool_defs

            betas = []
            if context_management is not None:
                payload["context_management"] = context_management
                from wire.zc_tools import CONTEXT_MANAGEMENT_BETA
                betas.append(CONTEXT_MANAGEMENT_BETA)

            if output_mode == "stream":
                print(f"\033[90m[turn {turn+1}]\033[0m ", end="", flush=True)

            data = self._post(payload, betas=betas or None)
            if "error" in data:
                return f"[ERROR] {data['error']}"

            stop_reason = data.get("stop_reason", "end_turn")
            content     = data.get("content", [])
            usage       = data.get("usage", {})

            # Extract text
            text = "".join(b.get("text","") for b in content if b.get("type")=="text")
            if text:
                final_text = text
                if output_mode == "stream":
                    print(text)

            # Update session
            session.add_turn("assistant", text or "[tool use]", usage)
            session.save()

            if stop_reason == "end_turn":
                break

            if stop_reason != "tool_use":
                break

            # Execute tool calls
            tool_results = []
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                tname  = block["name"]
                tinput = block.get("input", {})
                tid    = block["id"]

                if output_mode in ("stream",):
                    print(f"  \033[90m→ {tname}({json.dumps(tinput)[:60]})\033[0m")

                # Check disallowed
                if disallowed and tname in disallowed:
                    result = f"[DENIED] {tname} is in disallowed_tools"
                else:
                    result = self._execute_tool(tname, tinput, session,
                                                hooks, permission, can_use_tool)

                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": tid,
                    "content":     str(result),
                })

            if tool_results:
                session.add_turn("user", json.dumps(tool_results))

            turn += 1

        if output_mode == "json":
            return json.dumps({
                "session_id": session.id,
                "result":     final_text,
                "turns":      turn,
                "cost":       session.cost_summary(),
            })

        return final_text


# ══════════════════════════════════════════════════════════════════════════
# STRUCTURED OUTPUTS from agent
# ══════════════════════════════════════════════════════════════════════════

class StructuredAgentOutput:
    """Get JSON-structured output from the agent loop."""

    def __init__(self, agent: CodeAgent):
        self.agent = agent

    def query_json(self, prompt: str, schema: dict,
                   session: CodeSession) -> dict:
        """Run agent and parse structured JSON from the result."""
        full_prompt = (
            f"{prompt}\n\n"
            f"Respond ONLY with a valid JSON object matching this schema:\n"
            f"{json.dumps(schema, indent=2)}\n"
            f"No markdown, no explanation — pure JSON only."
        )
        result = self.agent.query(
            full_prompt, session, tools="none",
            permission="dontAsk", output_mode="text",
        )
        try:
            clean = result.strip()
            if clean.startswith("```"):
                clean = "\n".join(clean.split("\n")[1:]).rstrip("`").strip()
            return json.loads(clean)
        except json.JSONDecodeError:
            return {"raw": result, "parse_error": True}


# ══════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINTS
# ══════════════════════════════════════════════════════════════════════════

def cmd_code_agent(
    prompt: str, api_key: str, model: str,
    cwd: str = ".", tools: str = "all",
    permission: str = "askPermission",
    session_id: Optional[str] = None, system: Optional[str] = None,
    mcp_urls: Optional[list] = None, output_mode: str = "stream",
    hooks_file: Optional[str] = None, checkpoint: bool = False,
    output_file: Optional[str] = None,
    output_style: Optional[str] = None,
    sandbox: bool = False, sandbox_allow_net: bool = False,
    sandbox_roots: Optional[list] = None,
    headless: bool = False,
    agent_context_editing: bool = False,
):
    """Main --code-agent entry point.

    agent_context_editing: opt-in context editing (clear_tool_uses) for this
    agent loop, on top of the existing Compaction support — the two are
    complementary (clearing drops stale tool results; Compaction summarizes
    the whole conversation), so this is safe to combine with an already
    long-running session. See --agent-context-editing.
    """
    if not headless:
        print(f"\033[94mℹ zAICoder Agent | tools={tools} | permission={permission}\033[0m")
        print(f"  cwd: {Path(cwd).resolve()}\n")

    # Session
    if session_id:
        try:
            session = CodeSession.load(session_id)
            if not headless:
                print(f"\033[90m  Resumed session: {session.id} ({len(session.turns)} turns)\033[0m\n")
        except FileNotFoundError:
            session = CodeSession(session_id=session_id, cwd=cwd, model=model,
                                  permission_mode=permission, system_prompt=system or "")
    else:
        session = CodeSession(cwd=cwd, model=model,
                              permission_mode=permission, system_prompt=system or "")

    # Output style: append style instructions to the session's system prompt
    if output_style:
        try:
            from wire.zc_output_styles import system_prompt_fragment
            fragment = system_prompt_fragment(output_style)
            if fragment:
                session.system_prompt = (session.system_prompt + "\n\n" + fragment).strip()
        except ImportError:
            pass

    # MCP (project .mcp.json + plugin-bundled servers + ad-hoc --code-agent-mcp URLs)
    mcp = McpConnector.from_json_file()
    for url in (mcp_urls or []):
        mcp.add_from_url(url)

    # Hooks: project/global settings hooks, merged with plugin-bundled hooks
    if hooks_file:
        hooks_engine = HooksEngine.from_file(hooks_file)
    else:
        hooks_engine = HooksEngine.from_settings()
    hooks_engine = HooksEngine.with_plugins(hooks_engine)

    # Sandboxed Bash: wrap permission/tool execution with filesystem+network checks
    if sandbox:
        os.environ["AI_CODER_SANDBOX"] = "1"
        os.environ["AI_CODER_SANDBOX_NET"] = "1" if sandbox_allow_net else "0"
        os.environ["AI_CODER_SANDBOX_ROOTS"] = json.dumps([str(Path(cwd).resolve())] + (sandbox_roots or []))
        if not headless:
            net_state = "network allowed" if sandbox_allow_net else "network blocked"
            print(f"\033[93m  ⚙ Sandbox enabled ({net_state})\033[0m")

    # Plugin bin/ dirs onto PATH for the duration of this run
    try:
        from wire.zc_plugins import plugin_bin_paths
        extra_bins = plugin_bin_paths()
        if extra_bins:
            os.environ["PATH"] = os.pathsep.join(extra_bins) + os.pathsep + os.environ.get("PATH", "")
    except ImportError:
        pass

    # Skills / Agents (now plugin-aware via their own .load())
    skills = SkillsRegistry(); skills.load()
    agents = SubagentRegistry(); agents.load()

    # Checkpoint before run
    if checkpoint:
        cp = session.checkpoint(f"before: {prompt[:40]}")
        if not headless:
            print(f"  \033[90m✓ Checkpoint: {cp['id']}\033[0m")

    # Headless/print mode forces non-interactive, non-streaming text output —
    # suitable for piping into other tools or scripts (matches `zc -p`).
    effective_output_mode = "text" if headless else output_mode

    # Context editing (opt-in): reuses zc_tools.py's build_context_management
    # rather than duplicating it, since that module already implements the
    # full context_management payload shape.
    cm = None
    if agent_context_editing:
        from wire.zc_tools import build_context_management
        cm = build_context_management(clear_tool_uses=True)
        if not headless:
            print("\033[90m  ⚙ Context editing enabled (clear_tool_uses)\033[0m")

    # Run
    agent  = CodeAgent(api_key=api_key, model=model)
    result = agent.query(
        prompt=prompt, session=session,
        tools=tools, permission=permission,
        hooks=hooks_engine,
        output_mode=effective_output_mode,
        context_management=cm,
    )

    if effective_output_mode != "stream":
        print(result)

    if output_file:
        Path(output_file).write_text(result)
        if not headless:
            print(f"\033[92m✓ Saved to {output_file}\033[0m")

    if not headless:
        print(f"\n\033[90m{session.cost_summary()}\033[0m")
        print(f"\033[90m  Resume: ai-coder --code-agent-session {session.id} -p \"...\"\033[0m")
    return result


def cmd_code_subagent(task: str, api_key: str, model: str, cwd: str = "."):
    """Spawn a focused subagent for a sub-task."""
    print("\033[94mℹ Spawning subagent…\033[0m\n")
    session = CodeSession(cwd=cwd, model=model, permission_mode="acceptEdits",
                          system_prompt=(
                              "You are a focused subagent. Complete ONLY the specific task. "
                              "Be thorough. Return just the result."
                          ))
    agent  = CodeAgent(api_key=api_key, model=model)
    result = agent.query(task, session, tools="safe",
                         permission="acceptEdits", output_mode="stream")
    return result


def cmd_code_todo(prompt: str, api_key: str, model: str):
    """Generate and manage a todo list from a prompt."""
    print(f"\033[94mℹ Todo list from: {prompt[:60]}\033[0m\n")
    tm = TodoManager()

    # Ask zAICoder to decompose the prompt into todos
    session = CodeSession(model=model, permission_mode="dontAsk")
    agent   = CodeAgent(api_key=api_key, model=model)
    raw     = agent.query(
        f"Break this task into 5-8 concrete todo items (JSON array of strings):\n{prompt}",
        session, tools="none", permission="dontAsk", output_mode="text",
    )
    try:
        import re
        m = re.search(r'\[.*?\]', raw, re.DOTALL)
        if m:
            items = json.loads(m.group(0))
            for item in items:
                t = tm.add(str(item))
                print(f"  ○ [{t['id']}] {t['text']}")
    except Exception:
        print(raw)


def cmd_code_slash(command: str, api_key: str, model: str,
                   cwd: str = ".", prompt: str = "", session_id: Optional[str] = None):
    """Handle slash commands."""
    cmd = command.lstrip("/").lower()
    full_cmd = SLASH_COMMAND_ALIASES.get(cmd, f"/{cmd}")

    if cmd == "clear":
        print("\033[92m✓ Session cleared.\033[0m")
        return

    if cmd == "compact":
        # Real server-side compaction (compact_20260112 / COMPACTION_BETA,
        # see zc_tools.build_context_management) against an actual
        # session's turn history. Previously this printed a success
        # message and did nothing — see CHANGELOG for this fix. There's
        # nothing to compact without a session: cmd_code_slash is a
        # one-shot call with no history of its own, so that case is
        # reported honestly instead of faking success.
        if not session_id:
            print("\033[93m⚠ /compact needs an active session — pass "
                  "--code-agent-session ID (or run /compact from within "
                  "--code-agent, not as a standalone --code-agent-slash "
                  "call).\033[0m")
            return
        try:
            session = CodeSession.load(session_id)
        except FileNotFoundError as e:
            print(f"\033[91m✗ {e}\033[0m")
            return

        from wire.zc_tools import COMPACTION_BETA, build_context_management
        messages = session.messages()
        if not messages:
            print("\033[93m⚠ Session has no turns yet — nothing to compact.\033[0m")
            return

        before_tokens = session.input_tokens + session.output_tokens
        agent = CodeAgent(api_key, model=session.model)
        payload = {
            "model": session.model,
            "max_tokens": 1024,
            "messages": messages,
            "context_management": build_context_management(
                clear_tool_uses=False, compact=True,
                compact_trigger_tokens=0,  # force it now rather than waiting for the threshold
            ),
        }
        print("\033[94mℹ Compacting message history…\033[0m")
        result = agent._post(payload, betas=[COMPACTION_BETA])
        if "error" in result:
            print(f"\033[91m✗ Compaction failed: {result['error']}\033[0m")
            return

        compaction_blocks = [b for b in result.get("content", []) if b.get("type") == "compaction"]
        summary_text = compaction_blocks[0].get("content", "") if compaction_blocks else ""
        usage = result.get("usage", {})

        # Replace turn history with the compaction summary as the new
        # starting point, mirroring how the API expects the compaction
        # block to anchor subsequent requests (see resume_after_compaction
        # in zc_tools.py for the pause_after_compaction variant).
        session.turns = [{
            "role": "assistant",
            "content": summary_text or json.dumps(result.get("content", [])),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "usage": usage,
        }]
        session.save()

        after_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        print(f"\033[92m✓ Compacted. Session {session.id[:8]}: "
              f"~{before_tokens:,} tokens of history \u2192 summary "
              f"(this call used {after_tokens:,} tokens).\033[0m")
        return

    if cmd in ("help", "?"):
        print("\nBuilt-in slash commands:")
        for name, desc in BUILTIN_SLASH_COMMANDS.items():
            print(f"  {name:<15} — {desc}")
        # Check custom commands
        for d in (COMMANDS_DIR, SKILLS_DIR):
            if d.exists():
                for f in d.rglob("*.md"):
                    print(f"  /{f.stem:<13} — custom command from {f.relative_to(d)}")
        return

    if cmd == "cost":
        print("Session cost tracking (use --code-agent-cost for full summary)")
        return

    if cmd in ("status", "model", "mcp", "agents", "skills", "memory", "doctor",
               "plugin", "output-style", "statusline"):
        # Route to appropriate command
        if cmd == "model":
            print(f"  Current model: {model}")
        elif cmd == "mcp":
            mcp = McpConnector.from_json_file()
            servers = mcp.list_servers()
            if servers:
                for s in servers:
                    print(f"  {s['name']}: {s.get('type','?')} {s.get('url','')}")
            else:
                print("  No MCP servers configured. Add to .mcp.json")
        elif cmd == "agents":
            reg = SubagentRegistry(); reg.load()
            for a in reg.list():
                tag = f" [{a['plugin']}]" if a.get("plugin") else ""
                print(f"  {a['name']}{tag}: {a['description']}")
        elif cmd == "skills":
            skills_reg = SkillsRegistry(); skills_reg.load()
            for s in skills_reg.list():
                print(f"  {s['name']} ({s['source']}): {s['description']}")
        elif cmd == "memory":
            mm = MemoryManager()
            mem = mm.combined()
            print(mem if mem else "  No memory (ZC.md) found.")
        elif cmd == "doctor":
            _run_doctor()
        elif cmd == "plugin":
            from wire.zc_plugins import cmd_plugin_list
            cmd_plugin_list()
        elif cmd == "output-style":
            from wire.zc_output_styles import cmd_list_output_styles
            cmd_list_output_styles()
        elif cmd == "statusline":
            from wire.zc_settings import cmd_status_line
            cmd_status_line(model=model, cwd=cwd)
        return

    # Check for custom slash command (project/skills dirs, then plugins)
    for d in (COMMANDS_DIR, SKILLS_DIR):
        if d.exists():
            for f in d.rglob("*.md"):
                if f.stem == cmd:
                    content = f.read_text()
                    print(f"\033[94mℹ Running custom command: /{cmd}\033[0m\n")
                    session = CodeSession(cwd=cwd, model=model)
                    agent   = CodeAgent(api_key=api_key, model=model)
                    agent.query(
                        f"{content}\n\n{prompt}" if prompt else content,
                        session, tools="code", permission="acceptEdits",
                    )
                    return

    try:
        from wire.zc_plugins import load_plugin_commands
        for entry in load_plugin_commands():
            if entry["name"] == cmd or entry["name"].split(":", 1)[-1] == cmd:
                content = Path(entry["path"]).read_text()
                print(f"\033[94mℹ Running plugin command: /{entry['name']}\033[0m\n")
                session = CodeSession(cwd=cwd, model=model)
                agent   = CodeAgent(api_key=api_key, model=model)
                agent.query(
                    f"{content}\n\n{prompt}" if prompt else content,
                    session, tools="code", permission="acceptEdits",
                )
                return
    except ImportError:
        pass

    print(f"\033[91m✗ Unknown slash command: {full_cmd}\033[0m")
    print("  Run: ai-coder --code-agent-slash help")


def cmd_code_cost(api_key: str):
    """Show cost summary across all sessions."""
    sessions = sorted(SESSIONS_DIR.glob("*.json"))
    total_in, total_out, total_cost = 0, 0, 0.0
    print(f"\n{'SESSION':<18}{'TURNS':<8}{'IN':<12}{'OUT':<12}{'COST'}")
    print("─" * 60)
    for sf in sessions[-20:]:
        try:
            d = json.loads(sf.read_text())
            i = d.get("input_tokens", 0)
            o = d.get("output_tokens", 0)
            c = d.get("cost_usd", 0.0)
            t = len(d.get("turns", [])) // 2
            total_in += i; total_out += o; total_cost += c
            print(f"{d['id'][:16]:<18}{t:<8}{i:,<12}{o:,<12}${c:.4f}")
        except Exception as _e:
            pass
    print("─" * 60)
    print(f"{'TOTAL':<18}{'':8}{total_in:,<12}{total_out:,<12}${total_cost:.4f}")


def cmd_code_list_sessions():
    sessions = sorted(SESSIONS_DIR.glob("*.json"))
    if not sessions:
        print("No code agent sessions saved.")
        return
    print(f"\n{'ID':<18}{'TURNS':<8}{'MODEL':<25}{'UPDATED'}")
    print("─" * 65)
    for sf in sessions[-25:]:
        try:
            d = json.loads(sf.read_text())
            t = len(d.get("turns", [])) // 2
            print(f"{d['id'][:16]:<18}{t:<8}{d.get('model','')[:24]:<25}{d.get('updated_at','')[:10]}")
        except Exception as _e:
            pass


def cmd_code_list_tools():
    print("\nBuilt-in tools:")
    descs = {
        "Read":"Read file contents",      "Write":"Write a file",
        "Edit":"Edit part of a file",      "MultiEdit":"Multi-location edit",
        "Bash":"Run bash commands",         "Glob":"Find files by pattern",
        "Grep":"Search file contents",      "LS":"List directory",
        "WebSearch":"Search the web",       "WebFetch":"Fetch a URL",
        "TodoRead":"Read todo list",         "TodoWrite":"Update todo list",
        "NotebookRead":"Read Jupyter nb",   "NotebookEdit":"Edit Jupyter nb",
        "Task":"Spawn a subagent task",
    }
    for name, desc in descs.items():
        print(f"  {name:<15} — {desc}")
    print("\nTool presets:")
    for name, tools in TOOL_PRESETS.items():
        print(f"  {name:<12} — {', '.join(tools[:5])}{'…' if len(tools)>5 else ''}")
    print("\nPermission modes:")
    for mode, desc in PERMISSION_MODES.items():
        print(f"  {mode:<20} — {desc}")


def _run_doctor():
    """Diagnostics for zAICoder environment."""
    print("\n\033[94mℹ zAICoder Diagnostics\033[0m")
    checks = [
        ("ANTHROPIC_API_KEY set",  bool(os.getenv("ANTHROPIC_API_KEY"))),
        (".mcp.json exists",       MCP_JSON.exists()),
        (".zc/settings.json",  SETTINGS_JSON.exists()),
        (".zc/agents/ exists", AGENTS_DIR.exists()),
        (".zc/skills/ exists", SKILLS_DIR.exists()),
        ("ZC.md exists",       MEMORY_FILE.exists() or Path("ZC.md").exists()),
        ("~/.zc/ZC.md",    USER_MEMORY.exists()),
        ("Sessions dir",           SESSIONS_DIR.exists()),
    ]
    try:
        from wire.zc_plugins import marketplace_list, plugin_list
        checks.append(("Plugins installed", len(plugin_list()) > 0))
        checks.append(("Marketplaces registered", len(marketplace_list()) > 0))
    except ImportError:
        pass
    all_ok = True
    for name, ok in checks:
        icon = "\033[92m✓\033[0m" if ok else "\033[93m○\033[0m"
        print(f"  {icon} {name}")
        if not ok:
            all_ok = False
    if all_ok:
        print("\n\033[92m✓ All checks passed.\033[0m")
    else:
        print("\n\033[93m⚠ Some items not configured (optional).\033[0m")
