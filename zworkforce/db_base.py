from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from .db_backend import connect_postgres, is_postgres_target
from .db_schema import SCHEMA_SQL
from .db_schema_v3 import V3_SCHEMA_SQL
from .db_schema_workspace import WORKSPACE_SCHEMA_SQL

SCHEMA_VERSION = 5
TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "dead_letter"}
_ARRAY_JSON_FIELDS = {
    "allowed_tools_json", "approval_tools_json", "skill_ids_json", "tags_json", "success_criteria_json",
    "scopes_json", "depends_on_json", "cases_json", "variants_json", "artifact_ids_json",
}
_POSTGRES_SCHEMA_LOCK_KEY = 0x5A574F524B
_ALLOWED_PRAGMA_TABLES = frozenset({"workflow_runs3", "outbox3", "agents", "tasks", "usage_events", "budgets", "audit_events"})


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def utc_after(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def json_dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, sort_keys=True, default=str)


def json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class DatabaseBase:
    def __init__(self, target: str | Path, default_tenant: str = "default"):
        self.target = str(target)
        self.backend_kind = "postgres" if is_postgres_target(self.target) else "sqlite"
        self.path = None if self.backend_kind == "postgres" else Path(target)
        self.default_tenant = default_tenant
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self):
        if self.backend_kind == "postgres":
            pool = get_postgres_pool(self.target, min_size=1, max_size=10)
            with pool.connection() as connection:
                yield connection
            return
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=30000")
        try:
            yield c
        finally:
            c.close()

    def initialize(self) -> None:
        with self.connection() as c:
            if self.backend_kind == "postgres":
                c.execute("BEGIN")
                try:
                    c.execute("SELECT pg_advisory_xact_lock(?)", (_POSTGRES_SCHEMA_LOCK_KEY,))
                    self._initialize_schema(c)
                    c.execute("COMMIT")
                except Exception:
                    c.execute("ROLLBACK")
                    raise
            else:
                c.execute("PRAGMA journal_mode=WAL")
                c.execute("PRAGMA synchronous=NORMAL")
                self._initialize_schema(c)
        self.ensure_tenant(self.default_tenant, self.default_tenant.title())
        if self.backend_kind == "sqlite":
            self._migrate_v1_if_needed()

    def _initialize_schema(self, c) -> None:
        c.executescript(SCHEMA_SQL)
        c.executescript(V3_SCHEMA_SQL)
        self._ensure_v4_schema(c)
        c.executescript(WORKSPACE_SCHEMA_SQL)
        c.execute(
            "INSERT INTO schema_meta(key,value) VALUES('schema_version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )

    def _column_exists(self, c, table: str, column: str) -> bool:
        if self.backend_kind == "postgres":
            row = c.execute(
                "SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=? AND column_name=?",
                (table, column),
            ).fetchone()
            return bool(row)
        if table not in _ALLOWED_PRAGMA_TABLES:
            raise ValueError(f"table {table} is not allowed for PRAGMA introspection")
        rows = c.execute(f"PRAGMA table_info({table})").fetchall()
        return any(row[1] == column for row in rows)

    def _ensure_v4_schema(self, c) -> None:
        if not self._column_exists(c, "workflow_runs3", "idempotency_key"):
            c.execute("ALTER TABLE workflow_runs3 ADD COLUMN idempotency_key TEXT NOT NULL DEFAULT ''")
        if not self._column_exists(c, "outbox3", "claim_owner"):
            c.execute("ALTER TABLE outbox3 ADD COLUMN claim_owner TEXT NULL")
        if not self._column_exists(c, "outbox3", "claim_expires_at"):
            c.execute("ALTER TABLE outbox3 ADD COLUMN claim_expires_at TEXT NULL")
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_runs3_idempotency "
            "ON workflow_runs3(tenant_id,idempotency_key) WHERE idempotency_key <> ''"
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_outbox3_claim ON outbox3(status,claim_expires_at)")

    def _table_exists(self, c, name: str) -> bool:
        if self.backend_kind == "postgres":
            row = c.execute("SELECT to_regclass(?)", (name,)).fetchone()
            return bool(row and row[0])
        return bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())

    def _rows(self, rows: Iterable) -> list[dict[str, Any]]:
        return [self._decode(dict(r)) for r in rows]

    @staticmethod
    def _decode(row: dict[str, Any]) -> dict[str, Any]:
        for key in list(row):
            if key.endswith("_json"):
                row[key[:-5]] = json_loads(row.pop(key), [] if key in _ARRAY_JSON_FIELDS else {})
        return row

    def ensure_tenant(self, tenant_id: str, name: str | None = None) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                c.execute(
                    "INSERT OR IGNORE INTO tenants(id,name,enabled,created_at,updated_at) VALUES(?,?,1,?,?)",
                    (tenant_id, name or tenant_id, now, now),
                )
                count = c.execute("SELECT COUNT(*) FROM agents2 WHERE tenant_id=?", (tenant_id,)).fetchone()[0]
                if count == 0:
                    self._seed_agents(c, tenant_id, now)
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        return self.get_tenant(tenant_id) or {}

    def _seed_agents(self, c, tenant_id: str, now: str) -> None:
        common_read = ["calculator", "workspace_list", "workspace_read", "memory_search", "http_get", "agent_delegate"]
        coding = common_read + ["workspace_write", "shell_exec"]
        seeds = [
            ("software-engineer", "Software Engineer", "Repository analysis, implementation, testing and review", "engineering", "terra", 80, 12, 3, 1, 1, "You are a careful senior software engineer. Prefer tests, small diffs, secure defaults, and explicit verification.", coding, ["workspace_write", "shell_exec"]),
            ("researcher", "Research Analyst", "Research, synthesis, evidence and decision support", "research", "terra", 50, 8, 2, 0, 0, "You are an evidence-first research analyst. Separate facts, assumptions, and recommendations.", common_read, []),
            ("finance-analyst", "Finance Analyst", "Forecasting, spreadsheet reasoning and financial analysis", "finance", "terra", 40, 8, 1, 1, 1, "You are a finance analyst. Show assumptions and never fabricate financial records.", common_read + ["memory_put"], ["memory_put"]),
            ("sales", "Sales Agent", "Lead preparation, proposals and sales workflow support", "sales", "luna", 25, 6, 1, 1, 1, "You are a concise sales operations agent. Never make unauthorized commitments.", common_read + ["memory_put"], ["memory_put"]),
            ("operations", "Operations Agent", "Operational checks, runbooks and workflow automation", "operations", "terra", 50, 10, 2, 1, 1, "You are an operations engineer. Prefer reversible actions and explicit verification.", coding + ["http_request"], ["workspace_write", "shell_exec", "http_request"]),
            ("management", "Management Analyst", "Executive synthesis, planning and board-ready outputs", "management", "sol", 80, 8, 2, 0, 0, "You are an executive analyst. Optimize for decision quality, risks, and measurable outcomes.", common_read, []),
        ]
        for s in seeds:
            c.execute(
                """INSERT OR IGNORE INTO agents2(tenant_id,id,name,description,department,default_tier,max_cost_credits,max_iterations,
                max_subagents,required_approvals,requires_approval_for_mutations,system_prompt,allowed_tools_json,approval_tools_json,
                skill_ids_json,enabled,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                (tenant_id, *s[:11], json_dumps(s[11]), json_dumps(s[12]), "[]", now, now),
            )

    def get_tenant(self, tenant_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM tenants WHERE id=?", (tenant_id,)).fetchone()
            return dict(row) if row else None

    def list_tenants(self) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM tenants ORDER BY id").fetchall())

    def list_agents(self, tenant_id: str) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM agents2 WHERE tenant_id=? ORDER BY department,name", (tenant_id,)).fetchall())

    def get_agent(self, tenant_id: str, agent_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM agents2 WHERE tenant_id=? AND id=?", (tenant_id, agent_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def upsert_agent(self, tenant_id: str, a: dict[str, Any], actor: str = "system") -> dict[str, Any]:
        now = utcnow()
        before = self.get_agent(tenant_id, a["id"])
        values = (
            tenant_id,
            a["id"],
            a["name"],
            a.get("description", ""),
            a.get("department", "general"),
            a.get("default_tier", "terra"),
            float(a.get("max_cost_credits", 50)),
            int(a.get("max_iterations", 8)),
            int(a.get("max_subagents", 2)),
            int(a.get("required_approvals", 1)),
            int(bool(a.get("requires_approval_for_mutations", True))),
            a.get("system_prompt", ""),
            json_dumps(list(a.get("allowed_tools", []))),
            json_dumps(list(a.get("approval_tools", []))),
            json_dumps(list(a.get("skill_ids", []))),
            int(bool(a.get("enabled", True))),
            now,
            now,
        )
        with self.connection() as c:
            c.execute(
                """INSERT INTO agents2(tenant_id,id,name,description,department,default_tier,max_cost_credits,max_iterations,max_subagents,
                required_approvals,requires_approval_for_mutations,system_prompt,allowed_tools_json,approval_tools_json,skill_ids_json,
                enabled,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tenant_id,id) DO UPDATE SET name=excluded.name,description=excluded.description,department=excluded.department,
                default_tier=excluded.default_tier,max_cost_credits=excluded.max_cost_credits,max_iterations=excluded.max_iterations,
                max_subagents=excluded.max_subagents,required_approvals=excluded.required_approvals,
                requires_approval_for_mutations=excluded.requires_approval_for_mutations,system_prompt=excluded.system_prompt,
                allowed_tools_json=excluded.allowed_tools_json,approval_tools_json=excluded.approval_tools_json,
                skill_ids_json=excluded.skill_ids_json,enabled=excluded.enabled,updated_at=excluded.updated_at""",
                values,
            )
        result = self.get_agent(tenant_id, a["id"]) or {}
        def comparable(value):
            if not value: return value
            return {k: v for k, v in value.items() if k not in {"created_at", "updated_at"}}
        if result and comparable(result) != comparable(before) and hasattr(self, "record_agent_version"):
            self.record_agent_version(tenant_id, a["id"], result, actor)
        return result
