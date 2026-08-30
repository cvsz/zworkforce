from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit

from . import __version__
from .api import App, serve
from .artifacts import build_artifact_store
from .config import Settings
from .db import Database, SCHEMA_VERSION
from .economics import capacity_forecast, chargeback_report, slo_status
from .policy import PolicyEngine
from .evaluation_suite import EvaluationRunner
from .identity import build_oidc_from_env
from .mcp import RemoteMCPClient
from .outbox import OutboxDispatcher
from .providers import build_provider
from .prometa import install_prometa_catalog, load_prometa_catalog
from .rag import build_semantic_memory
from .scheduler import Scheduler
from .secret_store import SecretResolver
from .security import AuthManager
from .skill_registry import RemoteSkillRegistry
from .skills import sign_manifest, validate_manifest
from .telemetry import wrap_provider_from_env
from .workflow import WorkflowOrchestrator


def _resolve_secret_references() -> None:
    resolver = SecretResolver.from_env()
    for value_name, ref_name in (("ZWORKFORCE_PROVIDER_API_KEY", "ZWORKFORCE_PROVIDER_API_KEY_REF"),
                                 ("ZWORKFORCE_SKILL_SIGNING_KEY", "ZWORKFORCE_SKILL_SIGNING_KEY_REF"),
                                 ("ZWORKFORCE_PROXY_IDENTITY_SECRET", "ZWORKFORCE_PROXY_IDENTITY_SECRET_REF"),
                                 ("ZWORKFORCE_DATABASE_URL", "ZWORKFORCE_DATABASE_URL_REF"),
                                 ("ZWORKFORCE_OUTBOX_SIGNING_SECRET", "ZWORKFORCE_OUTBOX_SIGNING_SECRET_REF"),
                                 ("ZWORKFORCE_EMBEDDING_API_KEY", "ZWORKFORCE_EMBEDDING_API_KEY_REF"),
                                 ("ZWORKFORCE_QDRANT_API_KEY", "ZWORKFORCE_QDRANT_API_KEY_REF")):
        ref = os.getenv(ref_name, "").strip()
        if ref and not os.getenv(value_name, ""):
            os.environ[value_name] = resolver.resolve(ref)
    raw = os.getenv("ZWORKFORCE_PROVIDERS_JSON", "").strip()
    if raw:
        providers = json.loads(raw)
        changed = False
        if isinstance(providers, list):
            for item in providers:
                if isinstance(item, dict) and item.get("api_key_ref") and not item.get("api_key"):
                    item["api_key"] = resolver.resolve(str(item.pop("api_key_ref")))
                    changed = True
            if changed:
                os.environ["ZWORKFORCE_PROVIDERS_JSON"] = json.dumps(providers, separators=(",", ":"))


def build():
    _resolve_secret_references()
    settings = Settings.from_env()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    target = os.getenv("ZWORKFORCE_DATABASE_URL", "").strip() or settings.database_path
    db = Database(target, settings.default_tenant)
    provider = wrap_provider_from_env(build_provider(settings, db))
    engine = PolicyEngine(settings, db, provider)
    oidc = build_oidc_from_env(settings.default_tenant)
    auth = AuthManager(db, settings.bootstrap_keys, settings.trust_proxy_identity, settings.proxy_identity_secret,
                       oidc=oidc, metrics_bearer=settings.metrics_bearer, metrics_tenant_id=settings.default_tenant)
    return settings, db, engine, auth, provider


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="zworkforce", description="AI Workforce control plane and durable agent runtime")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command")
    sub.add_parser("serve", help="Run the API/control-plane server")

    worker = sub.add_parser("worker", help="Run a durable queue worker")
    worker.add_argument("--id", default="")
    worker.add_argument("--once", action="store_true")

    scheduler = sub.add_parser("scheduler", help="Run workflow/schedule/event orchestration")
    scheduler.add_argument("--once", action="store_true")
    scheduler.add_argument("--poll", type=float, default=1.0)

    sub.add_parser("doctor", help="Validate configuration and runtime dependencies")
    sub.add_parser("init", help="Initialize/migrate the database")

    tenant = sub.add_parser("tenant-create", help="Create a tenant and seed default agents")
    tenant.add_argument("id")
    tenant.add_argument("--name", default="")

    key = sub.add_parser("key-create", help="Create an API key and store its one-time secret in a protected file")
    key.add_argument("--tenant", default="")
    key.add_argument("--name", required=True)
    key.add_argument("--role", choices=["viewer", "operator", "admin", "superadmin"], default="viewer")
    key.add_argument("--scopes", default="*")
    key.add_argument("--secret-file", default="", help="Write the one-time secret to this new mode-0600 file")

    verify = sub.add_parser("audit-verify", help="Verify the tenant audit hash chain")
    verify.add_argument("--tenant", default="")

    skill = sub.add_parser("skill-sign", help="Sign a skill manifest using ZWORKFORCE_SKILL_SIGNING_KEY")
    skill.add_argument("file")

    install = sub.add_parser("skill-install", help="Install a signed remote skill package over HTTPS")
    install.add_argument("url")
    install.add_argument("--tenant", default="")
    install.add_argument("--actor", default="cli")

    prometa = sub.add_parser("prometa-install", help="Install the built-in ProMeta agents, skills, templates and workflows")
    prometa.add_argument("--tenant", default="")
    prometa.add_argument("--actor", default="cli")
    prometa.add_argument("--sign-skills", action="store_true", help="Sign installed skill manifests with ZWORKFORCE_SKILL_SIGNING_KEY")
    prometa.add_argument("--dry-run", action="store_true", help="Validate and summarize the built-in ProMeta catalog without writing")

    wf_upsert = sub.add_parser("workflow-upsert", help="Create/update a workflow DAG from JSON")
    wf_upsert.add_argument("file")
    wf_upsert.add_argument("--tenant", default="")
    wf_upsert.add_argument("--actor", default="cli")
    wf_run = sub.add_parser("workflow-run", help="Start a workflow DAG")
    wf_run.add_argument("id")
    wf_run.add_argument("--tenant", default="")
    wf_run.add_argument("--input", default="{}")
    wf_run.add_argument("--actor", default="cli")
    wf_tick = sub.add_parser("workflow-tick", help="Advance active workflow DAGs once")
    wf_tick.add_argument("--tenant", default="")

    schedule_upsert = sub.add_parser("schedule-upsert", help="Create/update cron or interval schedule from JSON")
    schedule_upsert.add_argument("file")
    schedule_upsert.add_argument("--tenant", default="")
    schedule_upsert.add_argument("--actor", default="cli")

    rule_upsert = sub.add_parser("event-rule-upsert", help="Create/update event rule from JSON")
    rule_upsert.add_argument("file")
    rule_upsert.add_argument("--tenant", default="")
    rule_upsert.add_argument("--actor", default="cli")

    emit = sub.add_parser("event-emit", help="Emit a durable event")
    emit.add_argument("event_type")
    emit.add_argument("--tenant", default="")
    emit.add_argument("--source", default="cli")
    emit.add_argument("--dedupe-key", default="")
    emit.add_argument("--payload", default="{}")

    ev_upsert = sub.add_parser("eval-upsert", help="Create/update A/B evaluation suite from JSON")
    ev_upsert.add_argument("file")
    ev_upsert.add_argument("--tenant", default="")
    ev_upsert.add_argument("--actor", default="cli")
    ev_run = sub.add_parser("eval-run", help="Start an evaluation suite")
    ev_run.add_argument("id")
    ev_run.add_argument("--tenant", default="")
    ev_run.add_argument("--actor", default="cli")
    sub.add_parser("eval-tick", help="Advance evaluation runs once")

    rag_reindex = sub.add_parser("rag-reindex", help="Index tenant memories into local semantic vectors")
    rag_reindex.add_argument("--tenant", default="")
    rag_search = sub.add_parser("rag-search", help="Semantic memory search")
    rag_search.add_argument("query")
    rag_search.add_argument("--tenant", default="")
    rag_search.add_argument("--agent", default="")
    rag_search.add_argument("--limit", type=int, default=10)

    artifact = sub.add_parser("artifact-put", help="Store a content-addressed artifact")
    artifact.add_argument("file")
    artifact.add_argument("--tenant", default="")
    artifact.add_argument("--actor", default="cli")
    artifact.add_argument("--task-id", default="")
    artifact.add_argument("--workflow-run-id", default="")

    slo = sub.add_parser("slo-set", help="Create/update SLO policy from JSON")
    slo.add_argument("file")
    slo.add_argument("--tenant", default="")
    slo_status_p = sub.add_parser("slo-status", help="Evaluate tenant SLO policies")
    slo_status_p.add_argument("--tenant", default="")

    charge = sub.add_parser("chargeback", help="Calculate tenant chargeback report")
    charge.add_argument("--tenant", default="")
    charge.add_argument("--hours", type=int, default=720)
    cap = sub.add_parser("capacity", help="Forecast worker capacity")
    cap.add_argument("--tenant", default="")
    cap.add_argument("--hours", type=int, default=24)

    outbox = sub.add_parser("outbox", help="Deliver durable external integration outbox")
    outbox.add_argument("--once", action="store_true")
    outbox.add_argument("--poll", type=float, default=2.0)

    mcp_tools = sub.add_parser("mcp-tools", help="List tools from a stateless MCP 2026-07-28 server")
    mcp_tools.add_argument("endpoint")
    mcp_tools.add_argument("--token-env", default="ZWORKFORCE_MCP_TOKEN")
    mcp_call = sub.add_parser("mcp-call", help="Call a tool on a stateless MCP 2026-07-28 server")
    mcp_call.add_argument("endpoint")
    mcp_call.add_argument("name")
    mcp_call.add_argument("--arguments", default="{}")
    mcp_call.add_argument("--token-env", default="ZWORKFORCE_MCP_TOKEN")
    return p


def _json_file(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON file must contain an object")
    return data


def _tenant(args, settings) -> str:
    return (getattr(args, "tenant", "") or settings.default_tenant).strip().lower()


def _safe_database_target(db) -> str:
    if db.backend_kind != "postgres":
        return str(db.path)
    parts = urlsplit(db.target)
    host = parts.hostname or ""
    if parts.port:
        host += ":" + str(parts.port)
    user = parts.username or ""
    netloc = (user + "@" if user else "") + host
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, ""))


def _write_secret_file(path: Path, secret: str) -> Path:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        raise ValueError(f"secret file already exists: {path}") from None
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            handle.write(secret + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _restrict_secret_file_permissions(path)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise
    return path


def _restrict_secret_file_permissions(path: Path) -> None:
    if os.name != "nt":
        return
    raw = subprocess.check_output(
        ["whoami", "/user", "/fo", "csv", "/nh"],
        text=True,
        encoding="utf-8",
    ).strip()
    rows = list(csv.reader([raw]))
    sid = rows[0][1] if rows and len(rows[0]) >= 2 else ""
    if not sid:
        raise RuntimeError("unable to determine current Windows user SID")
    subprocess.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r", f"*{sid}:F"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )


def main(argv=None):
    args = parser().parse_args(argv)
    cmd = args.command or "serve"
    try:
        settings, db, engine, auth, provider = build()
    except Exception as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    long_running = cmd in {"serve", "scheduler"} and not getattr(args, "once", False)
    try:
        if cmd == "doctor":
            health = provider.models()
            report = {
                "version": __version__,
                "environment": settings.env,
                "database": _safe_database_target(db),
                "database_backend": db.backend_kind,
                "database_ready": db.ready(),
                "schema_version": SCHEMA_VERSION,
                "default_tenant": settings.default_tenant,
                "tenants": len(db.list_tenants()),
                "agents": len(db.list_agents(settings.default_tenant)),
                "workspace_root": str(settings.workspace_root),
                "workspace_exists": settings.workspace_root.exists(),
                "shell_enabled": settings.shell_enabled,
                "http_allowlist": list(settings.http_allowlist),
                "embedded_workers": settings.embedded_workers,
                "dashboard_event_retention_seconds": settings.dashboard_event_retention_seconds,
                "providers": [{"name": x["name"], "kind": x["kind"], "available": x["available"], "models": x["models"]} for x in health],
                "audit": db.verify_audit_chain(settings.default_tenant),
                "oidc_enabled": bool(os.getenv("ZWORKFORCE_OIDC_ISSUER", "").strip()),
                "otlp_enabled": bool(os.getenv("ZWORKFORCE_OTLP_TRACES_ENDPOINT", "").strip()),
            }
            print(json.dumps(report, indent=2, ensure_ascii=False))
            providers_ready = bool(report["providers"]) and any(
                item["available"] and (settings.env != "production" or item["kind"] != "mock")
                for item in report["providers"]
            )
            audit_ok = bool(report["audit"].get("ok"))
            return 0 if report["database_ready"] and report["workspace_exists"] and providers_ready and audit_ok else 1
        if cmd == "init":
            print(json.dumps({"ok": True, "database": _safe_database_target(db), "backend": db.backend_kind,
                              "schema_version": SCHEMA_VERSION, "tenants": len(db.list_tenants())}, indent=2))
            return 0
        if cmd == "tenant-create":
            print(json.dumps(db.ensure_tenant(args.id.strip().lower(), args.name or args.id), indent=2, ensure_ascii=False)); return 0
        if cmd == "key-create":
            tenant_id = _tenant(args, settings); db.ensure_tenant(tenant_id)
            key_id, secret = auth.create_key(tenant_id, args.name, args.role, [x.strip() for x in args.scopes.split(",") if x.strip()])
            secret_path = Path(args.secret_file).expanduser() if args.secret_file else settings.data_dir / "api-keys" / f"{key_id}.secret"
            try:
                _write_secret_file(secret_path, secret)
            except Exception:
                db.revoke_api_key(tenant_id, key_id)
                raise
            print(json.dumps({"id": key_id, "tenant_id": tenant_id, "name": args.name, "role": args.role,
                              "secret_file": str(secret_path),
                              "warning": "Store or move this mode-0600 file; the secret is not printed or retrievable later."}, indent=2)); return 0
        if cmd == "audit-verify":
            result = db.verify_audit_chain(_tenant(args, settings)); print(json.dumps(result, indent=2)); return 0 if result["ok"] else 1
        if cmd == "skill-sign":
            manifest = _json_file(args.file); validate_manifest(manifest); print(sign_manifest(manifest, settings.skill_signing_key)); return 0
        if cmd == "skill-install":
            hosts = tuple(x.strip() for x in os.getenv("ZWORKFORCE_SKILL_REGISTRY_ALLOWLIST", "").split(",") if x.strip())
            registry = RemoteSkillRegistry(db, settings.skill_signing_key, hosts)
            result = registry.install(_tenant(args, settings), args.url, args.actor, require_signature=True)
            print(json.dumps(result, indent=2, ensure_ascii=False)); return 0
        if cmd == "prometa-install":
            if args.dry_run:
                catalog = load_prometa_catalog()
                print(json.dumps({"ok": True, "agents": len(catalog["agents"]), "skills": len(catalog["skills"]),
                                  "agent_templates": len(catalog["templates"]), "workflows": len(catalog["workflows"])},
                                 indent=2, ensure_ascii=False)); return 0
            if args.sign_skills and not settings.skill_signing_key:
                raise ValueError("ZWORKFORCE_SKILL_SIGNING_KEY is required with --sign-skills")
            result = install_prometa_catalog(db, _tenant(args, settings), args.actor,
                                             signing_key=settings.skill_signing_key, sign_skills=bool(args.sign_skills))
            print(json.dumps(result, indent=2, ensure_ascii=False)); return 0
        if cmd == "worker":
            engine.recover(); worker_id = args.id.strip() or f"worker-{socket.gethostname()}"
            processed = engine.worker_loop(worker_id, once=args.once)
            if args.once: print(json.dumps({"processed": processed, "worker_id": worker_id}))
            return 0
        if cmd == "scheduler":
            scheduler = Scheduler(db, engine, dashboard_event_retention_seconds=settings.dashboard_event_retention_seconds); print(json.dumps(scheduler.loop(args.poll, args.once), indent=2)) if args.once else scheduler.loop(args.poll, False); return 0
        if cmd == "workflow-upsert":
            result = WorkflowOrchestrator(db, engine).upsert(_tenant(args, settings), _json_file(args.file), args.actor)
            print(json.dumps(result, indent=2, ensure_ascii=False)); return 0
        if cmd == "workflow-run":
            result = WorkflowOrchestrator(db, engine).start(_tenant(args, settings), args.id, json.loads(args.input), args.actor)
            print(json.dumps(result, indent=2, ensure_ascii=False)); return 0
        if cmd == "workflow-tick":
            result = WorkflowOrchestrator(db, engine).tick(_tenant(args, settings) if args.tenant else None)
            print(json.dumps(result, indent=2)); return 0
        if cmd == "schedule-upsert":
            result = Scheduler(db, engine, dashboard_event_retention_seconds=settings.dashboard_event_retention_seconds).upsert_schedule(_tenant(args, settings), _json_file(args.file), args.actor)
            print(json.dumps(result, indent=2, ensure_ascii=False)); return 0
        if cmd == "event-rule-upsert":
            result = db.upsert_event_rule(_tenant(args, settings), _json_file(args.file), args.actor)
            print(json.dumps(result, indent=2, ensure_ascii=False)); return 0
        if cmd == "event-emit":
            payload = json.loads(args.payload)
            if not isinstance(payload, dict): raise ValueError("--payload must be a JSON object")
            result = db.emit_event(_tenant(args, settings), args.event_type, args.source, payload, args.dedupe_key)
            print(json.dumps(result, indent=2, ensure_ascii=False)); return 0
        if cmd == "eval-upsert":
            result = EvaluationRunner(db, engine).upsert(_tenant(args, settings), _json_file(args.file), args.actor)
            print(json.dumps(result, indent=2, ensure_ascii=False)); return 0
        if cmd == "eval-run":
            result = EvaluationRunner(db, engine).start(_tenant(args, settings), args.id, args.actor)
            print(json.dumps(result, indent=2, ensure_ascii=False)); return 0
        if cmd == "eval-tick":
            print(json.dumps(EvaluationRunner(db, engine).tick(), indent=2)); return 0
        if cmd == "rag-reindex":
            print(json.dumps(build_semantic_memory(db).reindex(_tenant(args, settings)), indent=2)); return 0
        if cmd == "rag-search":
            items = build_semantic_memory(db).search(_tenant(args, settings), args.query, args.agent or None, args.limit)
            print(json.dumps({"items": items}, indent=2, ensure_ascii=False)); return 0
        if cmd == "artifact-put":
            store = build_artifact_store(settings, db)
            result = store.put_file(_tenant(args, settings), args.file, actor=args.actor,
                                    task_id=args.task_id or None, workflow_run_id=args.workflow_run_id or None)
            print(json.dumps(result, indent=2, ensure_ascii=False)); return 0
        if cmd == "slo-set":
            db.set_slo_policy(_tenant(args, settings), _json_file(args.file)); print(json.dumps({"ok": True}, indent=2)); return 0
        if cmd == "slo-status":
            print(json.dumps(slo_status(db, _tenant(args, settings)), indent=2)); return 0
        if cmd == "chargeback":
            print(json.dumps(chargeback_report(db, _tenant(args, settings), args.hours), indent=2)); return 0
        if cmd == "capacity":
            print(json.dumps(capacity_forecast(db, _tenant(args, settings), args.hours), indent=2)); return 0
        if cmd == "outbox":
            dispatcher = OutboxDispatcher(db, os.getenv("ZWORKFORCE_OUTBOX_SIGNING_SECRET", ""), allow_hosts=tuple(x.strip() for x in os.getenv("ZWORKFORCE_OUTBOX_ALLOWLIST", "").split(",") if x.strip()))
            if args.once: print(json.dumps(dispatcher.tick(), indent=2)); return 0
            dispatcher.loop(args.poll); return 0
        if cmd == "mcp-tools":
            client=RemoteMCPClient(args.endpoint, os.getenv(args.token_env, ""))
            print(json.dumps(client.list_tools(), indent=2, ensure_ascii=False)); return 0
        if cmd == "mcp-call":
            arguments=json.loads(args.arguments)
            if not isinstance(arguments,dict): raise ValueError("--arguments must be a JSON object")
            client=RemoteMCPClient(args.endpoint, os.getenv(args.token_env, ""))
            print(json.dumps(client.call_tool(args.name,arguments), indent=2, ensure_ascii=False)); return 0

        serve(App(settings, db, engine, auth, provider))
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"{cmd} error: {exc}", file=sys.stderr)
        return 1
    finally:
        if cmd != "serve":
            engine.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
