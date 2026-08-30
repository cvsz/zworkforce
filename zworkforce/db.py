from __future__ import annotations

from .db_base import DatabaseBase, TERMINAL_STATUSES, json_dumps, json_loads, utc_after, utcnow
from .db_migration import MigrationMixin
from .db_tasks import TaskMixin
from .db_finops import FinOpsMixin
from .db_governance import GovernanceMixin
from .db_automation import AutomationMixin
from .db_artifact_content import ArtifactContentMixin
from .db_browser_effects import BrowserEffectMixin
from .db_evidence import EvidenceMixin
from .db_workspace import WorkspaceMixin
from .db_workspace_context import WorkspaceContextMixin
from .db_workspace_grants import WorkspaceGrantMixin
from .db_workspace_worktrees import WorkspaceWorktreeMixin
from .db_realtime import DashboardEventMixin
from .db_schema_browser_effects import BROWSER_EFFECT_SCHEMA_SQL
from .db_schema_workspace_grants import WORKSPACE_GRANT_SCHEMA_SQL
from .db_schema_workspace_worktrees import WORKSPACE_WORKTREE_SCHEMA_SQL
from .db_schema_realtime import DASHBOARD_EVENT_SCHEMA_SQL

SCHEMA_VERSION = 9


class Database(WorkspaceWorktreeMixin, WorkspaceGrantMixin, WorkspaceContextMixin, WorkspaceMixin, EvidenceMixin, BrowserEffectMixin, ArtifactContentMixin, AutomationMixin, TaskMixin, FinOpsMixin, GovernanceMixin, DashboardEventMixin, MigrationMixin, DatabaseBase):
    def _initialize_schema(self, c) -> None:
        super()._initialize_schema(c)
        c.executescript(WORKSPACE_GRANT_SCHEMA_SQL)
        c.executescript(WORKSPACE_WORKTREE_SCHEMA_SQL)
        c.executescript(BROWSER_EFFECT_SCHEMA_SQL)
        c.executescript(DASHBOARD_EVENT_SCHEMA_SQL)
        c.execute(
            "INSERT INTO schema_meta(key,value) VALUES('schema_version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )

    def ready(self) -> bool:
        try:
            with self.connection() as c:
                row = c.execute("SELECT 1").fetchone()
                return bool(row and row[0] == 1)
        except Exception:
            return False

    def record_provider_success(self, name: str, latency_ms: float, tenant_id: str | None = None) -> None:
        if self.backend_kind != "postgres":
            return super().record_provider_success(name, latency_ms, tenant_id)
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO provider_health2(name,consecutive_failures,successes,failures,last_latency_ms,last_error,last_success_at,open_until,updated_at)
                VALUES(?,0,1,0,?,'',?,NULL,?) ON CONFLICT(name) DO UPDATE SET
                consecutive_failures=0,successes=provider_health2.successes+1,
                last_latency_ms=excluded.last_latency_ms,last_error='',last_success_at=excluded.last_success_at,
                open_until=NULL,updated_at=excluded.updated_at""",
                (name, latency_ms, now, now),
            )
        if tenant_id:
            self.append_dashboard_event(
                tenant_id,
                "provider.changed",
                "provider",
                name,
                {"summary": {"provider": name, "available": True, "latency_ms": latency_ms}},
            )

    def record_provider_failure(self, name: str, latency_ms: float, error: str, threshold: int, circuit_seconds: int, tenant_id: str | None = None) -> None:
        if self.backend_kind != "postgres":
            return super().record_provider_failure(name, latency_ms, error, threshold, circuit_seconds, tenant_id)
        now = utcnow()
        with self.connection() as c:
            row = c.execute("SELECT consecutive_failures FROM provider_health2 WHERE name=?", (name,)).fetchone()
            failures = (int(row[0]) if row else 0) + 1
            open_until = utc_after(circuit_seconds) if failures >= threshold else None
            c.execute(
                """INSERT INTO provider_health2(name,consecutive_failures,successes,failures,last_latency_ms,last_error,last_failure_at,open_until,updated_at)
                VALUES(?,?,0,1,?,?,?, ?,?) ON CONFLICT(name) DO UPDATE SET
                consecutive_failures=excluded.consecutive_failures,failures=provider_health2.failures+1,
                last_latency_ms=excluded.last_latency_ms,last_error=excluded.last_error,last_failure_at=excluded.last_failure_at,
                open_until=excluded.open_until,updated_at=excluded.updated_at""",
                (name, failures, latency_ms, error[:1000], now, open_until, now),
            )
        if tenant_id:
            self.append_dashboard_event(
                tenant_id,
                "provider.changed",
                "provider",
                name,
                {"summary": {"provider": name, "available": not bool(open_until), "latency_ms": latency_ms}},
            )

    def claim_next_task(self, worker_id: str, lease_seconds: int):
        if self.backend_kind != "postgres":
            return super().claim_next_task(worker_id, lease_seconds)
        return self._claim_next_task_postgres(worker_id, lease_seconds)

    def _claim_next_task_postgres(self, worker_id: str, lease_seconds: int):
        now = utcnow()
        lease_until = utc_after(lease_seconds)
        with self.connection() as c:
            c.execute("BEGIN")
            try:
                row = c.execute(
                    """SELECT * FROM tasks2 WHERE status='queued' AND cancel_requested=0 AND run_after<=?
                    ORDER BY priority DESC,created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED""",
                    (now,),
                ).fetchone()
                if not row:
                    c.execute("COMMIT")
                    return None
                task_id = row["id"]
                next_attempt = int(row["attempt"]) + 1
                if next_attempt > int(row["max_attempts"]):
                    c.execute(
                        "UPDATE tasks2 SET status='dead_letter',error='max attempts exhausted',finished_at=?,updated_at=? WHERE id=?",
                        (now, now, task_id),
                    )
                    c.execute("COMMIT")
                    return None
                c.execute(
                    """UPDATE tasks2 SET status='running',attempt=?,lease_owner=?,lease_expires_at=?,heartbeat_at=?,
                    started_at=COALESCE(started_at,?),updated_at=? WHERE id=?""",
                    (next_attempt, worker_id, lease_until, now, now, now, task_id),
                )
                claimed = c.execute("SELECT * FROM tasks2 WHERE id=?", (task_id,)).fetchone()
                if not claimed:
                    c.execute("ROLLBACK")
                    return None
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        task = self._decode(dict(claimed))
        self.task_event(task["tenant_id"], task_id, "claimed", worker_id,
                        {"attempt": next_attempt, "lease_expires_at": lease_until, "backend": "postgres"})
        return task


__all__ = ["Database", "SCHEMA_VERSION", "TERMINAL_STATUSES", "json_dumps", "json_loads", "utc_after", "utcnow"]
