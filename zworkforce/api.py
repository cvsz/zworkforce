from __future__ import annotations

import base64
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import urllib.parse
import uuid
from typing import Any

from . import __version__
from .artifacts import build_artifact_store
from .economics import capacity_forecast, chargeback_report, slo_status
from .evaluation_suite import EvaluationRunner
from .metrics import prometheus
from .mcp import MCP_PROTOCOL_VERSION, handle_mcp
from .acp import ACP_PROTOCOL_VERSION, handle_acp
from .policy import PolicyError, validate_policy
from .prometa import install_prometa_catalog
from .rag import build_semantic_memory
from .scheduler import Scheduler
from .security import AuthManager, RateLimiter, resolve_tenant
from .skills import SkillError, validate_manifest, verify_manifest
from .tools import TOOL_DEFINITIONS
from .workflow import WorkflowOrchestrator
from .zarvis_voice import ZarvisVoiceError, build_zarvis_voice_service, ZarvisLiveVoiceService, build_zarvis_voice_services

AGENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
STATIC_CONTENT_TYPES = {
    "index.html": "text/html; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "styles.css": "text/css; charset=utf-8",
    "zarvis-voice-worklet.js": "text/javascript; charset=utf-8",
}


def _sanitize_header_value(value: str) -> str:
    return value.replace("\r", "").replace("\n", "")


def _sanitize_error(error: str) -> str:
    import re
    sanitized = re.sub(r"/[^\s:]+\.py:\d+", "<file>", error)
    sanitized = re.sub(r"Traceback \(most recent call last\):.*", "internal error", sanitized, flags=re.DOTALL)
    sanitized = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<uuid>", sanitized)
    return sanitized[:500] if sanitized else "internal server error"


class App:
    def __init__(self, settings, db, engine, auth: AuthManager, provider):
        self.settings = settings
        self.db = db
        self.engine = engine
        self.auth = auth
        self.provider = provider
        self.static = Path(__file__).parent / "static"
        self.rate_limiter = RateLimiter(settings.api_rate_limit_per_minute)
        self.auth_rate_limiter = RateLimiter(max(60, settings.api_rate_limit_per_minute * 2))
        self.workflows = WorkflowOrchestrator(db, engine)
        self.scheduler = Scheduler(db, engine)
        self.evaluations = EvaluationRunner(db, engine)
        self.rag = build_semantic_memory(db)
        self.artifacts = build_artifact_store(settings, db)
        self.voice = build_zarvis_voice_service()
        self.live_voice = ZarvisLiveVoiceService()

    def handler(self):
        app = self

        class Handler(BaseHTTPRequestHandler):
            server_version = f"zWorkforce/{__version__}"

            def setup(self):
                super().setup()
                self.request_id = uuid.uuid4().hex
                self._cors_origin = ""

            def log_message(self, fmt, *args):
                print(json.dumps({"event": "http", "request_id": self.request_id, "client": self.client_address[0], "message": fmt % args},
                                 separators=(",", ":")), flush=True)

            def _prepare(self):
                rid = _sanitize_header_value(self.headers.get("X-Request-ID", ""))
                self.request_id = rid if REQUEST_ID_RE.fullmatch(rid) else uuid.uuid4().hex
                origin = _sanitize_header_value(self.headers.get("Origin", ""))
                self._cors_origin = origin if origin and origin in app.settings.cors_origins else ""

            def _security_headers(self, cache_control: str = "no-store"):
                self.send_header("Cache-Control", cache_control)
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                microphone_policy = "microphone=(self)" if (app.voice.microphone_enabled or app.live_voice.config.enabled) else "microphone=()"
                self.send_header("Permissions-Policy", f"camera=(), {microphone_policy}, geolocation=()")
                connect_sources = " ".join(("'self'", *app.voice.csp_connect_sources, *app.live_voice.csp_connect_sources))
                self.send_header("Content-Security-Policy", f"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src {connect_sources}; frame-ancestors 'none'; base-uri 'none'")
                self.send_header("X-Request-ID", _sanitize_header_value(self.request_id))
                if self._cors_origin:
                    self.send_header("Access-Control-Allow-Origin", _sanitize_header_value(self._cors_origin))
                    self.send_header("Vary", "Origin")

            def _json(self, status: int, data: Any, headers: dict[str, str] | None = None):
                payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self._security_headers()
                for k, v in (headers or {}).items():
                    self.send_header(k, _sanitize_header_value(str(v)))
                self.end_headers()
                self.wfile.write(payload)

            def _error(self, status: int, code: str, message: str, details: Any = None):
                body = {"error": {"code": code, "message": message}, "request_id": self.request_id}
                if details is not None and app.settings.env != "production":
                    body["error"]["details"] = details
                return self._json(status, body)

            def _body(self) -> dict[str, Any]:
                try:
                    n = int(self.headers.get("Content-Length", "0"))
                except ValueError as exc:
                    raise ValueError("invalid Content-Length") from exc
                if n < 0 or n > app.settings.max_request_bytes:
                    raise ValueError("request body too large")
                if n == 0:
                    return {}
                if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                    raise ValueError("Content-Type must be application/json")
                try:
                    data = json.loads(self.rfile.read(n))
                except json.JSONDecodeError as exc:
                    raise ValueError("invalid JSON") from exc
                if not isinstance(data, dict):
                    raise ValueError("JSON body must be an object")
                return data

            def _principal(self, role: str, scope: str | None = None):
                allowed, retry_after = app.auth_rate_limiter.allow(f"auth:{self.client_address[0]}")
                if not allowed:
                    self._json(429, {"error": {"code": "auth_rate_limited", "message": "authentication rate limit exceeded"},
                                     "request_id": self.request_id}, {"Retry-After": str(retry_after)})
                    return None, True
                proxy_headers = {k: self.headers.get(k, "") for k in (
                    "X-Forwarded-User", "X-Forwarded-Role", "X-Forwarded-Tenant", "X-Forwarded-Scopes",
                    "X-ZWorkforce-Proxy-Signature", "X-ZWorkforce-Proxy-Timestamp")}
                principal = app.auth.authenticate(self.headers.get("Authorization"), self.headers.get("X-API-Key"), proxy_headers)
                if not app.auth.require(principal, role, scope):
                    self._error(401 if principal is None else 403, "auth_failed", "authentication, role, or scope requirement failed")
                    return None, True
                allowed, retry_after = app.rate_limiter.allow(f"{principal.key_id}:{self.client_address[0]}")
                if not allowed:
                    self._json(429, {"error": {"code": "rate_limited", "message": "API rate limit exceeded"},
                                     "request_id": self.request_id}, {"Retry-After": str(retry_after)})
                    return None, True
                try:
                    tenant_id = resolve_tenant(principal, self.headers.get("X-Tenant-ID"))
                except ValueError as exc:
                    self._error(400, "invalid_tenant", str(exc)); return None, True
                if not app.db.get_tenant(tenant_id):
                    self._error(404, "tenant_not_found", "tenant not found"); return None, True
                return (principal, tenant_id), None

            def _static(self, name: str):
                path = app.static / name
                if not path.is_file():
                    return self._error(404, "not_found", "not found")
                data = path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", STATIC_CONTENT_TYPES.get(name, "application/octet-stream"))
                self.send_header("Content-Length", str(len(data)))
                self._security_headers("public,max-age=300")
                self.end_headers()
                self.wfile.write(data)

            def _query(self):
                return urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query, keep_blank_values=False)

            def do_OPTIONS(self):
                self._prepare()
                origin = _sanitize_header_value(self.headers.get("Origin", ""))
                if not origin or origin not in app.settings.cors_origins:
                    return self._error(403, "cors_denied", "origin is not allowed")
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Authorization,Content-Type,Idempotency-Key,X-API-Key,X-Request-ID,X-Tenant-ID")
                self.send_header("Access-Control-Max-Age", "600")
                self.send_header("Vary", "Origin")
                self._security_headers()
                self.end_headers()

            def do_GET(self):
                self._prepare()
                path = urllib.parse.urlsplit(self.path).path
                try:
                    if path == "/":
                        return self._static("index.html")
                    if path in {"/app.js", "/styles.css", "/zarvis-voice-worklet.js"}:
                        return self._static(path[1:])
                    if path == "/health":
                        return self._json(200, {"status": "ok", "version": __version__})
                    if path == "/ready":
                        providers = app.provider.models()
                        provider_ready = any(
                            item["available"] and (app.settings.env != "production" or item["kind"] != "mock")
                            for item in providers
                        )
                        ready = app.db.ready() and provider_ready
                        return self._json(200 if ready else 503, {"status": "ready" if ready else "not_ready",
                                                                  "database": app.db.ready(), "database_backend": app.db.backend_kind,
                                                                  "providers": [{"name": p["name"], "available": p["available"]} for p in providers]})
                    if path == "/metrics":
                        ctx, response = self._principal("viewer", "metrics:read")
                        if response: return response
                        _, tenant_id = ctx
                        data = prometheus(app.db, tenant_id).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
                        self.send_header("Content-Length", str(len(data)))
                        self._security_headers(); self.end_headers(); self.wfile.write(data); return
                    return self._get_api(path)
                except (ValueError, TypeError, SkillError) as exc:
                    return self._error(400, "invalid_request", str(exc))
                except Exception as exc:
                    return self._error(500, "internal_error", "internal server error", str(exc))

            def _get_api(self, path: str):
                q = self._query()
                if path == "/api/v1/zarvis/voice":
                    ctx, response = self._principal("viewer", "voice:use")
                    if response: return response
                    snapshot = app.voice.snapshot()
                    snapshot.update(app.live_voice.snapshot())
                    return self._json(200, snapshot)
                if path == "/api/v1/tenants":
                    ctx, response = self._principal("superadmin", "tenant:read")
                    if response: return response
                    return self._json(200, {"items": app.db.list_tenants()})
                if path == "/api/v1/audit/verify":
                    ctx, response = self._principal("admin", "audit:verify")
                    if response: return response
                    _, tenant_id = ctx
                    return self._json(200, app.db.verify_audit_chain(tenant_id))
                if path == "/api/v1/audit":
                    ctx, response = self._principal("admin", "audit:read")
                    if response: return response
                    _, tenant_id = ctx
                    return self._json(200, {"items": app.db.list_audit(tenant_id, _intq(q, "limit", 100), _intq(q, "offset", 0))})
                if path == "/api/v1/api-keys":
                    ctx, response = self._principal("admin", "key:read")
                    if response: return response
                    _, tenant_id = ctx
                    return self._json(200, {"items": app.db.list_api_keys(tenant_id)})
                if path == "/api/v1/tool-events":
                    ctx, response = self._principal("admin", "audit:read")
                    if response: return response
                    _, tenant_id = ctx
                    return self._json(200, {"items": app.db.list_tool_events(tenant_id, _strq(q, "task_id") or None, _intq(q, "limit", 100))})

                ctx, response = self._principal("viewer", "workforce:read")
                if response: return response
                _, tenant_id = ctx
                if path == "/api/v1/overview": return self._json(200, app.db.overview(tenant_id))
                if path == "/api/v1/agents": return self._json(200, {"items": app.db.list_agents(tenant_id)})
                if path == "/api/v1/agent-templates": return self._json(200, {"items": app.db.list_agent_templates(tenant_id)})
                if path == "/api/v1/policies": return self._json(200, {"items": app.db.list_policies(tenant_id)})
                agent_versions = re.fullmatch(r"/api/v1/agents/([a-z0-9][a-z0-9-]{0,62})/versions", path)
                if agent_versions:
                    return self._json(200, {"items": app.db.list_agent_versions(tenant_id, agent_versions.group(1), _intq(q,"limit",100))})
                if path == "/api/v1/tasks":
                    return self._json(200, {"items": app.db.list_tasks(tenant_id, _intq(q,"limit",100), _intq(q,"offset",0),
                                                                      _strq(q,"status") or None, _strq(q,"agent_id") or None)})
                if path == "/api/v1/budgets": return self._json(200, {"items": app.db.list_budgets(tenant_id)})
                if path == "/api/v1/providers": return self._json(200, {"items": app.provider.models()})
                if path == "/api/v1/models":
                    return self._json(200, {"tiers": [{"tier": tier, "rate": app.settings.rates[tier].__dict__,
                                                       "provider_preview": dict(zip(("provider","model"), app.provider.preview(tier)))}
                                                      for tier in ("luna","terra","sol")]})
                if path == "/api/v1/recommendations": return self._json(200, {"items": app.db.recommendations(tenant_id, _intq(q,"days",7))})
                if path == "/api/v1/memories":
                    query = _strq(q,"q")
                    items = app.db.search_memories(tenant_id, query, limit=_intq(q,"limit",50)) if query else app.db.list_memories(tenant_id,_intq(q,"limit",100))
                    return self._json(200, {"items": items})
                if path == "/api/v1/skills": return self._json(200, {"items": app.db.list_skills(tenant_id)})
                if path == "/api/v1/tools":
                    return self._json(200, {"items": [{"name": name, "mutating": bool(defn["mutating"]),
                                                       "description": defn["schema"]["function"]["description"]}
                                                      for name, defn in TOOL_DEFINITIONS.items()]})
                match = re.fullmatch(r"/api/v1/tasks/([0-9a-f-]+)(?:/(events|approvals))?", path)
                if match:
                    task_id, suffix = match.group(1), match.group(2)
                    task = app.db.get_task(tenant_id, task_id)
                    if not task: return self._error(404, "task_not_found", "task not found")
                    if suffix == "events": return self._json(200, {"items": app.db.list_task_events(tenant_id, task_id)})
                    if suffix == "approvals": return self._json(200, {"items": app.db.list_approvals(tenant_id, task_id)})
                    return self._json(200, task)

                # v3 automation / economics endpoints
                if path == "/api/v1/workflows": return self._json(200, {"items": app.db.list_workflows(tenant_id)})
                if path == "/api/v1/workflow-runs": return self._json(200, {"items": app.db.list_workflow_runs(tenant_id,_intq(q,"limit",100))})
                if path == "/api/v1/schedules": return self._json(200, {"items": app.db.list_schedules(tenant_id)})
                if path == "/api/v1/event-rules": return self._json(200, {"items": app.db.list_event_rules(tenant_id)})
                if path == "/api/v1/evaluation-suites": return self._json(200, {"items": app.db.list_evaluation_suites(tenant_id)})
                if path == "/api/v1/artifacts": return self._json(200, {"items": app.db.list_artifacts(tenant_id,_intq(q,"limit",100))})
                if path == "/api/v1/slo": return self._json(200, {"items": app.db.list_slo_policies(tenant_id)})
                if path == "/api/v1/slo/status": return self._json(200, slo_status(app.db, tenant_id))
                if path == "/api/v1/chargeback": return self._json(200, chargeback_report(app.db, tenant_id,_intq(q,"hours",720)))
                if path == "/api/v1/capacity": return self._json(200, capacity_forecast(app.db, tenant_id,_intq(q,"hours",24)))
                if path == "/api/v1/rag":
                    query = _strq(q,"q")
                    if not query: raise ValueError("q is required")
                    return self._json(200, {"items": app.rag.search(tenant_id, query, _strq(q,"agent_id") or None,_intq(q,"limit",10))})
                m = re.fullmatch(r"/api/v1/workflow-runs/([0-9a-f-]+)", path)
                if m:
                    run=app.db.get_workflow_run(tenant_id,m.group(1))
                    if not run: return self._error(404,"workflow_run_not_found","workflow run not found")
                    return self._json(200, {**run, "steps": app.db.list_workflow_steps(run["id"])})
                m = re.fullmatch(r"/api/v1/evaluation-runs/([0-9a-f-]+)", path)
                if m:
                    run=app.db.get_evaluation_run(tenant_id,m.group(1))
                    if not run: return self._error(404,"evaluation_run_not_found","evaluation run not found")
                    return self._json(200, {**run, "results": app.db.list_evaluation_results(run["id"])})
                return self._error(404, "not_found", "not found")

            def do_POST(self):
                self._prepare()
                path = urllib.parse.urlsplit(self.path).path
                try:
                    if path == "/mcp":
                        ctx, response = self._principal("viewer", "workforce:read")
                        if response: return response
                        principal, tenant_id = ctx
                        body = self._body()
                        if not isinstance(body, dict): raise ValueError("MCP request must be a JSON object")
                        result = handle_mcp(app, principal, tenant_id, body, self.headers.get("Mcp-Method", ""), self.headers.get("Mcp-Name", ""))
                        return self._json(200, result, {"MCP-Protocol-Version": MCP_PROTOCOL_VERSION})
                    if path == "/acp":
                        ctx, response = self._principal("viewer", "workforce:read")
                        if response: return response
                        principal, tenant_id = ctx
                        body = self._body()
                        if not isinstance(body, dict): raise ValueError("ACP request must be a JSON object")
                        result = handle_acp(app, principal, tenant_id, body)
                        return self._json(200, result, {"ACP-Protocol-Version": ACP_PROTOCOL_VERSION})
                    if path == "/api/v1/zarvis/voice/session":
                        ctx, response = self._principal("viewer", "voice:use")
                        if response: return response
                        principal, tenant_id = ctx
                        body = self._body()
                        try:
                            result = app.voice.issue_session(
                                tenant_id=tenant_id,
                                subject_id=f"{principal.key_id}:{principal.name}"[:256],
                                request_id=self.request_id,
                                model=str(body.get("model") or "") or None,
                            )
                        except ZarvisVoiceError as exc:
                            return self._error(exc.status, exc.code, str(exc))
                        app.db.audit(tenant_id, principal.name, "zarvis.voice.session", "voice_session", self.request_id,
                                     {"expires_at": result["expires_at"], "model": result["model"], "transport": result["transport"]})
                        return self._json(201, result)
                    if path == "/api/v1/zarvis/voice/live-token":
                        ctx, response = self._principal("viewer", "voice:use")
                        if response: return response
                        principal, tenant_id = ctx
                        try:
                            result = app.live_voice.issue_live_token(
                                tenant_id=tenant_id,
                                subject_id=f"{principal.key_id}:{principal.name}"[:256],
                                request_id=self.request_id,
                            )
                        except ZarvisVoiceError as exc:
                            return self._error(exc.status, exc.code, str(exc))
                        app.db.audit(tenant_id, principal.name, "zarvis.voice.live_token", "voice_live_token", self.request_id,
                                     {"expires_at": result["expires_at"], "model": result["model"], "transport": result["transport"]})
                        return self._json(201, result)
                    if path == "/api/v1/tenants":
                        ctx, response = self._principal("superadmin", "tenant:write")
                        if response: return response
                        principal, _ = ctx; body = self._body()
                        tenant_id = str(body.get("id","")).strip().lower()
                        from .security import TENANT_RE
                        if not TENANT_RE.fullmatch(tenant_id): raise ValueError("tenant id must be a DNS-like slug")
                        tenant = app.db.ensure_tenant(tenant_id, str(body.get("name") or tenant_id))
                        app.db.audit(tenant_id, principal.name, "tenant.create", "tenant", tenant_id)
                        return self._json(201, tenant)
                    if path == "/api/v1/api-keys":
                        ctx, response = self._principal("admin", "key:write")
                        if response: return response
                        principal, tenant_id = ctx; body = self._body()
                        target_tenant = str(body.get("tenant_id") or tenant_id)
                        if target_tenant != tenant_id and principal.role != "superadmin": return self._error(403,"cross_tenant_denied","only superadmin can create keys for another tenant")
                        role = str(body.get("role","viewer"))
                        if role == "superadmin" and principal.role != "superadmin": return self._error(403,"role_escalation_denied","only superadmin can create a superadmin key")
                        key_id,secret=app.auth.create_key(target_tenant,str(body.get("name","")),role,[str(x) for x in body.get("scopes",["*"])])
                        app.db.audit(target_tenant,principal.name,"api_key.create","api_key",key_id,{"name":body.get("name"),"role":role})
                        return self._json(201,{"id":key_id,"secret":secret,"warning":"This secret is returned once. Store it securely."})

                    task_action = re.fullmatch(r"/api/v1/tasks/([0-9a-f-]+)/(approve|reject|cancel|retry)", path)
                    if task_action:
                        ctx,response=self._principal("operator","task:write")
                        if response:return response
                        principal,tenant_id=ctx; body=self._body(); task_id,action=task_action.group(1),task_action.group(2)
                        if action=="approve":result=app.engine.approve(tenant_id,task_id,principal.name,str(body.get("comment","")))
                        elif action=="reject":result=app.engine.reject(tenant_id,task_id,principal.name,str(body.get("comment","")))
                        elif action=="cancel":result=app.engine.cancel(tenant_id,task_id,principal.name)
                        else:result=app.engine.retry(tenant_id,task_id,principal.name)
                        return self._json(200,result)
                    key_revoke=re.fullmatch(r"/api/v1/api-keys/([0-9a-f-]+)/revoke",path)
                    if key_revoke:
                        ctx,response=self._principal("admin","key:write")
                        if response:return response
                        principal,tenant_id=ctx
                        if not app.db.revoke_api_key(tenant_id,key_revoke.group(1)):return self._error(404,"key_not_found","API key not found")
                        app.db.audit(tenant_id,principal.name,"api_key.revoke","api_key",key_revoke.group(1));return self._json(200,{"ok":True})

                    if path == "/api/v1/tasks":
                        ctx,response=self._principal("operator","task:write")
                        if response:return response
                        principal,tenant_id=ctx;body=self._body()
                        task,created=app.engine.submit(tenant_id,str(body.get("agent_id","")),str(body.get("prompt","")),actor=principal.name,
                            mutating=bool(body.get("mutating",False)),tier_override=body.get("tier_override"),
                            idempotency_key=self.headers.get("Idempotency-Key"),priority=int(body.get("priority",0)),
                            success_criteria=body.get("success_criteria"),max_attempts=body.get("max_attempts"))
                        return self._json(201 if created else 200,task)
                    if path == "/api/v1/agents":
                        ctx,response=self._principal("admin","agent:write")
                        if response:return response
                        principal,tenant_id=ctx;body=self._body();_validate_agent(body);agent=app.db.upsert_agent(tenant_id,body,principal.name)
                        app.db.audit(tenant_id,principal.name,"agent.upsert","agent",agent["id"],{"department":agent["department"],"default_tier":agent["default_tier"]})
                        return self._json(200,agent)
                    if path == "/api/v1/agent-templates":
                        ctx,response=self._principal("admin","agent:write")
                        if response:return response
                        principal,tenant_id=ctx;body=self._body()
                        template_id=str(body.get("id","")).strip().lower()
                        if not AGENT_ID_RE.fullmatch(template_id): raise ValueError("template id must be a DNS-like slug")
                        agent_spec=body.get("agent")
                        if not isinstance(agent_spec,dict): raise ValueError("agent template requires an agent object")
                        result=app.db.upsert_agent_template(tenant_id,{**body,"id":template_id},principal.name)
                        app.db.audit(tenant_id,principal.name,"agent_template.upsert","agent_template",template_id)
                        return self._json(201,result)
                    instantiate = re.fullmatch(r"/api/v1/agent-templates/([a-z0-9][a-z0-9-]{0,62})/instantiate", path)
                    if instantiate:
                        ctx,response=self._principal("admin","agent:write")
                        if response:return response
                        principal,tenant_id=ctx;body=self._body();template=app.db.get_agent_template(tenant_id,instantiate.group(1))
                        if not template or not template.get("enabled"): return self._error(404,"template_not_found","agent template not found")
                        spec=dict(template.get("template") or {});spec.update(body.get("overrides") or {})
                        spec["id"]=str(body.get("agent_id") or spec.get("id") or "").strip().lower()
                        if body.get("name"): spec["name"]=str(body["name"])
                        _validate_agent(spec);agent=app.db.upsert_agent(tenant_id,spec,principal.name)
                        app.db.audit(tenant_id,principal.name,"agent_template.instantiate","agent",agent["id"],{"template_id":instantiate.group(1)})
                        return self._json(201,agent)

                    if path == "/api/v1/budgets":
                        ctx,response=self._principal("admin","budget:write")
                        if response:return response
                        principal,tenant_id=ctx;body=self._body();scope_type=str(body.get("scope_type",""));period=str(body.get("period",""));scope_id=str(body.get("scope_id",""));limit=float(body.get("limit_credits",0))
                        if scope_type not in {"global","department","agent"} or period not in {"daily","monthly"} or not scope_id or limit<0:raise ValueError("invalid budget")
                        app.db.set_budget(tenant_id,scope_type,scope_id,period,limit);app.db.audit(tenant_id,principal.name,"budget.set","budget",f"{scope_type}:{scope_id}:{period}",{"limit_credits":limit})
                        return self._json(200,{"ok":True})
                    if path == "/api/v1/memories":
                        ctx,response=self._principal("operator","memory:write")
                        if response:return response
                        principal,tenant_id=ctx;body=self._body();title,content=str(body.get("title","")).strip(),str(body.get("content",""))
                        if not title or not content:raise ValueError("memory title and content are required")
                        memory=app.db.put_memory(tenant_id,str(body.get("agent_id")) if body.get("agent_id") else None,title,content,[str(x) for x in body.get("tags",[])],principal.name,body.get("id"))
                        app.db.audit(tenant_id,principal.name,"memory.put","memory",memory["id"],{"title":title[:200],"agent_id":memory.get("agent_id")})
                        return self._json(201,memory)
                    if path == "/api/v1/skills":
                        ctx,response=self._principal("admin","skill:write")
                        if response:return response
                        principal,tenant_id=ctx;body=self._body();manifest=body.get("manifest")
                        if not isinstance(manifest,dict):raise ValueError("manifest must be an object")
                        validate_manifest(manifest);signature=str(body.get("signature",""))
                        if not verify_manifest(manifest,signature,app.settings.skill_signing_key,app.settings.env=="production"):raise ValueError("skill signature is invalid or required")
                        skill=app.db.upsert_skill(tenant_id,manifest,signature,principal.name,bool(body.get("enabled",True)))
                        app.db.audit(tenant_id,principal.name,"skill.upsert","skill",manifest["id"],{"version":manifest["version"]})
                        return self._json(201,skill)
                    if path == "/api/v1/prometa/install":
                        ctx,response=self._principal("admin","agent:write")
                        if response:return response
                        principal,tenant_id=ctx;body=self._body()
                        sign_skills=bool(body.get("sign_skills",False))
                        if sign_skills and not app.settings.skill_signing_key:raise ValueError("skill signing key is required when sign_skills is true")
                        result=install_prometa_catalog(app.db,tenant_id,principal.name,
                                                       signing_key=app.settings.skill_signing_key,sign_skills=sign_skills)
                        app.db.audit(tenant_id,principal.name,"prometa.install","prometa","default",result)
                        return self._json(201,result)

                    if path == "/api/v1/policies":
                        ctx,response=self._principal("admin","policy:write")
                        if response:return response
                        principal,tenant_id=ctx;body=self._body()
                        policy_id=str(body.get("id","")).strip().lower()
                        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}",policy_id):raise ValueError("policy id must be a DNS-like slug")
                        document=validate_policy(body.get("document") or {})
                        result=app.db.upsert_policy(tenant_id,{"id":policy_id,"name":body.get("name") or policy_id,"document":document,"enabled":body.get("enabled",True)},principal.name)
                        app.db.audit(tenant_id,principal.name,"policy.upsert","policy",policy_id,{"enabled":result.get("enabled")})
                        return self._json(201,result)

                    # v3 writes
                    if path == "/api/v1/workflows":
                        ctx,response=self._principal("admin","automation:write")
                        if response:return response
                        principal,tenant_id=ctx
                        result=app.workflows.upsert(tenant_id,self._body(),principal.name)
                        app.db.audit(tenant_id,principal.name,"workflow.upsert","workflow",result["id"],{"version":result["version"]})
                        return self._json(201,result)
                    if path == "/api/v1/workflow-runs":
                        ctx,response=self._principal("operator","automation:write")
                        if response:return response
                        principal,tenant_id=ctx;body=self._body()
                        result=app.workflows.start(tenant_id,str(body.get("workflow_id","")),body.get("input") or {},principal.name,self.headers.get("Idempotency-Key"))
                        return self._json(201,result)
                    if path == "/api/v1/workflow-tick":
                        ctx,response=self._principal("operator","automation:write")
                        if response:return response
                        _,tenant_id=ctx
                        return self._json(200,app.workflows.tick(tenant_id))
                    if path == "/api/v1/schedules":
                        ctx,response=self._principal("admin","automation:write")
                        if response:return response
                        principal,tenant_id=ctx
                        return self._json(201,app.scheduler.upsert_schedule(tenant_id,self._body(),principal.name))
                    if path == "/api/v1/event-rules":
                        ctx,response=self._principal("admin","automation:write")
                        if response:return response
                        principal,tenant_id=ctx
                        return self._json(201,app.db.upsert_event_rule(tenant_id,self._body(),principal.name))
                    if path == "/api/v1/events":
                        ctx,response=self._principal("operator","automation:write")
                        if response:return response
                        principal,tenant_id=ctx;body=self._body()
                        payload=body.get("payload") or {}
                        if not isinstance(payload,dict):raise ValueError("event payload must be an object")
                        return self._json(202,app.db.emit_event(tenant_id,str(body.get("event_type","")),str(body.get("source") or principal.name),payload,str(body.get("dedupe_key",""))))
                    if path == "/api/v1/scheduler-tick":
                        ctx,response=self._principal("operator","automation:write")
                        if response:return response
                        principal,_=ctx
                        return self._json(200,app.scheduler.loop(1.0, True, owner_id=f"api-{principal.key_id}"))
                    if path == "/api/v1/evaluation-suites":
                        ctx,response=self._principal("admin","evaluation:write")
                        if response:return response
                        principal,tenant_id=ctx
                        return self._json(201,app.evaluations.upsert(tenant_id,self._body(),principal.name))
                    if path == "/api/v1/evaluation-runs":
                        ctx,response=self._principal("operator","evaluation:write")
                        if response:return response
                        principal,tenant_id=ctx;body=self._body()
                        return self._json(201,app.evaluations.start(tenant_id,str(body.get("suite_id","")),principal.name))
                    if path == "/api/v1/evaluation-tick":
                        ctx,response=self._principal("operator","evaluation:write")
                        if response:return response
                        return self._json(200,app.evaluations.tick())
                    if path == "/api/v1/rag/reindex":
                        ctx,response=self._principal("operator","memory:write")
                        if response:return response
                        _,tenant_id=ctx
                        return self._json(200,app.rag.reindex(tenant_id))
                    if path == "/api/v1/artifacts":
                        ctx,response=self._principal("operator","artifact:write")
                        if response:return response
                        principal,tenant_id=ctx;body=self._body()
                        raw=str(body.get("content_base64",""))
                        if not raw:raise ValueError("content_base64 is required")
                        try:data=base64.b64decode(raw,validate=True)
                        except Exception as exc:raise ValueError("content_base64 is invalid") from exc
                        result=app.artifacts.put_bytes(tenant_id,str(body.get("name","artifact.bin")),data,actor=principal.name,
                            content_type=body.get("content_type"),task_id=body.get("task_id"),workflow_run_id=body.get("workflow_run_id"),
                            metadata=body.get("metadata") if isinstance(body.get("metadata"),dict) else {})
                        return self._json(201,result)
                    if path == "/api/v1/slo":
                        ctx,response=self._principal("admin","finops:write")
                        if response:return response
                        _,tenant_id=ctx;app.db.set_slo_policy(tenant_id,self._body());return self._json(200,{"ok":True})
                    if path == "/api/v1/economics":
                        ctx,response=self._principal("admin","finops:write")
                        if response:return response
                        _,tenant_id=ctx;body=self._body()
                        app.db.set_tenant_economics(tenant_id,str(body.get("currency","USD")),float(body.get("currency_per_credit",.01)),float(body.get("target_worker_utilization",.70)))
                        return self._json(200,app.db.get_tenant_economics(tenant_id))
                    return self._error(404,"not_found","not found")
                except (ValueError,TypeError,SkillError,PolicyError) as exc:
                    return self._error(400,"invalid_request",_sanitize_error(str(exc)))
                except Exception as exc:
                    return self._error(500,"internal_error","internal server error",_sanitize_error(str(exc)))
        return Handler


def serve(app: App):
    app.engine.recover()
    workers = app.engine.start_workers()
    server = ThreadingHTTPServer((app.settings.host, app.settings.port), app.handler())
    server.daemon_threads = True
    print(f"zWorkforce {__version__} listening on http://{app.settings.host}:{app.settings.port} (embedded_workers={workers}, db={app.db.backend_kind})", flush=True)
    try:
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown(); server.server_close(); app.engine.shutdown()


def _intq(query: dict[str, list[str]], key: str, default: int) -> int:
    try:return int((query.get(key) or [str(default)])[0])
    except ValueError as exc:raise ValueError(f"query parameter {key} must be an integer") from exc


def _strq(query: dict[str, list[str]], key: str) -> str:
    return str((query.get(key) or [""])[0]).strip()


def _validate_agent(body: dict[str, Any]) -> None:
    agent_id=str(body.get("id",""))
    if not AGENT_ID_RE.fullmatch(agent_id):raise ValueError("agent id must be a DNS-like slug")
    if not str(body.get("name","")).strip():raise ValueError("agent name is required")
    if body.get("default_tier","terra") not in {"luna","terra","sol"}:raise ValueError("invalid default_tier")
    for field,minimum,maximum in (("max_iterations",1,64),("max_subagents",0,16),("required_approvals",0,3)):
        value=int(body.get(field,minimum))
        if value<minimum or value>maximum:raise ValueError(f"{field} must be between {minimum} and {maximum}")
    if float(body.get("max_cost_credits",0))<0:raise ValueError("max_cost_credits cannot be negative")
    allowed=body.get("allowed_tools",[]);approval=body.get("approval_tools",[]);skills=body.get("skill_ids",[])
    if not isinstance(allowed,list) or any(str(x) not in TOOL_DEFINITIONS for x in allowed):raise ValueError("allowed_tools contains an unknown tool")
    if not isinstance(approval,list) or any(str(x) not in TOOL_DEFINITIONS for x in approval):raise ValueError("approval_tools contains an unknown tool")
    if not set(map(str,approval)).issubset(set(map(str,allowed))):raise ValueError("approval_tools must be a subset of allowed_tools")
    if not isinstance(skills,list) or any(not isinstance(x,str) for x in skills):raise ValueError("skill_ids must be an array of strings")
