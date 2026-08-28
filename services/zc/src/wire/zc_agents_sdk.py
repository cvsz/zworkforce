"""
zc_agents.py — zAICoder Agent SDK / Managed Agents
AI Model Coder CLI v1.8.0

Implements the zAICoder Agent SDK patterns:
  • Stateful sessions with persistent event history
  • Subagent spawning and orchestration
  • MCP server connections (stdio / SSE / HTTP)
  • MCP tunnels (research preview) — expose a local-only MCP server via a
    public Anthropic-routed URL, so it can be wired up as an mcp_servers
    entry without deploying it publicly first. See McpTunnel.
  • Tool search and on-demand tool loading
  • Session resume
  • Permission modes
  • zAICoder Managed Agents (beta) via API
  • Self-hosted sandboxes (public beta, v1.26.0) — run agent tool
    execution on infrastructure you control instead of Anthropic's cloud
    sandbox. See ManagedAgentsClient.create_environment(env_type=
    "self_hosted") and get_environment_work_stats().

CLI flags:
  --agent-session ID       Resume or create a named session
  --agent-mcp URL          Connect an MCP server
  --agent-mcp-stdio CMD    Connect stdio MCP server
  --agent-mcp-tunnel PORT  Open an MCP tunnel to a local MCP server on PORT
                           and print its public URL (research preview)
  --agent-tools TOOLS      Comma-separated tool preset
  --agent-permission MODE  acceptEdits | askPermission | supervised
  --agent-subagent PROMPT  Spawn a subagent for a sub-task
  --agent-list-sessions    List saved sessions
  --agent-resume ID        Resume a session
  --agent-memory-store NAME    Create/reuse a persistent Managed Agents
                                memory store, mounted into the session
                                started by --agent-managed-run (v1.19.0,
                                agent-memory-2026-07-22 beta)
  --agent-memory-store-create  Create a memory store standalone, without
                                also running a task (v1.19.0)
  --agent-dream STORE_ID        Run a Dreaming pass over a memory store,
                                 curating it into a new output store
                                 (v1.20.0, research preview,
                                 dreaming-2026-04-21 beta)
  --agent-dream-sessions IDS    Comma-separated session IDs to fold into
                                 the dream, alongside the memory store
  --agent-dream-instructions T  Optional steering text for the dream
  --agent-dream-list            List non-archived dreams in the workspace
  --agent-dream-get ID           Retrieve one dream's status/output
  --agent-outcome DESC          With --agent-managed-run: define an outcome
                                 (rubric-graded self-correction loop)
                                 instead of a single plain task (v1.20.0,
                                 public beta, part of managed-agents-2026-04-01)
  --agent-outcome-rubric FILE   Markdown rubric file for --agent-outcome
                                 (required alongside --agent-outcome)
  --agent-outcome-max-iter N    max_iterations for the outcome loop
                                 (default 3, max 20)
  --agent-webhook-register URL  Register a webhook to be notified of
                                 session/outcome/dream events (v1.20.0,
                                 public beta)
  --agent-webhook-events LIST   Comma-separated event types to subscribe
                                 (with --agent-webhook-register)
  --agent-vault-create NAME     Create a vault (v1.21.0, public beta)
  --agent-vault-external-user ID  Optional external_user_id metadata for
                                 --agent-vault-create
  --agent-vault-add-credential VAULT_ID  Add a credential to a vault
  --agent-vault-cred-type TYPE   mcp_oauth | static_bearer | environment_variable
                                 (with --agent-vault-add-credential)
  --agent-vault-mcp-url URL      MCP server URL (mcp_oauth/static_bearer)
  --agent-vault-secret-name NAME Environment variable name (environment_variable)
  --agent-vault-secret VALUE     The credential's secret value (write-only)
  --agent-vault-allowed-domains LIST  Comma-separated allow-listed domains
                                 (environment_variable)
  --agent-vault-list             List vaults in the workspace
  --agent-vault VAULT_ID         With --agent-managed-run: mount a vault's
                                 credentials into the session
  --agent-schedule-create AGENT_ID  Attach a cron schedule (v1.21.0,
                                 public beta) to AGENT_ID
  --agent-schedule-env ENV_ID    Environment id (with --agent-schedule-create)
  --agent-schedule-cron EXPR     Cron expression (with --agent-schedule-create)
  --agent-schedule-tz TZ         IANA timezone (default UTC)
  --agent-schedule-task TEXT     Initial task text for the scheduled session
  --agent-schedule-list          List scheduled deployments
  --agent-schedule-cancel ID     Archive a scheduled deployment
  --agent-review-multiagent PATH  Native Multiagent orchestration (v1.21.0):
                                 parallel specialist code review over one
                                 shared sandbox
  --agent-review-specialists LIST  Comma-separated specialists (security,
                                 style, test-coverage) for --agent-review-multiagent
  --agent-outcome-rubric-upload FILE  Upload a rubric once via the Files
                                 API, print its file_id (v1.21.0)
  --agent-outcome-rubric-file ID  Reuse an uploaded rubric's file_id with
                                 --agent-outcome instead of --agent-outcome-rubric
  --agent-override-json FILE     With --agent-managed-run: JSON file of an
                                 agent_with_overrides dict (v1.22.0, public beta)
  --agent-override-model MODEL   With --agent-managed-run: override just the model
  --agent-override-system TEXT   With --agent-managed-run: override just the system prompt
  --agent-stream-deltas          With --agent-managed-run: live-print text as it's
                                 generated (v1.22.0, public beta)
  --agent-vault-injection-location LOC  headers | body | both — where an
                                 environment_variable credential's secret is
                                 substituted at egress (v1.22.0, public beta)

Managed Agents memory stores vs. the other two "memory" features in this
codebase — they solve different problems and don't overlap:
  • zc_memory.py's memory_20250818 tool: client-side, you implement the
    file-operation handlers yourself, scoped to whatever storage you wire
    it to (local disk, DB, etc.), used with the plain Messages API.
  • zAICoder's local .zc/auto MEMORY.md: lives only on the
    developer's own machine, loaded into a zAICoder session's context.
  • Managed Agents memory store (v1.19.0): server-side, Anthropic-hosted,
    versioned, workspace-scoped, mounted as a `resources` entry when
    creating a Managed Agents session.
  • Dreaming (v1.20.0, this module): reads a memory store plus past
    session transcripts and produces a *new, curated* output memory
    store — merging duplicates, dropping stale entries, promoting
    recurring patterns. It doesn't replace a memory store, it cleans one
    up; the input store is never modified. Research preview, requires
    `dreaming-2026-04-21` in addition to `managed-agents-2026-04-01`.

Outcomes (v1.20.0) vs. just prompting harder: an outcome-oriented session
gets a `user.define_outcome` event (description + rubric + max_iterations)
instead of a plain `user.message`. A separate grader model evaluates the
agent's work against the rubric in its own context window (so it isn't
swayed by the agent's own reasoning) and the agent revises until the
grader is satisfied or `max_iterations` is hit. Public beta, no extra
beta header beyond `managed-agents-2026-04-01`.

Webhooks (v1.20.0): out-of-band HTTP notifications for session/outcome/
dream lifecycle events, so a long-running Managed Agents task doesn't
need a client holding an SSE stream open the whole time. Public beta.
"""

import json
import os
import time
import urllib.error
import urllib.request
import typing
import uuid
from pathlib import Path
from typing import Optional

from wire.exceptions import AICoderError
from wire.resilience import CircuitBreaker, raise_for_http_error, retry, urlopen_json

SESSIONS_DIR = Path(os.path.expanduser("~/.ai-coder/agent_sessions"))
ENDPOINT     = "https://api.anthropic.com/v1/messages"
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)


# ── Permission modes ───────────────────────────────────────────────────────

class PermissionMode:
    ACCEPT_EDITS   = "acceptEdits"      # auto-approve all tool calls
    ASK_PERMISSION = "askPermission"    # ask user for each tool call
    SUPERVISED     = "supervised"       # auto-approve reads, ask for writes


# ── Tool presets ───────────────────────────────────────────────────────────

TOOL_PRESETS = {
    "all":          ["bash", "text_editor", "web_search", "code_execution"],
    "code":         ["bash", "text_editor", "code_execution"],
    "web":          ["web_search", "web_fetch"],
    "readonly":     ["web_search", "web_fetch", "code_execution"],
    "filesystem":   ["bash", "text_editor"],
}


# ── AgentSession ──────────────────────────────────────────────────────────

class AgentSession:
    """Persistent session with message history and tool state."""

    def __init__(self, session_id: Optional[str] = None, name: str = "",
                 permission_mode: str = PermissionMode.ASK_PERMISSION):
        self.id              = session_id or str(uuid.uuid4())[:12]
        self.name            = name or f"session-{self.id}"
        self.permission_mode = permission_mode
        self.history: list   = []
        self.mcp_servers: list = []
        self.created_at      = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.updated_at      = self.created_at
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load(cls, session_id: str) -> "AgentSession":
        p = SESSIONS_DIR / f"{session_id}.json"
        if not p.exists():
            raise FileNotFoundError(f"Session {session_id} not found.")
        data = json.loads(p.read_text())
        s = cls.__new__(cls)
        s.__dict__.update(data)
        return s

    def save(self):
        self.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        p = SESSIONS_DIR / f"{self.id}.json"
        p.write_text(json.dumps(self.__dict__, indent=2))

    def add_turn(self, role: str, content: str):
        self.history.append({"role": role, "content": content,
                              "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ")})

    def messages(self) -> list[dict]:
        return [{"role": t["role"], "content": t["content"]} for t in self.history]


# ── MCP connector config ───────────────────────────────────────────────────

class McpServerConfig:
    def __init__(self, type: str, name: str, **kwargs):
        self.type = type
        self.name = name
        self.extra = kwargs

    def to_dict(self) -> dict:
        return {"type": self.type, "name": self.name, **self.extra}

    @classmethod
    def stdio(cls, name: str, command: str, args: Optional[list] = None) -> "McpServerConfig":
        return cls("stdio", name, command=command, args=args or [])

    @classmethod
    def sse(cls, name: str, url: str, headers: Optional[dict] = None) -> "McpServerConfig":
        return cls("sse", name, url=url, headers=headers or {})

    @classmethod
    def http(cls, name: str, url: str, headers: Optional[dict] = None) -> "McpServerConfig":
        return cls("http", name, url=url, headers=headers or {})


# ── MCP tunnels (research preview) ─────────────────────────────────────────
# New surface (checked platform.zc.com/docs, 2026-07-02) for exposing a
# local MCP server — one only reachable on your machine/private network —
# to the zAICoder API without deploying it publicly first. Distinct from
# McpServerConfig above, which connects to an MCP server that's already
# reachable at a URL (sse/http) or spawnable as a local subprocess (stdio):
# a tunnel is what makes a *local* server reachable in the first place, so
# you can then hand its public tunnel URL to McpServerConfig.sse/http.
# Moved off the Admin API onto its own /v1/tunnels surface in the last
# couple of months per the release notes; research preview, so this can
# still change shape — re-verify before depending on it for anything but
# local dev/testing.
MCP_TUNNELS_BETA = "mcp-tunnels-2026-06-22"
TUNNELS_ENDPOINT = "https://api.anthropic.com/v1/tunnels"


class McpTunnel:
    """Client for the MCP tunnels research preview. Opens a public,
    Anthropic-routed URL that forwards to a local MCP server, so a server
    only reachable on localhost/your private network can still be handed to
    McpServerConfig.sse()/http() as an mcp_servers entry in a Messages API
    request. Local-only MCP dev servers, or servers behind a firewall that
    you don't want to expose directly, are the intended use case."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.tunnel_id: Optional[str] = None
        self.public_url: Optional[str] = None

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": MCP_TUNNELS_BETA,
        }

    def open(self, local_port: int, name: Optional[str] = None) -> dict:
        """Open a tunnel to a local MCP server listening on local_port.
        Returns the API response, which includes the tunnel id and the
        public URL to hand to McpServerConfig.sse()/http()."""
        payload: dict[str, typing.Any] = {"local_port": local_port}
        if name:
            payload["name"] = name
        req = urllib.request.Request(
            TUNNELS_ENDPOINT, data=json.dumps(payload).encode(),
            headers=self._headers(), method="POST",
        )
        try:
            data = self._call(req)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}
        self.tunnel_id = data.get("id")
        self.public_url = data.get("url")
        return data

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, req: "urllib.request.Request") -> dict:
        return urlopen_json(req, timeout=30)

    def close(self) -> dict:
        """Close a previously opened tunnel."""
        if not self.tunnel_id:
            return {"error": "No open tunnel to close"}
        req = urllib.request.Request(
            f"{TUNNELS_ENDPOINT}/{self.tunnel_id}",
            headers=self._headers(), method="DELETE",
        )
        try:
            return self._call_delete(req)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call_delete(self, req: "urllib.request.Request") -> dict:
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return {"status": r.status}
        except (urllib.error.HTTPError, TimeoutError, ConnectionError, OSError) as e:
            raise_for_http_error(e)
            return {}

    def as_mcp_server(self, name: str, transport: str = "sse") -> McpServerConfig:
        """Build an McpServerConfig pointing at this tunnel's public URL,
        once open() has succeeded. transport is "sse" or "http" — whichever
        the local MCP server actually speaks."""
        if not self.public_url:
            raise RuntimeError("Tunnel not open yet — call open() first")
        return McpServerConfig(transport, name, url=self.public_url)


def cmd_mcp_tunnel_open(api_key: str, local_port: int, name: Optional[str] = None):
    """CLI entry: open a tunnel and print the public URL."""
    tunnel = McpTunnel(api_key)
    result = tunnel.open(local_port, name=name)
    if result.get("error"):
        print(f"\033[91m✗ Failed to open tunnel: {result['error']}\033[0m")
        return result
    print(f"\033[92m✓ Tunnel open: {tunnel.public_url}  (id={tunnel.tunnel_id})\033[0m")
    print(f"  Forwarding to local port {local_port}. Use this URL with "
          f"McpServerConfig.sse()/http() as an mcp_servers entry.")
    return result


# ── ManagedAgent ──────────────────────────────────────────────────────────
# NOTE: despite the name, this class does NOT call Anthropic's zAICoder
# Managed Agents API (/v1/agents, /v1/environments, /v1/sessions). It's a
# local agent loop built on the plain synchronous Messages API — an "agent"
# system prompt plus this module's own AgentSession for history/persistence.
# That's why _post() never sends the managed-agents-2026-04-01 beta header:
# there was nothing to attach it to, since ENDPOINT is /v1/messages, not a
# Managed Agents endpoint. For the actual hosted Managed Agents product
# (server-run sandbox, session persistence, SSE event streaming, webhooks),
# see ManagedAgentsClient below, which does call those endpoints and does
# send the beta header. Kept this class as-is (renaming would break
# cmd_agent_chat/cmd_agent_orchestrate call sites) but be aware it's really
# a lightweight local alternative, not a wrapper around the real product.

class ManagedAgent:
    """
    zAICoder Managed Agents via the Messages API.
    Uses agentic tool loops with session persistence.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-5",
                 max_tokens: int = 8192, system_prompt: Optional[str] = None):
        self.api_key     = api_key
        self.model       = model
        self.max_tokens  = max_tokens
        self.system      = system_prompt or (
            "You are an expert software agent. You have access to tools for "
            "reading files, running code, and searching the web. "
            "Complete tasks step-by-step, using tools as needed. "
            "Always verify your work before finishing."
        )

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict, beta: str = "") -> dict:
        headers = {
            "Content-Type":      "application/json",
            "x-api-key":         self.api_key,
            "anthropic-version": "2023-06-01",
        }
        if beta:
            headers["anthropic-beta"] = beta
        req = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        return urlopen_json(req, timeout=300)

    def _post(self, payload: dict, beta: str = "") -> dict:
        try:
            return self._call(payload, beta)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    # ── Simple session-aware call ──────────────────────────────────────────

    def chat(self, prompt: str, session: AgentSession,
             tools: Optional[list[dict]] = None) -> str:
        """Add a turn to the session and get a response."""
        session.add_turn("user", prompt)

        payload: dict = {
            "model":      self.model,
            "max_tokens": self.max_tokens,
            "system":     self.system,
            "messages":   session.messages(),
        }
        if tools:
            payload["tools"] = tools

        data = self._post(payload)
        if "error" in data:
            return f"[ERROR] {data['error']}"

        resp = "".join(
            b.get("text", "") for b in data.get("content", [])
            if b.get("type") == "text"
        )
        session.add_turn("assistant", resp)
        session.save()
        return resp

    # ── Subagent spawner ──────────────────────────────────────────────────

    def spawn_subagent(self, task: str, context: str = "",
                       tools: Optional[list[dict]] = None) -> str:
        """
        Spawn a focused subagent for a specific sub-task.
        Returns the subagent's result as a string.
        """
        sub_system = (
            "You are a focused subagent. Complete ONLY the specific task given. "
            "Be thorough but concise. Return just the result, no preamble."
        )
        prompt = f"Context: {context}\n\nTask: {task}" if context else task
        payload: dict = {
            "model":      self.model,
            "max_tokens": self.max_tokens,
            "system":     sub_system,
            "messages":   [{"role": "user", "content": prompt}],
        }
        if tools:
            payload["tools"] = tools

        data = self._post(payload)
        if "error" in data:
            return f"[SUBAGENT ERROR] {data['error']}"
        return "".join(
            b.get("text", "") for b in data.get("content", [])
            if b.get("type") == "text"
        )

    # ── Orchestrator ──────────────────────────────────────────────────────

    def orchestrate(self, goal: str, session: AgentSession,
                    max_steps: int = 8) -> dict:
        """
        High-level orchestrator: decompose goal into steps, run subagents,
        synthesise results.
        """
        # Step 1: Decompose
        print(f"\033[94mℹ Orchestrating: {goal[:60]}\033[0m")
        decomp_prompt = (
            f"Break this goal into 3-7 concrete, parallel or sequential steps. "
            f"Return as JSON array: [{{'step': int, 'task': str, 'depends_on': [int]}}]\n\n"
            f"Goal: {goal}"
        )
        raw = self.chat(decomp_prompt, session)

        steps = []
        try:
            import re
            m = re.search(r'\[.*\]', raw, re.DOTALL)
            if m:
                steps = json.loads(m.group(0))
        except Exception:
            steps = [{"step": 1, "task": goal, "depends_on": []}]

        print(f"  Decomposed into {len(steps)} steps")

        # Step 2: Execute steps as subagents
        step_results: dict[int, str] = {}
        for s in steps[:max_steps]:
            step_n = s.get("step", 0)
            task   = s.get("task", "")
            deps   = s.get("depends_on", [])

            context = "\n".join(
                f"Step {d} result: {step_results.get(d, '')[:500]}"
                for d in deps if d in step_results
            )
            print(f"  → Step {step_n}: {task[:60]}")
            result = self.spawn_subagent(task, context=context)
            step_results[step_n] = result

        # Step 3: Synthesise
        synthesis_prompt = (
            f"Goal: {goal}\n\nSubagent results:\n"
            + "\n\n".join(f"Step {k}: {v[:800]}" for k, v in step_results.items())
            + "\n\nSynthesise the above into a coherent, complete final answer."
        )
        final = self.chat(synthesis_prompt, session)

        return {
            "goal":         goal,
            "steps":        steps,
            "step_results": step_results,
            "final":        final,
        }


# ── ManagedAgentsClient (the actual hosted Managed Agents API) ─────────────
# Was missing entirely — nothing in this module talked to the real
# /v1/agents, /v1/environments, /v1/sessions endpoints. Per
# platform.zc.com/docs/en/managed-agents/quickstart (checked
# 2026-07-02): all Managed Agents endpoints require the
# managed-agents-2026-04-01 beta header (the official SDK sets it
# automatically for client.beta.{agents,environments,sessions}.* calls,
# which is what this wraps). Managed Agents is stateful server-side —
# sessions, sandbox filesystem state, and history all live on Anthropic's
# infrastructure — and is currently public beta, not GA, and not eligible
# for Zero Data Retention.
MANAGED_AGENTS_BETA = "managed-agents-2026-04-01"

# Managed Agents memory stores (v1.19.0) — a workspace-scoped, persistent,
# versioned file directory mountable into a session's `resources`. Found via
# the anthropic-sdk-python v0.116.0 release note "api: add
# agent-memory-2026-07-22 beta header" (checked 2026-07-08); confirmed
# against platform.zc.com/docs' Managed Agents memory pages the same
# day. Not to be confused with the memory_20250818 client-side tool in
# zc_memory.py, which is a completely separate, older (2025-09-29,
# now GA) feature with different scope and storage model.
MEMORY_STORE_BETA = "agent-memory-2026-07-22"

# Dreaming (v1.20.0) — research preview: reads a memory store plus past
# session transcripts and produces a new, curated output memory store.
# Found via this cycle's audit re-checking Managed Agents docs for what
# shipped alongside the memory-store feature closed in v1.19.0 (per that
# cycle's own note that "Dreaming" was mentioned alongside it). Confirmed
# genuinely absent: a first grep for "dream" found zero matches, and a
# second, differently-worded grep for "curat|reflect.*session|memory.*
# consolidat" also came up empty before this was written up as a gap.
DREAMING_BETA = "dreaming-2026-04-21"

# Vaults & credentials (v1.21.0, public beta) — per
# platform.zc.com/docs/en/managed-agents/vaults (checked 2026-07-08):
# no separate beta header beyond managed-agents-2026-04-01. A vault is a
# workspace-scoped collection of third-party credentials (MCP OAuth,
# static bearer, or environment-variable secrets for CLIs/SDKs) keyed to
# an end user; referenced by vault_ids at session creation. The agent's
# sandbox only ever sees an opaque placeholder for environment_variable
# credentials — the real secret is substituted at the network egress
# boundary, only on allow-listed domains. Distinct from
# zc_admin_api.py's API-key management (Anthropic's own platform
# keys) and from this project's own local .env (never sent to a
# sandbox).

# Scheduled deployments (v1.21.0, public beta) — per
# platform.zc.com/docs/en/managed-agents/scheduled-deployments
# (checked 2026-07-08): no separate beta header beyond
# managed-agents-2026-04-01 either. A deployment pairs an agent +
# environment + initial user.message event with a cron `schedule`
# ({"type": "cron", "expression": ..., "timezone": ...}); each firing
# starts a brand-new session. Distinct from --agent-orchestrate (one-
# shot, client-invoked) and from zc_workflow.py (sequences steps
# within a single invocation, never starts new sessions on a timer).
MULTIAGENT_MAX_ROSTER = 20

# Files API beta header, needed alongside MANAGED_AGENTS_BETA when an
# Outcomes rubric is passed by file_id instead of inline text (v1.21.0).
FILES_API_BETA = "files-api-2025-04-14"


def build_multiagent_config(agents: list) -> dict:
    """Build the {"type": "coordinator", "agents": [...]} dict passed as
    `multiagent` to create_agent(), per platform.zc.com/docs/en/
    managed-agents/multi-agent (checked 2026-07-08).

    Each entry in `agents` may be:
      - a plain agent_id string -> expanded to {"type": "agent", "id": id}
      - {"type": "self"} -> lets the coordinator spawn copies of itself
      - an already-shaped dict (e.g. {"type": "agent", "id": ..., "version": ...})
        -> passed through unchanged

    Raises ValueError if more than MULTIAGENT_MAX_ROSTER (20) entries are
    given — the API itself enforces this limit, but failing fast client-
    side gives a clearer error than a 4xx from the roster snapshot step."""
    if len(agents) > MULTIAGENT_MAX_ROSTER:
        raise ValueError(
            f"multiagent coordinator supports at most {MULTIAGENT_MAX_ROSTER} "
            f"agents in the roster, got {len(agents)}"
        )
    roster = []
    for a in agents:
        if isinstance(a, dict):
            roster.append(a)
        else:
            roster.append({"type": "agent", "id": a})
    return {"type": "coordinator", "agents": roster}


# Small built-in system-prompt presets for the --agent-review-multiagent
# CLI convenience wrapper (parallel specialist code review over one shared
# sandbox — the concrete wire use case that un-deferred Multiagent
# orchestration this cycle; see docs/35_upgrade_v1.21.0.md).
REVIEW_SPECIALIST_PRESETS = {
    "security": (
        "You are a security reviewer. Read the code at the given path and "
        "report vulnerabilities, unsafe input handling, secrets in source, "
        "and unsafe dependency usage. Be specific: file, line, and fix."
    ),
    "style": (
        "You are a style/lint reviewer. Read the code at the given path and "
        "report style inconsistencies, naming issues, dead code, and "
        "readability problems. Be specific: file, line, and fix."
    ),
    "test-coverage": (
        "You are a test-coverage reviewer. Read the code at the given path "
        "and report untested code paths, missing edge-case tests, and weak "
        "assertions. Be specific: file, function, and what test to add."
    ),
}


class ManagedAgentsClient:
    """Thin wrapper around the real zAICoder Managed Agents API
    (agent → environment → session), as distinct from the local
    Messages-API-based ManagedAgent class above. Requires the `anthropic`
    SDK to be new enough to expose client.beta.agents/environments/sessions
    — older pinned SDK versions won't have these."""

    def __init__(self, api_key: str):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)

    def create_agent(self, name: str, model: str = "zc-opus-4-8",
                     system: str = "You are a helpful coding assistant.",
                     tools: Optional[list] = None,
                     multiagent: Optional[dict] = None) -> dict:
        """Create a persisted, versioned Agent config. tools defaults to the
        full pre-built agent_toolset_20260401 (bash, file ops, web search,
        etc.) if not given.

        `multiagent` (v1.21.0, public beta), when given, makes this agent a
        *coordinator*: a {"type": "coordinator", "agents": [...]} dict (see
        build_multiagent_config()) declaring up to 20 other agents it can
        delegate to at runtime, sharing one sandbox filesystem and event
        stream within a single session. Omitted by default — no change to
        the existing single-agent behavior when not given."""
        tools = tools or [{"type": "agent_toolset_20260401"}]
        kwargs = {}
        if multiagent is not None:
            kwargs["multiagent"] = multiagent
        agent = self.client.beta.agents.create(
            name=name, model={"id": model}, system=system, tools=tools,
            betas=[MANAGED_AGENTS_BETA], **kwargs,  # type: ignore
        )
        return {"id": agent.id, "name": name, "model": model}

    def create_environment(self, name: str, networking: str = "unrestricted",
                           env_type: str = "cloud") -> dict:
        """Create a sandbox environment for an agent to run in.
        networking: "unrestricted" or "limited" (safer if the agent only
        needs to touch its own filesystem) — ignored when env_type is
        "self_hosted", since {"type": "self_hosted"} is the entire config;
        there are no networking/pool/capacity sub-fields (public beta,
        added v1.26.0). With self_hosted, tool execution runs on
        infrastructure you control (your own worker, or a managed provider
        like Cloudflare/Daytona/Modal/Vercel) instead of Anthropic's cloud
        sandbox — the agent loop, context management, and error recovery
        stay on Anthropic's side either way. After creating a self-hosted
        environment you still need to (1) generate an environment key —
        Console-only, regardless of whether the environment was created
        via Console or API — and (2) run a worker (EnvironmentWorker in
        the Python/TypeScript/Go SDKs, or `ant beta:worker poll`) that
        polls this environment's work queue with that key. See
        get_environment_work_stats() to check whether a worker is
        actually connected before creating a session against it."""
        if env_type == "self_hosted":
            config: typing.Any = {"type": "self_hosted"}
        else:
            config = {"type": "cloud", "networking": {"type": networking}}
        env = self.client.beta.environments.create(
            name=name, config=config, betas=[MANAGED_AGENTS_BETA],
        )
        return {"id": env.id, "name": name, "type": env_type}

    def get_environment_work_stats(self, environment_id: str) -> dict:
        """Read the self-hosted work queue's state for `environment_id`
        (public beta, v1.26.0) — GET-equivalent of
        `client.beta.environments.work.stats(environment_id)`. Meaningless
        for env_type="cloud" environments (no queue to poll there).
        Authenticates with the org API key, not the environment key — call
        this from your own monitoring/ops tooling, never from the worker
        host itself. Returns depth (items waiting to be claimed), pending
        (items a worker has already claimed and is processing),
        oldest_queued_at (timestamp of the oldest still-queued/processing
        item, or None), and workers_polling (workers that polled in the
        last 30s — use this for liveness alerting; if it's 0, no worker is
        connected and sessions routed here will queue forever instead of
        failing outright)."""
        stats = self.client.beta.environments.work.stats(environment_id)
        return {
            "depth": stats.depth,
            "pending": stats.pending,
            "oldest_queued_at": getattr(stats, "oldest_queued_at", None),
            "workers_polling": stats.workers_polling,
        }

    def create_memory_store(self, name: str, description: Optional[str] = None) -> dict:
        """Create a workspace-scoped, persistent Managed Agents memory
        store — a versioned collection of text documents that survives
        across sessions. Distinct from `zc_memory.py`'s client-side
        `memory_20250818` tool (which requires the caller's own app to
        implement file-operation handlers, scoped to one conversation)
        and from zAICoder's local `.zc`/`MEMORY.md` auto-memory
        (which never leaves the developer's machine). A memory store
        lives on Anthropic's infrastructure, is mounted into a session at
        creation time as a `resources` entry, and every write gets an
        immutable version for audit/point-in-time recovery. Public beta.

        Beta header, corrected in v1.27.0: this is a direct call to a
        `/v1/memory_stores/*` endpoint. Per platform.zc.com/docs'
        July 2, 2026 release note, `agent-memory-2026-07-22`
        (MEMORY_STORE_BETA) now *replaces* `managed-agents-2026-04-01`
        on memory store endpoints specifically — sending both headers on
        one of these calls returns a 400. Every other Managed Agents
        endpoint (sessions, agents, environments, dreams, ...) is
        unaffected and still wants MANAGED_AGENTS_BETA alone (or
        alongside its own feature-specific header, e.g. DREAMING_BETA).
        create_session()'s memory_store_id branch is deliberately left
        sending both: it calls /v1/sessions, not a memory_stores
        endpoint, and the docs scope the replacement to memory store
        endpoints only."""
        kwargs: dict[str, typing.Any] = {"name": name, "betas": [MEMORY_STORE_BETA]}
        if description is not None:
            kwargs["description"] = description
        store = self.client.beta.memory_stores.create(**kwargs)
        return {"id": store.id, "name": name}

    def get_memory_store(self, memory_store_id: str) -> dict:
        """Retrieve a single memory store's metadata (name, description,
        archived status). GET /v1/memory_stores/{id} — memory store
        endpoint, so MEMORY_STORE_BETA alone (see create_memory_store()'s
        docstring for why not MANAGED_AGENTS_BETA too)."""
        store = self.client.beta.memory_stores.retrieve(
            memory_store_id, betas=[MEMORY_STORE_BETA],
        )
        return {"id": getattr(store, "id", memory_store_id), "raw": store}

    def list_memory_stores(self, include_archived: bool = False,
                           limit: int = 50, page: Optional[str] = None) -> dict:
        """List memory stores in the workspace. GET /v1/memory_stores —
        memory store endpoint, MEMORY_STORE_BETA alone."""
        params: dict[str, typing.Any] = {"limit": limit, "include_archived": include_archived}
        if page is not None:
            params["page"] = page
        result = self.client.beta.memory_stores.list(
            betas=[MEMORY_STORE_BETA], **params,
        )
        return {"raw": result}

    def archive_memory_store(self, memory_store_id: str) -> dict:
        """Archive a memory store: makes it read-only and prevents new
        sessions from attaching it. One-way — there is no unarchive.
        POST /v1/memory_stores/{id}/archive — memory store endpoint,
        MEMORY_STORE_BETA alone."""
        store = self.client.beta.memory_stores.archive(
            memory_store_id, betas=[MEMORY_STORE_BETA],
        )
        return {"id": memory_store_id, "raw": store}

    def delete_memory_store(self, memory_store_id: str) -> dict:
        """Permanently delete a memory store along with all of its
        memories and versions. DELETE /v1/memory_stores/{id} — memory
        store endpoint, MEMORY_STORE_BETA alone. Irreversible; callers
        should confirm before invoking (see cmd_agent_memory_store_delete
        for the CLI's confirmation gate)."""
        self.client.beta.memory_stores.delete(
            memory_store_id, betas=[MEMORY_STORE_BETA],
        )
        return {"id": memory_store_id, "deleted": True}

    def list_memories(self, memory_store_id: str, path_prefix: Optional[str] = None,
                      depth: Optional[int] = None, limit: int = 50,
                      page: Optional[str] = None) -> dict:
        """List the individual memory entries inside a memory store (v1.24.0)
        — distinct from create_memory_store(), which only creates the store
        itself. GET /v1/memory_stores/{memory_store_id}/memories, sent with
        the agent-memory-2026-07-22 beta header (MEMORY_STORE_BETA), which
        changes this endpoint's list behavior: results come back in a
        stable, server-defined order (any client-side order_by/order the
        SDK might otherwise send is not applicable here and isn't sent);
        `depth` only accepts 0, 1, or omitted — anything else 400s
        server-side, so this raises ValueError client-side first instead;
        and `path_prefix`, if given, must end with "/" and matches whole
        path segments rather than an arbitrary substring (raises ValueError
        if it doesn't end with "/", to fail fast instead of a confusing
        empty result set from the server's substring-vs-segment
        mismatch). Page cursors from the older list behavior aren't valid
        here — always start from the first page (page=None) when calling
        this fresh."""
        if depth is not None and depth not in (0, 1):
            raise ValueError(
                f"depth must be 0, 1, or omitted (got {depth!r}) — "
                f"agent-memory-2026-07-22 rejects any other value"
            )
        if path_prefix is not None and not path_prefix.endswith("/"):
            raise ValueError(
                f"path_prefix must end with '/' under agent-memory-2026-07-22 "
                f"(got {path_prefix!r}) — it matches whole path segments, not "
                f"an arbitrary substring"
            )
        params: dict[str, typing.Any] = {"limit": limit}
        if path_prefix is not None:
            params["path_prefix"] = path_prefix
        if depth is not None:
            params["depth"] = depth
        if page is not None:
            params["page"] = page
        result = self.client.beta.memory_stores.memories.list(
            memory_store_id, betas=[MEMORY_STORE_BETA], **params,
        )
        return {
            "memory_store_id": memory_store_id, "path_prefix": path_prefix,
            "depth": depth, "raw": result,
        }

    def create_memory(self, memory_store_id: str, path: str, content: str) -> dict:
        """Create a memory at `path` inside a store. Does not overwrite —
        an existing memory at that path must go through update_memory()
        instead. POST /v1/memory_stores/{id}/memories — memory store
        endpoint, MEMORY_STORE_BETA alone. Individual memories are capped
        at 100 kB (~25k tokens) by the platform; larger content should be
        split into multiple focused memories rather than one large one."""
        mem = self.client.beta.memory_stores.memories.create(
            memory_store_id, path=path, content=content, betas=[MEMORY_STORE_BETA],
        )
        return {"id": getattr(mem, "id", None), "path": path, "raw": mem}

    def get_memory(self, memory_store_id: str, memory_id: str) -> dict:
        """Retrieve a single memory's full content. GET
        /v1/memory_stores/{id}/memories/{memory_id} — memory store
        endpoint, MEMORY_STORE_BETA alone."""
        mem = self.client.beta.memory_stores.memories.retrieve(
            memory_id, memory_store_id=memory_store_id, betas=[MEMORY_STORE_BETA],
        )
        return {"id": memory_id, "raw": mem}

    def update_memory(self, memory_store_id: str, memory_id: str,
                      content: Optional[str] = None, path: Optional[str] = None,
                      content_sha256: Optional[str] = None) -> dict:
        """Update an existing memory's content and/or rename it (path).
        POST /v1/memory_stores/{id}/memories/{memory_id} — memory store
        endpoint, MEMORY_STORE_BETA alone. Pass `content_sha256` (the
        hash of the content you last read) to use optimistic concurrency:
        the update only applies if the stored content still matches that
        hash, protecting against clobbering a concurrent write; on
        mismatch the platform rejects the request and the caller should
        re-read the memory and retry."""
        kwargs: dict[str, any] = {"betas": [MEMORY_STORE_BETA]}  # type: ignore
        if content is not None:
            kwargs["content"] = content
        if path is not None:
            kwargs["path"] = path
        if content_sha256 is not None:
            kwargs["precondition"] = {"type": "content_sha256", "content_sha256": content_sha256}
        kwargs["memory_store_id"] = memory_store_id
        mem = self.client.beta.memory_stores.memories.update(
            memory_id, **kwargs,
        )
        return {"id": memory_id, "raw": mem}

    def delete_memory(self, memory_store_id: str, memory_id: str) -> dict:
        """Delete a single memory. Its version history survives the
        deletion (versions belong to the store, not the memory). DELETE
        /v1/memory_stores/{id}/memories/{memory_id} — memory store
        endpoint, MEMORY_STORE_BETA alone."""
        self.client.beta.memory_stores.memories.delete(
            memory_id, memory_store_id=memory_store_id, betas=[MEMORY_STORE_BETA],
        )
        return {"id": memory_id, "deleted": True}

    def create_session(self, agent_id: str, environment_id: str, title: str = "",
                       memory_store_id: Optional[str] = None,
                       vault_ids: Optional[list] = None,
                       agent_overrides: Optional[dict] = None) -> dict:
        """Create a session. If `memory_store_id` is given, mount that
        memory store as a session resource so the agent can read/write it
        through normal file tools — no memory-tool handler code required
        on our end, since Anthropic hosts the storage.

        If `vault_ids` (v1.21.0, public beta) is given, those vaults'
        credentials are made available to the session — MCP servers the
        agent declares are matched by mcp_server_url, and
        environment_variable credentials are injected at network egress
        for any allow-listed domain. Omitted by default: no regression to
        the pre-v1.21.0 no-vault path, since `vault_ids` is only included
        in the request when actually given.

        If `agent_overrides` (v1.22.0, public beta) is given, this
        session runs a modified copy of the agent's configuration
        instead of its stored version — the agent resource itself is
        never changed. `agent_overrides` may contain any of: `version`
        (pin a specific agent version to override on top of), `model`,
        `system`, `tools`, `mcp_servers`, `skills`. Per
        platform.zc.com/docs/en/managed-agents/sessions: omitting a
        field inherits the agent's stored value; setting a field to None
        (or `[]` for list fields) clears it for this session only,
        except `model` (never clearable — the API 400s) — that
        restriction is enforced server-side, not here. Omitted entirely
        (the default), `agent` is sent as the bare agent_id string,
        unchanged from pre-v1.22.0 behavior."""
        resources: typing.Any = None
        betas = [MANAGED_AGENTS_BETA]
        if memory_store_id:
            resources = [{"type": "memory_store", "memory_store_id": memory_store_id}]
            betas = [MANAGED_AGENTS_BETA, MEMORY_STORE_BETA]
        kwargs = {}
        if vault_ids:
            kwargs["vault_ids"] = vault_ids
        agent_param: typing.Any = agent_id
        if agent_overrides:
            agent_param = {"type": "agent_with_overrides", "id": agent_id, **agent_overrides}
        session = self.client.beta.sessions.create(
            agent=agent_param, environment_id=environment_id, title=title,
            resources=resources, betas=betas, **kwargs,  # type: ignore
        )
        return {
            "id": session.id, "agent_id": agent_id,
            "environment_id": environment_id, "memory_store_id": memory_store_id,
            "vault_ids": vault_ids, "agent_overrides": agent_overrides,
        }

    # ── Vaults & credentials (v1.21.0, public beta) ──────────────────────
    def create_vault(self, display_name: str, external_user_id: Optional[str] = None) -> dict:
        """Create a workspace-scoped vault — the collection of credentials
        for one end user. `external_user_id`, if given, is stored as
        metadata so the vault can be mapped back to your own user
        records; it isn't a structural field the API requires."""
        kwargs: dict[str, typing.Any] = {"betas": [MANAGED_AGENTS_BETA]}
        if external_user_id:
            kwargs["metadata"] = {"external_user_id": external_user_id}
        vault = self.client.beta.vaults.create(
            display_name=display_name, **kwargs,
        )
        return {"id": vault.id, "display_name": display_name,
                "external_user_id": external_user_id}

    VALID_INJECTION_LOCATIONS = ("headers", "body", "both")

    def add_credential(self, vault_id: str, credential_type: str,
                       mcp_server_url: Optional[str] = None,
                       secret_name: Optional[str] = None,
                       secret_value: str = "",
                       allowed_domains: Optional[list] = None,
                       injection_location: Optional[str] = None) -> dict:
        """Add a credential to a vault. credential_type is one of
        "mcp_oauth", "static_bearer" (both keyed by mcp_server_url — the
        token is injected automatically when the agent connects to an MCP
        server at that URL), or "environment_variable" (keyed by
        secret_name, restricted to allowed_domains — the sandbox only ever
        holds an opaque placeholder, the real value is substituted at
        network egress, so the model never sees it).

        `injection_location` (v1.22.0, public beta) is only valid for
        "environment_variable" credentials: one of "headers", "body", or
        "both", controlling whether the resolved secret is substituted,
        at egress, into the agent's outbound request headers, body, or
        both. Omitted by default — the platform applies its own default
        when not given, so this is purely additive over the v1.21.0
        behavior.

        secret_value is write-only end to end: never logged, never
        returned by the API, and must never appear in any exception
        message raised from this method."""
        if injection_location is not None and credential_type != "environment_variable":
            raise ValueError(
                "injection_location is only valid for credential_type="
                "'environment_variable'"
            )
        if injection_location is not None and injection_location not in self.VALID_INJECTION_LOCATIONS:
            raise ValueError(
                f"injection_location must be one of {self.VALID_INJECTION_LOCATIONS}, "
                f"got {injection_location!r}"
            )
        if credential_type in ("mcp_oauth", "static_bearer"):
            if not mcp_server_url:
                raise ValueError(
                    f"credential_type={credential_type!r} requires mcp_server_url"
                )
            auth: dict[str, typing.Any] = {"type": credential_type, "token": secret_value} \
                if credential_type == "static_bearer" \
                else {"type": credential_type, "access_token": secret_value}
            auth["mcp_server_url"] = mcp_server_url
            cred = self.client.beta.vaults.credentials.create(
                vault_id=vault_id, auth=auth,  # type: ignore
                betas=[MANAGED_AGENTS_BETA],
            )
        elif credential_type == "environment_variable":
            if not secret_name:
                raise ValueError("credential_type='environment_variable' requires secret_name")
            if not allowed_domains:
                raise ValueError("credential_type='environment_variable' requires allowed_domains")
            auth = {"type": credential_type, "secret_value": secret_value,
                    "networking": {"type": "allow_list", "allowed_domains": allowed_domains}}
            if injection_location is not None:
                auth["injection_location"] = injection_location
            auth["secret_name"] = secret_name
            cred = self.client.beta.vaults.credentials.create(
                vault_id=vault_id, auth=auth,  # type: ignore
                betas=[MANAGED_AGENTS_BETA],
            )
        else:
            raise ValueError(
                f"Unknown credential_type {credential_type!r}: expected "
                f"'mcp_oauth', 'static_bearer', or 'environment_variable'"
            )
        return {"id": cred.id, "vault_id": vault_id, "credential_type": credential_type,
                "mcp_server_url": mcp_server_url, "secret_name": secret_name}

    def list_vaults(self, include_archived: bool = False) -> list:
        """List non-archived vaults in the workspace, newest first."""
        page = self.client.beta.vaults.list(
            include_archived=include_archived, betas=[MANAGED_AGENTS_BETA],
        )
        return [{"id": v.id, "display_name": v.display_name} for v in page]

    def archive_vault(self, vault_id: str) -> dict:
        """Archive a vault. Cascades to all its credentials (secrets are
        purged; records are retained for auditing). Future sessions
        referencing this vault fail; already-running sessions continue."""
        vault = self.client.beta.vaults.archive(vault_id, betas=[MANAGED_AGENTS_BETA])
        return {"id": vault.id, "archived": True}

    def archive_credential(self, vault_id: str, credential_id: str) -> dict:
        """Archive one credential. Purges the secret payload; the
        credential's key (mcp_server_url or secret_name) stays visible and
        is freed for a replacement credential."""
        cred = self.client.beta.vaults.credentials.archive(
            credential_id, vault_id=vault_id, betas=[MANAGED_AGENTS_BETA],
        )
        return {"id": cred.id, "vault_id": vault_id, "archived": True}

    def run_task(self, session_id: str, task: str, stream_deltas: bool = False) -> dict:
        """Send a task as a user.message event and stream until the session
        goes idle. Returns the accumulated assistant text and tool calls.

        If `stream_deltas` (v1.22.0, public beta) is True, opts into
        `event_deltas=["text"]` on the event stream: `event_delta` events
        preview an agent.message's text as it's generated and are printed
        live here (for a live-typing effect), while `event_start` is a
        no-op marker that a not-yet-complete message has begun. The
        returned "text" is still accumulated only from complete
        agent.message blocks, exactly as before this parameter existed —
        so the return value is unchanged whether or not this is set.
        Default False: no `event_deltas` param is sent and no new event
        types are expected, matching pre-v1.22.0 behavior exactly."""
        text_parts: list[str] = []
        tool_calls: list[dict] = []
        stream_kwargs = {"event_deltas": ["text"]} if stream_deltas else {}
        with self.client.beta.sessions.events.stream(
            session_id, betas=[MANAGED_AGENTS_BETA], **stream_kwargs  # type: ignore
        ) as stream:
            self.client.beta.sessions.events.send(
                session_id,
                events=[{"type": "user.message", "content": [{"type": "text", "text": task}]}],
                betas=[MANAGED_AGENTS_BETA],
            )
            for event in stream:
                if event.type == "agent.message":
                    for block in event.content:
                        if getattr(block, "text", None):
                            text_parts.append(block.text)
                elif event.type == "agent.tool_use":
                    tool_calls.append({"name": event.name})
                elif event.type == "event_delta":
                    delta_text = getattr(event, "text", None) or getattr(event, "delta", "")
                    if delta_text:
                        print(delta_text, end="", flush=True)
                elif event.type == "event_start":
                    pass  # marks a not-yet-complete message; nothing to accumulate yet
                elif event.type == "session.status_idle":
                    break
        return {"text": "".join(text_parts), "tool_calls": tool_calls}


    # ── Dreaming (v1.20.0, research preview) ────────────────────────────
    def create_dream(self, memory_store_id: str, session_ids: Optional[list] = None,
                     model: str = "zc-opus-4-8", instructions: Optional[str] = None) -> dict:
        """Start a dream: curate `memory_store_id` (optionally alongside past
        `session_ids` transcripts) into a new output memory store. The input
        store is never modified — the dream produces a separate output store
        you can review, adopt, or discard. Returns immediately with
        status "pending"; poll get_dream() until status is a terminal state
        (completed/failed/canceled)."""
        inputs: typing.Any = [{"type": "memory_store", "memory_store_id": memory_store_id}]
        if session_ids:
            inputs.append({"type": "sessions", "session_ids": session_ids})
        dream = self.client.beta.dreams.create(  # type: ignore
            inputs=inputs, model={"id": model}, instructions=instructions,
            betas=[MANAGED_AGENTS_BETA, DREAMING_BETA],
        )
        return {"id": dream.id, "status": dream.status}

    def get_dream(self, dream_id: str) -> dict:
        """Retrieve a dream's current status and, once complete, the
        output_store_id of the curated memory store it produced."""
        dream = self.client.beta.dreams.retrieve(  # type: ignore
            dream_id, betas=[MANAGED_AGENTS_BETA, DREAMING_BETA],
        )
        output_store_id = None
        for output in getattr(dream, "outputs", None) or []:
            if getattr(output, "type", None) == "memory_store":
                output_store_id = output.memory_store_id
        return {"id": dream.id, "status": dream.status, "output_store_id": output_store_id,
                "error": getattr(dream, "error", None)}

    def list_dreams(self, include_archived: bool = False) -> list:
        """List non-archived dreams in the workspace, newest first."""
        page = self.client.beta.dreams.list(  # type: ignore
            include_archived=include_archived, betas=[MANAGED_AGENTS_BETA, DREAMING_BETA],
        )
        return [{"id": d.id, "status": d.status} for d in page]

    def cancel_dream(self, dream_id: str) -> dict:
        """Move a pending/running dream to canceled immediately."""
        dream = self.client.beta.dreams.cancel(  # type: ignore
            dream_id, betas=[MANAGED_AGENTS_BETA, DREAMING_BETA],
        )
        return {"id": dream.id, "status": dream.status}

    # ── Scheduled deployments (v1.21.0, public beta) ─────────────────────
    def create_scheduled_deployment(self, agent_id: str, environment_id: str,
                                    cron_expression: str, timezone: str = "UTC",
                                    task: str = "", memory_store_id: Optional[str] = None,
                                    name: str = "") -> dict:
        """Attach a cron schedule to an agent + environment pair. Each time
        the schedule fires, Managed Agents starts a brand-new session,
        sends `task` as its initial user.message, and runs it to
        completion — no external scheduler/cron host required on our
        side. Distinct from --agent-orchestrate (one-shot, client-
        invoked) and from zc_workflow.py (sequences steps within a
        single invocation, doesn't start new sessions on a timer)."""
        resources: typing.Any = None
        if memory_store_id:
            resources = [{"type": "memory_store", "memory_store_id": memory_store_id}]
        deployment = self.client.beta.deployments.create(
            name=name or f"scheduled-{agent_id}",
            agent=agent_id, environment_id=environment_id,
            schedule={"type": "cron", "expression": cron_expression, "timezone": timezone},
            initial_events=[{"type": "user.message", "content": [{"type": "text", "text": task}]}],
            resources=resources,
            betas=[MANAGED_AGENTS_BETA],
        )
        return {"id": deployment.id, "agent_id": agent_id, "environment_id": environment_id,
                "cron_expression": cron_expression, "timezone": timezone,
                "status": getattr(deployment, "status", None)}

    def list_scheduled_deployments(self) -> list:
        """List scheduled deployments in the workspace, newest first."""
        page = self.client.beta.deployments.list(betas=[MANAGED_AGENTS_BETA])
        return [{"id": d.id, "status": getattr(d, "status", None)} for d in page]

    def get_scheduled_deployment(self, deployment_id: str) -> dict:
        """Retrieve one scheduled deployment's current status/schedule."""
        d = self.client.beta.deployments.retrieve(deployment_id, betas=[MANAGED_AGENTS_BETA])
        return {"id": d.id, "status": getattr(d, "status", None),
                "schedule": getattr(d, "schedule", None)}

    def cancel_scheduled_deployment(self, deployment_id: str) -> dict:
        """Archive a scheduled deployment, stopping future scheduled runs
        (an in-flight run, if any, finishes normally)."""
        d = self.client.beta.deployments.archive(deployment_id, betas=[MANAGED_AGENTS_BETA])
        return {"id": d.id, "status": getattr(d, "status", None)}

    # ── Outcomes (v1.20.0, public beta; file_id rubric form v1.21.0) ─────
    def define_outcome(self, session_id: str, description: str,
                       rubric_text: Optional[str] = None,
                       rubric_file_id: Optional[str] = None,
                       max_iterations: int = 3) -> dict:
        """Send a user.define_outcome event: the agent starts working
        immediately toward `description`, revising until a grader (running
        in its own context window, independent of the agent's reasoning)
        is satisfied the rubric is met or `max_iterations` is hit. Do not
        also send a user.message — the define_outcome event alone kicks
        off the agent's work.

        Exactly one of `rubric_text` (inline markdown) or `rubric_file_id`
        (a file_id from the Files API — upload the rubric once, reuse it
        by id across many outcome-oriented sessions) must be given."""
        if bool(rubric_text) == bool(rubric_file_id):
            raise ValueError(
                "define_outcome requires exactly one of rubric_text or "
                "rubric_file_id, not both or neither"
            )
        rubric: typing.Any = None
        if rubric_file_id:
            rubric = {"type": "file", "file_id": rubric_file_id}
            betas = [MANAGED_AGENTS_BETA, FILES_API_BETA]
        else:
            rubric = {"type": "text", "content": rubric_text}
            betas = [MANAGED_AGENTS_BETA]
        result = self.client.beta.sessions.events.send(
            session_id,
            events=[{
                "type": "user.define_outcome",
                "description": description,
                "rubric": rubric,
                "max_iterations": max_iterations,
            }],
            betas=betas,
        )
        return {"session_id": session_id, "sent": True, "raw": result}

    def wait_for_outcome(self, session_id: str, stream_deltas: bool = False) -> dict:
        """Stream a session's events until the outcome reaches a terminal
        span.outcome_evaluation_end (satisfied / needs_revision loop exhaustion
        / max_iterations_reached / failed / interrupted), returning the
        accumulated assistant text like run_task().

        `stream_deltas` behaves exactly as in run_task(): opts into live
        preview text via `event_delta` events (printed as they arrive),
        with no change to the accumulated "text" return value either way."""
        text_parts: list[str] = []
        result_state = None
        stream_kwargs = {"event_deltas": ["text"]} if stream_deltas else {}
        with self.client.beta.sessions.events.stream(
            session_id, betas=[MANAGED_AGENTS_BETA], **stream_kwargs  # type: ignore
        ) as stream:
            for event in stream:
                if event.type == "agent.message":
                    for block in event.content:
                        if getattr(block, "text", None):
                            text_parts.append(block.text)
                elif event.type == "span.outcome_evaluation_end":
                    result_state = getattr(event, "result", None)
                elif event.type == "event_delta":
                    delta_text = getattr(event, "text", None) or getattr(event, "delta", "")
                    if delta_text:
                        print(delta_text, end="", flush=True)
                elif event.type == "event_start":
                    pass
                elif event.type == "session.status_idle":
                    break
        return {"text": "".join(text_parts), "result": result_state}

    # ── Webhooks (v1.20.0, public beta) ─────────────────────────────────
    def register_webhook(self, url: str, event_types: Optional[list] = None) -> dict:
        """Subscribe a URL to Managed Agents lifecycle events (session,
        outcome, dream). If event_types is omitted, subscribes to all
        event types the endpoint supports."""
        webhook = self.client.beta.webhooks.create(  # type: ignore
            url=url, event_types=event_types or None,
            betas=[MANAGED_AGENTS_BETA],
        )
        return {"id": webhook.id, "url": url, "event_types": event_types}


def cmd_managed_agent_run(task: str, api_key: str, model: str = "zc-opus-4-8",
                          memory_store: Optional[str] = None,
                          outcome_description: Optional[str] = None,
                          outcome_rubric: Optional[str] = None,
                          outcome_rubric_file_id: Optional[str] = None,
                          outcome_max_iterations: int = 3,
                          vault_id: Optional[str] = None,
                          agent_overrides: Optional[dict] = None,
                          stream_deltas: bool = False):
    """End-to-end convenience: create a throwaway agent + environment +
    session, run one task, print the result. For anything beyond a single
    one-off task, create the agent/environment once and reuse them across
    sessions instead — see ManagedAgentsClient methods.

    If `memory_store` is given (a store name, new or existing), it's
    created if needed and mounted into the session so the agent's work
    persists past this one throwaway session — pass the same name next
    time to keep building on it.

    If `outcome_description` and either `outcome_rubric` (inline markdown
    text) or `outcome_rubric_file_id` (a Files API file_id, v1.21.0) are
    given, the session runs as an outcome-oriented loop instead of a
    single plain task: `task` is ignored and the agent works toward
    `outcome_description` until a separate grader is satisfied the rubric
    is met or `outcome_max_iterations` is reached — see define_outcome().

    If `vault_id` (v1.21.0, public beta) is given, that vault's
    credentials are mounted into the session so any MCP servers or CLIs
    the agent uses can authenticate without the model ever seeing a raw
    secret — see ManagedAgentsClient.create_vault()/add_credential().

    If `agent_overrides` (v1.22.0, public beta) is given, this one
    throwaway session runs with those fields (any of model, system,
    tools, mcp_servers, skills) overriding the throwaway agent's config
    for just this session — see ManagedAgentsClient.create_session().

    If `stream_deltas` (v1.22.0, public beta) is True, text is printed
    live as it's generated instead of only after the full turn completes
    — see ManagedAgentsClient.run_task()/wait_for_outcome()."""
    mac = ManagedAgentsClient(api_key)
    print("\033[94mℹ Creating Managed Agent, environment, and session…\033[0m")
    agent = mac.create_agent(name=f"ai-coder-task-{uuid.uuid4().hex[:8]}", model=model)
    env   = mac.create_environment(name=f"ai-coder-env-{uuid.uuid4().hex[:8]}")
    store_id = None
    if memory_store:
        store = mac.create_memory_store(name=memory_store)
        store_id = store["id"]
        print(f"\033[94mℹ memory store '{memory_store}' -> {store_id}\033[0m")
    title = (outcome_description or task)[:60]
    vault_ids = [vault_id] if vault_id else None
    sess  = mac.create_session(agent["id"], env["id"], title=title, memory_store_id=store_id,
                               vault_ids=vault_ids, agent_overrides=agent_overrides)
    print(f"\033[92m✓ session {sess['id']}\033[0m — running task…\n")

    if outcome_description and (outcome_rubric or outcome_rubric_file_id):
        mac.define_outcome(sess["id"], outcome_description,
                           rubric_text=outcome_rubric,
                           rubric_file_id=outcome_rubric_file_id,
                           max_iterations=outcome_max_iterations)
        result = mac.wait_for_outcome(sess["id"], stream_deltas=stream_deltas)
        print(result["text"])
        print(f"\n\033[90m[outcome result: {result['result']}]\033[0m")
        return result

    result = mac.run_task(sess["id"], task, stream_deltas=stream_deltas)
    print(result["text"])
    if result["tool_calls"]:
        print(f"\n\033[90m[tools used: {', '.join(t['name'] for t in result['tool_calls'])}]\033[0m")
    return result


def cmd_agent_memory_store_create(name: str, api_key: str) -> dict:
    """Standalone helper: create a Managed Agents memory store without
    also spinning up an agent/environment/session, so it can be created
    once and reused across many `--agent-managed-run` invocations via
    `--agent-memory-store`."""
    mac = ManagedAgentsClient(api_key)
    store = mac.create_memory_store(name=name)
    print(f"\033[92m✓ memory store created\033[0m  id={store['id']}  name={store['name']}")
    return store


def cmd_agent_memory_list(memory_store_id: str, api_key: str,
                          path_prefix: Optional[str] = None,
                          depth: Optional[int] = None, limit: int = 50) -> dict:
    """List the memory entries inside a memory store (v1.24.0) — see
    ManagedAgentsClient.list_memories() for the agent-memory-2026-07-22
    list-behavior details (stable order, depth 0/1/omitted only,
    path_prefix must end with '/')."""
    mac = ManagedAgentsClient(api_key)
    result = mac.list_memories(memory_store_id, path_prefix=path_prefix,
                               depth=depth, limit=limit)
    raw = result["raw"]
    entries = raw.get("data", []) if isinstance(raw, dict) else list(raw)
    print(f"\n\033[94mMemories in {memory_store_id}\033[0m"
          f"{f' (path_prefix={path_prefix!r})' if path_prefix else ''}\n")
    for entry in entries:
        path = entry.get("path", "?") if isinstance(entry, dict) else getattr(entry, "path", "?")
        print(f"  {path}")
    if not entries:
        print("  (no memories found)")
    print()
    return result


def cmd_agent_memory_stores_list(api_key: str, include_archived: bool = False) -> dict:
    """List memory stores in the workspace (v1.27.0)."""
    mac = ManagedAgentsClient(api_key)
    result = mac.list_memory_stores(include_archived=include_archived)
    raw = result["raw"]
    entries = raw.get("data", []) if isinstance(raw, dict) else list(raw)
    print(f"\n\033[94mMemory stores\033[0m{' (including archived)' if include_archived else ''}\n")
    for entry in entries:
        get = (lambda k, d="?": entry.get(k, d)) if isinstance(entry, dict) else \
              (lambda k, d="?": getattr(entry, k, d))
        print(f"  {get('id')}  {get('name')}"
              f"{'  [archived]' if get('archived', False) else ''}")
    if not entries:
        print("  (no memory stores found)")
    print()
    return result


def cmd_agent_memory_store_archive(memory_store_id: str, api_key: str) -> dict:
    """Archive a memory store (v1.27.0) — one-way, no unarchive."""
    mac = ManagedAgentsClient(api_key)
    result = mac.archive_memory_store(memory_store_id)
    print(f"\033[92m✓ memory store archived\033[0m  id={memory_store_id}")
    return result


def cmd_agent_memory_store_delete(memory_store_id: str, api_key: str,
                                  confirm: bool = False) -> Optional[dict]:
    """Permanently delete a memory store and everything in it (v1.27.0).
    Requires --agent-memory-store-delete-yes (confirm=True) — dry-run by
    default, same confirmation pattern as zc_compliance_api.py's
    hard-delete commands, since this destroys the store's memories and
    version history irreversibly."""
    if not confirm:
        print(f"\033[93m[DRY RUN]\033[0m would permanently delete memory store "
              f"{memory_store_id} and all memories/versions in it. "
              f"Re-run with --agent-memory-store-delete-yes to actually delete.")
        return None
    mac = ManagedAgentsClient(api_key)
    result = mac.delete_memory_store(memory_store_id)
    print(f"\033[92m✓ memory store deleted\033[0m  id={memory_store_id}")
    return result


def cmd_agent_memory_get(memory_store_id: str, memory_id: str, api_key: str) -> dict:
    """Retrieve a single memory's full content (v1.27.0)."""
    mac = ManagedAgentsClient(api_key)
    result = mac.get_memory(memory_store_id, memory_id)
    raw = result["raw"]
    get = (lambda k, d=None: raw.get(k, d)) if isinstance(raw, dict) else \
          (lambda k, d=None: getattr(raw, k, d))
    print(f"\n\033[94mMemory {memory_id}\033[0m  path={get('path')}\n")
    print(get("content", "(no content)"))
    print()
    return result


def cmd_agent_memory_create(memory_store_id: str, path: str, content: str,
                            api_key: str) -> dict:
    """Create a memory at `path` inside a store (v1.27.0). Does not
    overwrite an existing memory at that path — use
    --agent-memory-update for that."""
    mac = ManagedAgentsClient(api_key)
    result = mac.create_memory(memory_store_id, path=path, content=content)
    print(f"\033[92m✓ memory created\033[0m  id={result['id']}  path={path}")
    return result


def cmd_agent_memory_update(memory_store_id: str, memory_id: str, api_key: str,
                            content: Optional[str] = None,
                            path: Optional[str] = None) -> dict:
    """Update an existing memory's content and/or path (v1.27.0)."""
    mac = ManagedAgentsClient(api_key)
    result = mac.update_memory(memory_store_id, memory_id, content=content, path=path)
    print(f"\033[92m✓ memory updated\033[0m  id={memory_id}")
    return result


def cmd_agent_memory_delete(memory_store_id: str, memory_id: str, api_key: str,
                            confirm: bool = False) -> Optional[dict]:
    """Delete a single memory (v1.27.0). Requires
    --agent-memory-delete-yes (confirm=True) — dry-run by default. The
    memory's version history survives the deletion."""
    if not confirm:
        print(f"\033[93m[DRY RUN]\033[0m would delete memory {memory_id} from "
              f"store {memory_store_id}. Re-run with --agent-memory-delete-yes "
              f"to actually delete.")
        return None
    mac = ManagedAgentsClient(api_key)
    result = mac.delete_memory(memory_store_id, memory_id)
    print(f"\033[92m✓ memory deleted\033[0m  id={memory_id}")
    return result


def cmd_agent_vault_create(display_name: str, api_key: str,
                           external_user_id: Optional[str] = None) -> dict:
    """Create a vault (v1.21.0, public beta) — a workspace-scoped
    collection of one end user's third-party credentials, referenced by
    vault_id from --agent-managed-run --agent-vault or from
    create_session()'s vault_ids."""
    mac = ManagedAgentsClient(api_key)
    vault = mac.create_vault(display_name=display_name, external_user_id=external_user_id)
    print(f"\033[92m✓ vault created\033[0m  id={vault['id']}  display_name={display_name}")
    print(f"  Add a credential: ai-coder --agent-vault-add-credential {vault['id']} "
          f"--agent-vault-cred-type static_bearer --agent-vault-mcp-url URL --agent-vault-secret TOKEN")
    return vault


def cmd_agent_vault_add_credential(vault_id: str, credential_type: str, api_key: str,
                                   mcp_server_url: Optional[str] = None,
                                   secret_name: Optional[str] = None,
                                   secret_value: str = "",
                                   allowed_domains: Optional[list] = None,
                                   injection_location: Optional[str] = None) -> dict:
    """Add a credential to an existing vault. Never prints secret_value —
    it's write-only, matching the docs' framing of these fields as
    sensitive."""
    mac = ManagedAgentsClient(api_key)
    cred = mac.add_credential(vault_id, credential_type, mcp_server_url=mcp_server_url,
                              secret_name=secret_name, secret_value=secret_value,
                              allowed_domains=allowed_domains,
                              injection_location=injection_location)
    print(f"\033[92m✓ credential added\033[0m  id={cred['id']}  vault_id={vault_id}  "
          f"type={credential_type}")
    return cred


def cmd_agent_vault_list(api_key: str) -> list:
    mac = ManagedAgentsClient(api_key)
    vaults = mac.list_vaults()
    for v in vaults:
        print(f"  {v['id']}  {v['display_name']}")
    if not vaults:
        print("  (no vaults found)")
    return vaults


def cmd_agent_dream(store_id: str, api_key: str, model: str = "zc-opus-4-8",
                    session_ids: Optional[list] = None, instructions: Optional[str] = None) -> dict:
    """Start a Dreaming pass over a memory store (research preview) and
    print the pending dream's id — dreams run asynchronously, poll with
    --agent-dream-get to check status/output_store_id."""
    mac = ManagedAgentsClient(api_key)
    dream = mac.create_dream(store_id, session_ids=session_ids, model=model, instructions=instructions)
    print(f"\033[92m✓ dream started\033[0m  id={dream['id']}  status={dream['status']}")
    print(f"\033[90m  Poll: ai-coder --agent-dream-get {dream['id']}\033[0m")
    return dream


def cmd_agent_dream_get(dream_id: str, api_key: str) -> dict:
    mac = ManagedAgentsClient(api_key)
    dream = mac.get_dream(dream_id)
    print(f"dream {dream['id']}: status={dream['status']}")
    if dream.get("output_store_id"):
        print(f"  output_store_id={dream['output_store_id']}")
    if dream.get("error"):
        print(f"  \033[91merror: {dream['error']}\033[0m")
    return dream


def cmd_agent_dream_list(api_key: str) -> list:
    mac = ManagedAgentsClient(api_key)
    dreams = mac.list_dreams()
    for d in dreams:
        print(f"  {d['id']}  status={d['status']}")
    if not dreams:
        print("  (no dreams found)")
    return dreams


def cmd_agent_schedule_create(agent_id: str, environment_id: str, cron_expression: str,
                              api_key: str, timezone: str = "UTC", task: str = "") -> dict:
    """Attach a cron schedule (v1.21.0, public beta) to an existing agent +
    environment. Requires an agent_id/environment_id created ahead of
    time via ManagedAgentsClient.create_agent()/create_environment() —
    unlike --agent-managed-run, a scheduled deployment reuses a
    persistent agent/environment rather than a throwaway pair, since it
    needs to keep firing after this command returns."""
    mac = ManagedAgentsClient(api_key)
    dep = mac.create_scheduled_deployment(agent_id, environment_id, cron_expression,
                                          timezone=timezone, task=task)
    print(f"\033[92m✓ scheduled deployment created\033[0m  id={dep['id']}  "
          f"cron='{cron_expression}' tz={timezone}")
    return dep


def cmd_agent_schedule_list(api_key: str) -> list:
    mac = ManagedAgentsClient(api_key)
    deployments = mac.list_scheduled_deployments()
    for d in deployments:
        print(f"  {d['id']}  status={d['status']}")
    if not deployments:
        print("  (no scheduled deployments found)")
    return deployments


def cmd_agent_schedule_cancel(deployment_id: str, api_key: str) -> dict:
    mac = ManagedAgentsClient(api_key)
    dep = mac.cancel_scheduled_deployment(deployment_id)
    print(f"\033[92m✓ scheduled deployment archived\033[0m  id={dep['id']}")
    return dep


def cmd_agent_env_self_hosted_create(name: str, api_key: str) -> dict:
    """Create a self-hosted sandbox environment (public beta, v1.26.0) —
    tool execution runs on infrastructure the caller controls instead of
    Anthropic's cloud sandbox. Prints the next manual steps since neither
    can be done from here: environment-key generation is Console-only,
    and running a worker is a separate long-lived process (EnvironmentWorker
    SDK helper, or `ant beta:worker poll`), not a one-shot CLI call."""
    mac = ManagedAgentsClient(api_key)
    env = mac.create_environment(name=name, env_type="self_hosted")
    print(f"\033[92m✓ self-hosted environment created\033[0m  id={env['id']}")
    print("  Next steps (not done by this command):")
    print(f"    1. In the Console, open environment {env['id']} and click "
          f"'Generate environment key'")
    print(f"    2. Run a worker with ANTHROPIC_ENVIRONMENT_ID={env['id']} and "
          f"ANTHROPIC_ENVIRONMENT_KEY set — e.g. `ant beta:worker poll` or the "
          f"EnvironmentWorker SDK helper")
    print(f"    3. Check --agent-env-work-stats {env['id']} for "
          f"workers_polling > 0 before pointing a session at it")
    return env


def cmd_agent_env_work_stats(environment_id: str, api_key: str) -> dict:
    """Print the self-hosted work queue's state for `environment_id`
    (public beta, v1.26.0) — how many items are waiting (depth), how many
    a worker already claimed (pending), and whether a worker is actually
    connected (workers_polling; 0 means sessions will queue forever
    instead of failing, since a session against a workerless self-hosted
    environment just waits rather than erroring)."""
    mac = ManagedAgentsClient(api_key)
    stats = mac.get_environment_work_stats(environment_id)
    print(f"\033[94mℹ work queue stats for {environment_id}\033[0m")
    print(f"  depth={stats['depth']}  pending={stats['pending']}  "
          f"workers_polling={stats['workers_polling']}  "
          f"oldest_queued_at={stats['oldest_queued_at']}")
    if stats["workers_polling"] == 0:
        print("  \033[93m⚠ no worker has polled in the last 30s — sessions "
              "routed here will queue, not fail\033[0m")
    return stats


def cmd_agent_webhook_register(url: str, api_key: str, events: Optional[list] = None) -> dict:
    mac = ManagedAgentsClient(api_key)
    webhook = mac.register_webhook(url, event_types=events)
    print(f"\033[92m✓ webhook registered\033[0m  id={webhook['id']}  url={url}")
    if events:
        print(f"  events: {', '.join(events)}")
    return webhook


def cmd_agent_review_multiagent(path: str, specialists: list, api_key: str,
                                model: str = "zc-opus-4-8") -> dict:
    """Native Multiagent orchestration (v1.21.0, un-deferred from
    v1.20.0): run named specialist code reviewers (see
    REVIEW_SPECIALIST_PRESETS) as parallel subagents that share one
    sandbox filesystem and one event stream within a single Managed
    Agents session, with a lead/coordinator agent synthesizing one
    combined report. This is the shared-sandbox, cross-subagent-
    visibility case --agent-orchestrate cannot do (that makes
    independent Messages API calls with no shared filesystem)."""
    unknown = [s for s in specialists if s not in REVIEW_SPECIALIST_PRESETS]
    if unknown:
        raise ValueError(
            f"Unknown specialist(s) {unknown}: choose from "
            f"{sorted(REVIEW_SPECIALIST_PRESETS)}"
        )
    mac = ManagedAgentsClient(api_key)
    print(f"\033[94mℹ Creating {len(specialists)} specialist agent(s)…\033[0m")
    specialist_ids = []
    for name in specialists:
        agent = mac.create_agent(
            name=f"review-{name}-{uuid.uuid4().hex[:8]}", model=model,
            system=REVIEW_SPECIALIST_PRESETS[name],
        )
        specialist_ids.append(agent["id"])
        print(f"  {name} -> {agent['id']}")

    coordinator_system = (
        "You are the lead reviewer coordinating specialist subagents "
        f"({', '.join(specialists)}) that all share this sandbox's "
        "filesystem. Delegate the checked-out codebase to each specialist, "
        "wait for their findings, then synthesize one combined report "
        "referencing all of them, organized by severity."
    )
    coordinator = mac.create_agent(
        name=f"review-coordinator-{uuid.uuid4().hex[:8]}", model=model,
        system=coordinator_system,
        multiagent=build_multiagent_config(specialist_ids),
    )
    env  = mac.create_environment(name=f"ai-coder-review-env-{uuid.uuid4().hex[:8]}")
    sess = mac.create_session(coordinator["id"], env["id"],
                              title=f"multiagent review: {path}"[:60])
    print(f"\033[92m✓ session {sess['id']}\033[0m — running review…\n")

    task = (
        f"Review the codebase checked out at {path}. Delegate to the "
        f"{', '.join(specialists)} specialist(s), then synthesize one "
        "combined report referencing all of their findings."
    )
    result = mac.run_task(sess["id"], task)
    print(result["text"])
    return result


def cmd_agent_outcome_rubric_upload(file_path: str, api_key: str, model: str) -> str:
    """Upload a local rubric markdown file once via the Files API and
    print its file_id, so it can be reused across many --agent-outcome
    invocations with --agent-outcome-rubric-file FILE_ID instead of
    re-reading the local file into the request body every time (v1.21.0,
    the file_id form of define_outcome()'s rubric)."""
    from wire.zc_files import FilesAPI
    fa = FilesAPI(api_key=api_key, model=model)
    print(f"\033[94mℹ Uploading rubric {file_path}…\033[0m")
    result = fa.upload(file_path)
    print(f"\033[92m✓ rubric uploaded\033[0m  file_id={result['id']}")
    print(f"  Reuse with: ai-coder --agent-managed-run \"...\" --agent-outcome \"...\" "
          f"--agent-outcome-rubric-file {result['id']}")
    return result["id"]


# ── CLI entry points ───────────────────────────────────────────────────────

def cmd_agent_chat(prompt: str, api_key: str, model: str,
                   session_id: Optional[str] = None, new: bool = False):
    if session_id and not new:
        try:
            session = AgentSession.load(session_id)
            print(f"\033[94mℹ Resumed session: {session.name} ({len(session.history)} turns)\033[0m\n")
        except FileNotFoundError:
            session = AgentSession(session_id=session_id)
            print(f"\033[94mℹ Created new session: {session.id}\033[0m\n")
    else:
        session = AgentSession()
        print(f"\033[94mℹ New session: {session.id}\033[0m\n")

    agent  = ManagedAgent(api_key=api_key, model=model)
    result = agent.chat(prompt, session)
    print(result)
    print(f"\n\033[90m[session: {session.id}  turns: {len(session.history)//2}]\033[0m")
    print(f"\033[90m  Resume: ai-coder --agent-session {session.id} -p \"follow-up\"\033[0m")
    return result


def cmd_agent_orchestrate(goal: str, api_key: str, model: str, session_id: Optional[str] = None):
    session = AgentSession(session_id=session_id) if session_id else AgentSession()
    agent   = ManagedAgent(api_key=api_key, model=model)
    result  = agent.orchestrate(goal, session)
    print("\n\033[92m✓ Orchestration complete\033[0m\n")
    print(result["final"])
    return result


def cmd_agent_list_sessions():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    sessions = sorted(SESSIONS_DIR.glob("*.json"))
    if not sessions:
        print("No saved sessions.")
        return
    print(f"\n{'ID':<16}{'NAME':<25}{'TURNS':<8}{'UPDATED'}")
    print("─" * 60)
    for sf in sessions[-20:]:
        try:
            d     = json.loads(sf.read_text())
            turns = len(d.get("history", [])) // 2
            print(f"{d['id']:<16}{d.get('name','')[:24]:<25}{turns:<8}{d.get('updated_at','')[:10]}")
        except Exception:
            pass


def cmd_list_tool_presets():
    print("\nAgent tool presets:")
    for name, tools in TOOL_PRESETS.items():
        print(f"  {name:<14} — {', '.join(tools)}")