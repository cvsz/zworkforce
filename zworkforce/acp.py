from __future__ import annotations

import json
from typing import Any

ACP_PROTOCOL_VERSION = "2026-02-18"


class ACPError(RuntimeError):
    """Raised when an ACP request fails protocol or validation checks."""
    def __init__(self, message: str, code: int = -32603, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


def handle_acp(
    app,
    principal,
    tenant_id: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    """Handles JSON-RPC requests conforming to the Agent Client Protocol (ACP) standard."""
    request_id = request.get("id")
    method = str(request.get("method") or "").strip()
    params = request.get("params") or {}

    if not method:
        return _acp_err(request_id, -32600, "Invalid Request: method is required")

    try:
        if method == "initialize":
            return _acp_ok(request_id, {
                "protocolVersion": ACP_PROTOCOL_VERSION,
                "agentInfo": {
                    "name": "zWorkforce-Agent",
                    "version": "3.0.4",
                    "capabilities": {
                        "sessions": True,
                        "tools": True,
                        "streaming": True,
                        "prompts": True,
                        "modelRouting": "free_first",
                    },
                },
            })

        if method == "authenticate":
            # Verification already passed via standard API authentication bearer
            return _acp_ok(request_id, {
                "authenticated": True,
                "tenantId": tenant_id,
                "principal": principal.name,
                "role": principal.role,
            })

        if method == "newSession":
            agent_id = str(params.get("agentId") or "researcher")
            prompt = str(params.get("initialPrompt") or "ACP Session Initialized")
            # Create a session conversation under the authenticated tenant
            conv = app.db.create_workspace_conversation(
                tenant_id,
                principal.name,
                project_id=params.get("projectId"),
                title=f"ACP Session ({agent_id})",
            )
            return _acp_ok(request_id, {
                "sessionId": conv["id"],
                "agentId": agent_id,
                "tenantId": tenant_id,
                "createdAt": conv["created_at"],
            })

        if method == "loadSession":
            session_id = str(params.get("sessionId") or "")
            if not session_id:
                return _acp_err(request_id, -32602, "sessionId is required")
            conv = app.db.get_workspace_conversation(tenant_id, session_id)
            if not conv:
                return _acp_err(request_id, -32004, "Session not found")
            messages = app.db.list_workspace_messages(tenant_id, session_id, limit=100)
            return _acp_ok(request_id, {
                "session": conv,
                "messages": messages,
            })

        if method == "prompt":
            session_id = str(params.get("sessionId") or "")
            content = str(params.get("content") or "").strip()
            agent_id = str(params.get("agentId") or "researcher")
            mutating = bool(params.get("mutating", False))
            if not content:
                return _acp_err(request_id, -32602, "content is required")

            # Route task prioritizing free models
            task, created = app.engine.submit(
                tenant_id=tenant_id,
                agent_id=agent_id,
                prompt=content,
                actor=principal.name,
                mutating=mutating,
            )
            return _acp_ok(request_id, {
                "taskId": task["id"],
                "status": task["status"],
                "tier": task["tier"],
                "model": task["model"],
                "created": created,
            })

        if method == "cancel":
            task_id = str(params.get("taskId") or "")
            if not task_id:
                return _acp_err(request_id, -32602, "taskId is required")
            task = app.engine.cancel(tenant_id, task_id, principal.name)
            return _acp_ok(request_id, {"taskId": task_id, "status": task.get("status", "canceled")})

        if method == "requestPermission":
            task_id = str(params.get("taskId") or "")
            decision = str(params.get("decision") or "approve").lower()
            comment = str(params.get("comment") or "")
            if decision == "approve":
                task = app.engine.approve(tenant_id, task_id, principal.name, comment)
            else:
                task = app.engine.reject(tenant_id, task_id, principal.name, comment)
            return _acp_ok(request_id, {"taskId": task_id, "status": task["status"]})

        return _acp_err(request_id, -32601, f"Method not found: {method}")

    except Exception as exc:
        return _acp_err(request_id, -32603, f"Internal error: {str(exc)}")


def _acp_ok(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _acp_err(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": err}
