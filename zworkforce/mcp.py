from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from .prometa import install_prometa_catalog
from . import samsung_tv
from . import samsung_compat
from . import samsung_sdk_probe
from . import samsung_builder_preflight
from . import samsung_manifest
from . import cloudflare_api
from . import cloudflare_live
from .security import AuthManager

MCP_PROTOCOL_VERSION = "2026-07-28"
MCP_LEGACY_PROTOCOL_VERSION = "2025-11-25"
MCP_LEGACY_PROTOCOL_VERSIONS = (
    MCP_LEGACY_PROTOCOL_VERSION,
    "2025-06-18",
    "2025-03-26",
)
MCP_SUPPORTED_PROTOCOL_VERSIONS = (MCP_PROTOCOL_VERSION, *MCP_LEGACY_PROTOCOL_VERSIONS)
MCP_PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
MCP_CLIENT_INFO_META_KEY = "io.modelcontextprotocol/clientInfo"
MCP_CLIENT_CAPABILITIES_META_KEY = "io.modelcontextprotocol/clientCapabilities"
MCP_SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo"


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
    "samsung.builder_preflight": {
        "name": "samsung.builder_preflight",
        "description": "Non-executing builder prerequisite assessment; never verifies signing or builds packages.",
        "inputSchema": {"type": "object", "properties": {
            "model": {"type": "string", "minLength": 2, "maxLength": 64},
            "model_year": {"type": "integer", "minimum": 2010, "maximum": 2026}},
            "required": ["model", "model_year"], "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "samsung.sdk_environment": {
        "name": "samsung.sdk_environment",
        "description": "Inspect server-side Samsung SDK environment configuration without executing tools.",
        "inputSchema": {"type": "object", "properties": {
            "platform": {"type": "string", "enum": ["samsung-legacy", "tizen"]}},
            "required": ["platform"], "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "samsung.source_manifest": {
        "name": "samsung.source_manifest",
        "description": "Validate operator-supplied unverified package license/hash metadata without fetching releases.",
        "inputSchema": {"type": "object", "properties": {
            "model": {"type": "string", "minLength": 2, "maxLength": 64, "pattern": "^[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$"},
            "packages": {"type": "array", "maxItems": 100, "items": {
                "type": "object", "properties": {
                    "name": {"type": "string", "minLength": 2, "maxLength": 64, "pattern": "^[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$"},
                    "license": {"type": "string", "minLength": 1, "maxLength": 100, "pattern": "^[A-Za-z0-9][A-Za-z0-9.+-]{0,99}$"},
                    "sha256": {"type": "string", "pattern": "^[a-fA-F0-9]{64}$"}},
                "required": ["name", "license", "sha256"], "additionalProperties": False}}},
            "required": ["model", "packages"], "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "samsung.compatibility": {
        "name": "samsung.compatibility",
        "description": "Offline Samsung TV platform advisory using an explicitly supplied model year; never verifies hardware.",
        "inputSchema": {"type": "object", "properties": {
            "model": {"type": "string", "minLength": 2, "maxLength": 64},
            "model_year": {"type": "integer", "minimum": 2010, "maximum": 2026}},
            "required": ["model", "model_year"], "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "samsung.sources": {
        "name": "samsung.sources",
        "description": "List curated official Samsung Smart TV documentation and open-source release URLs (not live search).",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "samsung.model_guidance": {
        "name": "samsung.model_guidance",
        "description": "Return safe unverified model investigation steps and official Samsung source locations.",
        "inputSchema": {"type": "object", "properties": {"model": {"type": "string", "minLength": 2, "maxLength": 64}}, "required": ["model"], "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "cloudflare.live_inventory": {
        "name": "cloudflare.live_inventory",
        "description": "Read bounded Cloudflare inventory for a server-configured tenant and resource allowlist.",
        "inputSchema": {"type": "object", "properties": {
            "resource": {"type": "string", "enum": ["zones", "dns_records", "tunnels"]},
            "resource_id": {"type": "string", "pattern": "^[a-fA-F0-9]{32}$"},
            "page": {"type": "integer", "minimum": 1, "maximum": 10}},
            "required": ["resource"], "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    "cloudflare.references": {
        "name": "cloudflare.references",
        "description": "List vetted official Cloudflare API docs and authentication references without making API calls.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "cloudflare.operation_plan": {
        "name": "cloudflare.operation_plan",
        "description": "Describe allowlisted Cloudflare API operations, minimum permissions and safety gates; never executes.",
        "inputSchema": {"type": "object", "properties": {
            "operation": {"type": "string", "minLength": 3, "maxLength": 64}},
            "required": ["operation"], "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
}


def mcp_protocol_version(request: dict[str, Any], header_version: str = "") -> str | None:
    method = str(request.get("method") or "")
    params = request.get("params") if isinstance(request.get("params"), dict) else {}
    if method == "initialize":
        # Modern revisions use discovery. Legacy initialization counter-offers
        # the newest handshake revision for unsupported or modern proposals.
        requested = str(params.get("protocolVersion") or "")
        return requested if requested in MCP_LEGACY_PROTOCOL_VERSIONS else MCP_LEGACY_PROTOCOL_VERSION

    meta = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
    meta_version = str(meta.get(MCP_PROTOCOL_VERSION_META_KEY) or "")
    if header_version == MCP_PROTOCOL_VERSION or meta_version == MCP_PROTOCOL_VERSION:
        if not isinstance(meta.get(MCP_CLIENT_CAPABILITIES_META_KEY), dict):
            return None
    if header_version and meta_version and header_version != meta_version:
        return None
    version = header_version or meta_version or MCP_LEGACY_PROTOCOL_VERSION
    if version == MCP_PROTOCOL_VERSION and header_version != MCP_PROTOCOL_VERSION:
        return None
    if version == MCP_PROTOCOL_VERSION and meta_version != MCP_PROTOCOL_VERSION:
        return None
    return version if version in MCP_SUPPORTED_PROTOCOL_VERSIONS else None


def handle_mcp(
    app,
    principal,
    tenant_id: str,
    request: dict[str, Any],
    header_method: str = "",
    header_name: str = "",
    protocol_version: str | None = None,
) -> dict[str, Any] | None:
    request_id = request.get("id")
    method = str(request.get("method") or "")
    params = request.get("params") or {}
    if not isinstance(params, dict):
        return _error(request_id, -32602, "params must be an object")
    if protocol_version is None:
        return _error(request_id, -32022, "unsupported or mismatched MCP protocol version")
    if protocol_version == MCP_PROTOCOL_VERSION:
        if not header_method or header_method != method:
            return _error(request_id, -32020, "Mcp-Method header is required and must match the JSON-RPC method")
        expected_name = _mcp_header_name(method, params)
        if expected_name is not None and (not expected_name or header_name != expected_name):
            return _error(request_id, -32020, "Mcp-Name header is required and must match the JSON-RPC request")
    elif header_method and header_method != method:
        return _error(request_id, -32600, "Mcp-Method header does not match JSON-RPC method")
    if method == "initialize":
        if protocol_version not in MCP_LEGACY_PROTOCOL_VERSIONS:
            return _error(request_id, -32022, "initialize requires a legacy handshake version")
        return _result(request_id, _legacy_server_metadata(protocol_version))
    if method == "server/discover":
        if protocol_version != MCP_PROTOCOL_VERSION:
            return _error(request_id, -32601, "method not found")
        return _result(request_id, _modern_server_metadata())
    if method.startswith("notifications/"):
        return None
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
    if name == "cloudflare.live_inventory":
        _require(principal, "viewer", "workforce:read")
        if set(args) - {"resource", "resource_id", "page"} or not isinstance(args.get("resource"), str):
            raise ValueError("Invalid Cloudflare read arguments")
        if not isinstance(args.get("resource_id", ""), str):
            raise ValueError("Invalid Cloudflare resource ID")
        resource = args["resource"]
        resource_id = args.get("resource_id", "")
        page = args.get("page", 1)
        # Log only non-secret identifiers and outcome. Audit writes are mandatory.
        if app is None or not hasattr(app, "db") or not hasattr(app.db, "audit"):
            raise ValueError("Cloudflare inventory requires an audit-capable database")
        try:
            value = cloudflare_live.read(tenant_id, resource, resource_id, page)
        except (ValueError, PermissionError):
            app.db.audit(tenant_id, principal.name, "cloudflare.inventory.read", resource,
                         resource_id, {"outcome": "denied_or_failed", "page": page})
            raise
        app.db.audit(tenant_id, principal.name, "cloudflare.inventory.read", resource,
                     resource_id, {"outcome": "success", "page": page, "item_count": len(value["items"])})
        return value
    if name == "cloudflare.references":
        _require(principal, "viewer", "workforce:read")
        if args:
            raise ValueError("cloudflare.references does not accept arguments")
        return cloudflare_api.references()
    if name == "cloudflare.operation_plan":
        _require(principal, "viewer", "workforce:read")
        if set(args) != {"operation"} or not isinstance(args.get("operation"), str):
            raise ValueError("cloudflare.operation_plan requires a string operation")
        return cloudflare_api.operation_plan(args["operation"])
    if name == "samsung.builder_preflight":
        _require(principal, "viewer", "workforce:read")
        if set(args) != {"model", "model_year"}:
            raise ValueError("model and model_year required")
        return samsung_builder_preflight.assess(args["model"], args["model_year"])
    if name == "samsung.sdk_environment":
        _require(principal, "viewer", "workforce:read")
        if set(args) != {"platform"} or not isinstance(args["platform"], str):
            raise ValueError("platform is required")
        return samsung_sdk_probe.inspect_environment(args["platform"])
    if name == "samsung.source_manifest":
        _require(principal, "viewer", "workforce:read")
        if set(args) != {"model", "packages"}:
            raise ValueError("model and packages required")
        return samsung_manifest.analyze(args["model"], args["packages"])
    if name == "samsung.compatibility":
        _require(principal, "viewer", "workforce:read")
        if set(args) != {"model", "model_year"}:
            raise ValueError("model and model_year are required")
        return samsung_compat.compatibility(args["model"], args["model_year"])
    if name == "samsung.sources":
        _require(principal, "viewer", "workforce:read")
        if args:
            raise ValueError("samsung.sources does not accept arguments")
        return samsung_tv.sources()
    if name == "samsung.model_guidance":
        _require(principal, "viewer", "workforce:read")
        if set(args) != {"model"} or not isinstance(args.get("model"), str):
            raise ValueError("samsung.model_guidance requires a string model")
        return samsung_tv.model_guidance(args["model"])
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


def _server_info() -> dict[str, str]:
    return {"name": "zworkforce", "version": _version()}


def _legacy_server_metadata(protocol_version: str) -> dict[str, Any]:
    return {
        "protocolVersion": protocol_version,
        "serverInfo": _server_info(),
        "capabilities": {"tools": {}},
    }


def _modern_server_metadata() -> dict[str, Any]:
    return {
        "capabilities": {"tools": {}},
        "supportedVersions": list(MCP_SUPPORTED_PROTOCOL_VERSIONS),
        "_meta": {MCP_SERVER_INFO_META_KEY: _server_info()},
    }


def add_modern_mcp_metadata(response: dict[str, Any], method: str) -> None:
    result = response.get("result")
    if not isinstance(result, dict):
        return
    result.setdefault("resultType", "complete")
    meta = result.get("_meta")
    if not isinstance(meta, dict):
        meta = {}
        result["_meta"] = meta
    meta.setdefault(MCP_SERVER_INFO_META_KEY, _server_info())
    if method in {"server/discover", "tools/list"}:
        result.setdefault("ttlMs", 0)
        result.setdefault("cacheScope", "private")


def _mcp_header_name(method: str, params: dict[str, Any]) -> str | None:
    if method in {"tools/call", "prompts/get"}:
        value = params.get("name")
    elif method == "resources/read":
        value = params.get("uri")
    else:
        return None
    return str(value) if value is not None else ""


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
        meta[MCP_PROTOCOL_VERSION_META_KEY] = MCP_PROTOCOL_VERSION
        meta[MCP_CLIENT_INFO_META_KEY] = {"name": self.client_name, "version": _version()}
        meta.setdefault(MCP_CLIENT_CAPABILITIES_META_KEY, {})
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
