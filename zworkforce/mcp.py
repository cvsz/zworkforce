from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from .prometa import install_prometa_catalog
from .security import AuthManager

MCP_PROTOCOL_VERSION = "2026-07-28"


class MCPError(RuntimeError):
    pass


MCP_TOOLS: dict[str, dict[str, Any]] = {
    "workforce.submit_task": {
        "name": "workforce.submit_task",
        "description": "Submit a bounded zWorkforce task to a tenant agent.",
        "inputSchema": {"type": "object", "properties": {
            "agent_id": {"type": "string"}, "prompt": {"type": "string"}, "mutating": {"type": "boolean"},
            "tier": {"type": "string", "enum": ["luna", "terra", "sol"]}, "priority": {"type": "integer"}},
            "required": ["agent_id", "prompt"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    "workforce.get_task": {
        "name": "workforce.get_task", "description": "Read a zWorkforce task by id.",
        "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "workforce.search_memory": {
        "name": "workforce.search_memory", "description": "Search tenant semantic memory.",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "agent_id": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "workforce.run_workflow": {
        "name": "workforce.run_workflow", "description": "Start a versioned workflow DAG.",
        "inputSchema": {"type": "object", "properties": {"workflow_id": {"type": "string"}, "input": {"type": "object"}}, "required": ["workflow_id"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    "workforce.emit_event": {
        "name": "workforce.emit_event", "description": "Emit a durable event for event-triggered workflows and agents.",
        "inputSchema": {"type": "object", "properties": {"event_type": {"type": "string"}, "source": {"type": "string"}, "dedupe_key": {"type": "string"}, "payload": {"type": "object"}}, "required": ["event_type", "payload"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    "workforce.install_prometa": {
        "name": "workforce.install_prometa",
        "description": "Install the built-in ProMeta agents, skills, agent templates and workflows for the tenant.",
        "inputSchema": {"type": "object", "properties": {"sign_skills": {"type": "boolean"}}},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
}


def handle_mcp(app, principal, tenant_id: str, request: dict[str, Any], header_method: str = "", header_name: str = "") -> dict[str, Any]:
    request_id = request.get("id")
    method = str(request.get("method") or "")
    if header_method and header_method != method:
        return _error(request_id, -32600, "Mcp-Method header does not match JSON-RPC method")
    params = request.get("params") or {}
    if not isinstance(params, dict):
        return _error(request_id, -32602, "params must be an object")
    if method in {"initialize", "server/discover"}:
        return _result(request_id, _server_metadata())
    if method == "notifications/initialized":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, {"tools": [MCP_TOOLS[name] for name in sorted(MCP_TOOLS)]})
    if method != "tools/call":
        return _error(request_id, -32601, "method not found")
    name = str(params.get("name") or header_name or "")
    if header_name and name != header_name:
        return _error(request_id, -32602, "Mcp-Name header does not match tool name")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        return _error(request_id, -32602, "tool arguments must be an object")
    try:
        value = _call_tool(app, principal, tenant_id, name, arguments)
        return _result(request_id, {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, default=str)}], "structuredContent": value, "isError": False})
    except PermissionError as exc:
        return _result(request_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
    except (ValueError, KeyError) as exc:
        return _result(request_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})


def _call_tool(app, principal, tenant_id: str, name: str, args: dict[str, Any]) -> Any:
    if name == "workforce.get_task":
        _require(principal, "viewer", "workforce:read")
        task = app.db.get_task(tenant_id, str(args.get("task_id", "")))
        if not task:
            raise ValueError("task not found")
        return task
    if name == "workforce.search_memory":
        _require(principal, "viewer", "workforce:read")
        return {"items": app.rag.search(tenant_id, str(args.get("query", "")), str(args.get("agent_id")) if args.get("agent_id") else None, int(args.get("limit", 10)))}
    if name == "workforce.submit_task":
        _require(principal, "operator", "task:write")
        task, created = app.engine.submit(tenant_id, str(args.get("agent_id", "")), str(args.get("prompt", "")), actor=principal.name,
                                          mutating=bool(args.get("mutating", False)), tier_override=args.get("tier"), priority=int(args.get("priority", 0)))
        return {"created": created, "task": task}
    if name == "workforce.run_workflow":
        _require(principal, "operator", "automation:write")
        return app.workflows.start(tenant_id, str(args.get("workflow_id", "")), args.get("input") or {}, principal.name)
    if name == "workforce.emit_event":
        _require(principal, "operator", "automation:write")
        payload = args.get("payload") or {}
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        return app.db.emit_event(tenant_id, str(args.get("event_type", "")), str(args.get("source") or "mcp"), payload, str(args.get("dedupe_key") or ""))
    if name == "workforce.install_prometa":
        _require(principal, "admin", "agent:write")
        sign_skills = bool(args.get("sign_skills", False))
        if sign_skills and not app.settings.skill_signing_key:
            raise ValueError("skill signing key is required when sign_skills is true")
        result = install_prometa_catalog(app.db, tenant_id, principal.name,
                                         signing_key=app.settings.skill_signing_key, sign_skills=sign_skills)
        app.db.audit(tenant_id, principal.name, "prometa.mcp_install", "prometa", "default", result)
        return result
    raise ValueError(f"unknown MCP tool: {name}")


def _require(principal, role: str, scope: str) -> None:
    if not AuthManager.require(principal, role, scope):
        raise PermissionError(f"{role} role and {scope} scope required")


def _version() -> str:
    from . import __version__
    return __version__


def _server_metadata() -> dict[str, Any]:
    return {"protocolVersion": MCP_PROTOCOL_VERSION, "serverInfo": {"name": "zworkforce", "version": _version()}, "capabilities": {"tools": {}}}


def _result(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id, code: int, message: str):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


class RemoteMCPClient:
    """Stateless MCP 2026-07-28 HTTP client."""
    def __init__(self, endpoint: str, bearer_token: str = "", timeout: int = 30, client_name: str = "zworkforce"):
        parsed = urllib.parse.urlsplit(endpoint)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise MCPError("MCP endpoint must be an HTTP(S) URL")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise MCPError("remote MCP endpoints must use HTTPS")
        self.endpoint, self.bearer_token, self.timeout, self.client_name = endpoint, bearer_token, timeout, client_name
        self._counter = 0

    def request(self, method: str, params: dict[str, Any] | None = None, tool_name: str = "") -> Any:
        self._counter += 1
        params = dict(params or {})
        meta = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
        meta["io.modelcontextprotocol/clientInfo"] = {"name": self.client_name, "version": _version()}
        params["_meta"] = meta
        body = {"jsonrpc": "2.0", "id": self._counter, "method": method, "params": params}
        headers = {"Content-Type": "application/json", "Accept": "application/json", "MCP-Protocol-Version": MCP_PROTOCOL_VERSION, "Mcp-Method": method}
        if tool_name:
            headers["Mcp-Name"] = tool_name
        if self.bearer_token:
            headers["Authorization"] = "Bearer " + self.bearer_token
        req = urllib.request.Request(self.endpoint, data=json.dumps(body, separators=(",", ":")).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read(8_388_608))
        except Exception as exc:
            raise MCPError("MCP request failed") from exc
        if data.get("error"):
            raise MCPError(str(data["error"].get("message") or data["error"]))
        return data.get("result")

    def discover(self):
        return self.request("server/discover")

    def list_tools(self):
        return self.request("tools/list")

    def call_tool(self, name: str, arguments: dict[str, Any]):
        return self.request("tools/call", {"name": name, "arguments": arguments}, name)
