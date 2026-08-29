from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from .db_base import json_dumps, json_loads, utcnow


def _decode_json_rows(rows):
    return [dict(r) for r in rows]


class AutomationMixin:
    # ----- Policy as code -----
    def upsert_policy(self, tenant_id: str, policy: dict[str, Any], actor: str) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO policies3(tenant_id,id,name,document_json,enabled,created_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id,id) DO UPDATE SET name=excluded.name,
                document_json=excluded.document_json,enabled=excluded.enabled,updated_at=excluded.updated_at""",
                (tenant_id, policy["id"], policy.get("name") or policy["id"], json_dumps(policy["document"]),
                 int(bool(policy.get("enabled", True))), actor, now, now),
            )
        return self.get_policy(tenant_id, policy["id"]) or {}

    def get_policy(self, tenant_id: str, policy_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM policies3 WHERE tenant_id=? AND id=?", (tenant_id, policy_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def list_policies(self, tenant_id: str, enabled_only: bool = False) -> list[dict[str, Any]]:
        with self.connection() as c:
            sql = "SELECT * FROM policies3 WHERE tenant_id=?" + (" AND enabled=1" if enabled_only else "") + " ORDER BY id"
            return self._rows(c.execute(sql, (tenant_id,)).fetchall())

    # ----- Agent templates / versions -----
    def upsert_agent_template(self, tenant_id: str, template: dict[str, Any], actor: str) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO agent_templates3(tenant_id,id,name,description,template_json,enabled,created_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id,id) DO UPDATE SET name=excluded.name,description=excluded.description,
                template_json=excluded.template_json,enabled=excluded.enabled,updated_at=excluded.updated_at""",
                (tenant_id, template["id"], template.get("name") or template["id"], template.get("description", ""),
                 json_dumps(template.get("agent") or {}), int(bool(template.get("enabled", True))), actor, now, now),
            )
        return self.get_agent_template(tenant_id, template["id"]) or {}

    def get_agent_template(self, tenant_id: str, template_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM agent_templates3 WHERE tenant_id=? AND id=?", (tenant_id, template_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def list_agent_templates(self, tenant_id: str) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM agent_templates3 WHERE tenant_id=? ORDER BY id", (tenant_id,)).fetchall())

    def record_agent_version(self, tenant_id: str, agent_id: str, snapshot: dict[str, Any], actor: str = "system") -> int:
        with self.connection() as c:
            row = c.execute("SELECT COALESCE(MAX(version),0) n FROM agent_versions3 WHERE tenant_id=? AND agent_id=?", (tenant_id, agent_id)).fetchone()
            version = int(row["n"] if hasattr(row, "keys") else row[0]) + 1
            c.execute("INSERT INTO agent_versions3(id,tenant_id,agent_id,version,snapshot_json,created_by,created_at) VALUES(?,?,?,?,?,?,?)",
                      (str(uuid.uuid4()), tenant_id, agent_id, version, json_dumps(snapshot), actor, utcnow()))
        return version

    def list_agent_versions(self, tenant_id: str, agent_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM agent_versions3 WHERE tenant_id=? AND agent_id=? ORDER BY version DESC LIMIT ?",
                                        (tenant_id, agent_id, max(1, min(int(limit), 500)))).fetchall())

    # ----- Workflows -----
    def upsert_workflow(self, tenant_id: str, workflow: dict[str, Any], actor: str) -> dict[str, Any]:
        now = utcnow()
        workflow_id = str(workflow["id"])
        current = self.get_workflow(tenant_id, workflow_id)
        version = int(current["version"]) + 1 if current else 1
        with self.connection() as c:
            c.execute(
                """INSERT INTO workflows3(tenant_id,id,name,description,version,definition_json,enabled,created_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tenant_id,id) DO UPDATE SET name=excluded.name,description=excluded.description,
                version=excluded.version,definition_json=excluded.definition_json,enabled=excluded.enabled,updated_at=excluded.updated_at""",
                (tenant_id, workflow_id, str(workflow.get("name") or workflow_id), str(workflow.get("description") or ""),
                 version, json_dumps(workflow["definition"]), int(bool(workflow.get("enabled", True))), actor, now, now),
            )
        return self.get_workflow(tenant_id, workflow_id) or {}

    def get_workflow(self, tenant_id: str, workflow_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM workflows3 WHERE tenant_id=? AND id=?", (tenant_id, workflow_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def list_workflows(self, tenant_id: str) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM workflows3 WHERE tenant_id=? ORDER BY id", (tenant_id,)).fetchall())

    def create_workflow_run(self, tenant_id: str, workflow: dict[str, Any], actor: str, input_data: dict[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
        idempotency_key = str(idempotency_key or "").strip()
        run_id = str(uuid.uuid4())
        now = utcnow()
        request_hash = self._workflow_request_hash(workflow, actor, input_data)
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                if idempotency_key:
                    existing = c.execute(
                        "SELECT * FROM workflow_runs3 WHERE tenant_id=? AND idempotency_key=?",
                        (tenant_id, idempotency_key),
                    ).fetchone()
                    if existing:
                        if self._workflow_request_hash_from_row(existing) != request_hash:
                            raise ValueError("idempotency key was already used with a different workflow request")
                        c.execute("COMMIT")
                        return self._decode(dict(existing))
                c.execute(
                    """INSERT INTO workflow_runs3(id,tenant_id,workflow_id,workflow_version,status,actor,idempotency_key,input_json,context_json,
                    error,created_at,started_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (run_id, tenant_id, workflow["id"], int(workflow["version"]), "running", actor, idempotency_key,
                     json_dumps(input_data), "{}", "", now, now),
                )
                for step in workflow["definition"]["steps"]:
                    c.execute(
                        """INSERT INTO workflow_steps3(run_id,tenant_id,step_id,agent_id,status,depends_on_json,definition_json)
                        VALUES(?,?,?,?,?,?,?)""",
                        (run_id, tenant_id, step["id"], step["agent_id"], "pending",
                         json_dumps(step.get("depends_on", [])), json_dumps(step)),
                    )
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                if idempotency_key:
                    existing = c.execute(
                        "SELECT * FROM workflow_runs3 WHERE tenant_id=? AND idempotency_key=?",
                        (tenant_id, idempotency_key),
                    ).fetchone()
                    if existing:
                        if self._workflow_request_hash_from_row(existing) != request_hash:
                            raise ValueError("idempotency key was already used with a different workflow request")
                        return self._decode(dict(existing))
                raise
        return self.get_workflow_run(tenant_id, run_id) or {}

    @staticmethod
    def _workflow_request_hash(workflow: dict[str, Any], actor: str, input_data: dict[str, Any]) -> str:
        material = json_dumps({
            "workflow_id": str(workflow["id"]),
            "workflow_version": int(workflow["version"]),
            "actor": str(actor),
            "input": input_data,
        }).encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    @classmethod
    def _workflow_request_hash_from_row(cls, row: Any) -> str:
        material = json_dumps({
            "workflow_id": str(row["workflow_id"]),
            "workflow_version": int(row["workflow_version"]),
            "actor": str(row["actor"]),
            "input": json_loads(row["input_json"], {}),
        }).encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    def get_workflow_run(self, tenant_id: str, run_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM workflow_runs3 WHERE tenant_id=? AND id=?", (tenant_id, run_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def list_workflow_runs(self, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM workflow_runs3 WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",
                                        (tenant_id, max(1, min(int(limit), 500)))).fetchall())

    def active_workflow_runs(self, tenant_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        sql = "SELECT * FROM workflow_runs3 WHERE status='running'"
        args: list[Any] = []
        if tenant_id:
            sql += " AND tenant_id=?"
            args.append(tenant_id)
        sql += " ORDER BY created_at LIMIT ?"
        args.append(max(1, min(int(limit), 1000)))
        with self.connection() as c:
            return self._rows(c.execute(sql, tuple(args)).fetchall())

    def list_workflow_steps(self, run_id: str) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM workflow_steps3 WHERE run_id=? ORDER BY step_id", (run_id,)).fetchall())

    def update_workflow_step(self, run_id: str, step_id: str, **fields: Any) -> None:
        allowed = {"status", "task_id", "result", "error", "started_at", "finished_at"}
        items = [(k, v) for k, v in fields.items() if k in allowed]
        if not items:
            return
        with self.connection() as c:
            c.execute("UPDATE workflow_steps3 SET " + ",".join(f"{k}=?" for k, _ in items) +
                      " WHERE run_id=? AND step_id=?", tuple(v for _, v in items) + (run_id, step_id))

    def finish_workflow_run(self, run_id: str, status: str, context: dict[str, Any], error: str = "") -> None:
        with self.connection() as c:
            c.execute("UPDATE workflow_runs3 SET status=?,context_json=?,error=?,finished_at=? WHERE id=?",
                      (status, json_dumps(context), error[:4000], utcnow(), run_id))

    # ----- Scheduler -----
    def upsert_schedule(self, tenant_id: str, item: dict[str, Any], actor: str) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO schedules3(tenant_id,id,name,target_type,target_id,schedule_type,cron_expr,interval_seconds,timezone,
                payload_json,next_run_at,last_error,enabled,created_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tenant_id,id) DO UPDATE SET name=excluded.name,target_type=excluded.target_type,target_id=excluded.target_id,
                schedule_type=excluded.schedule_type,cron_expr=excluded.cron_expr,interval_seconds=excluded.interval_seconds,
                timezone=excluded.timezone,payload_json=excluded.payload_json,next_run_at=excluded.next_run_at,
                enabled=excluded.enabled,updated_at=excluded.updated_at""",
                (tenant_id, item["id"], item.get("name") or item["id"], item["target_type"], item["target_id"],
                 item["schedule_type"], item.get("cron_expr", ""), int(item.get("interval_seconds", 0)),
                 item.get("timezone", "UTC"), json_dumps(item.get("payload", {})), item["next_run_at"], "",
                 int(bool(item.get("enabled", True))), actor, now, now),
            )
        return self.get_schedule(tenant_id, item["id"]) or {}

    def get_schedule(self, tenant_id: str, schedule_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM schedules3 WHERE tenant_id=? AND id=?", (tenant_id, schedule_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def list_schedules(self, tenant_id: str) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM schedules3 WHERE tenant_id=? ORDER BY id", (tenant_id,)).fetchall())

    def due_schedules(self, now: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute(
                "SELECT * FROM schedules3 WHERE enabled=1 AND next_run_at<=? ORDER BY next_run_at LIMIT ?",
                (now, max(1, min(int(limit), 500))),
            ).fetchall())

    def mark_schedule_run(self, tenant_id: str, schedule_id: str, next_run_at: str, error: str = "") -> None:
        now = utcnow()
        with self.connection() as c:
            c.execute("UPDATE schedules3 SET last_run_at=?,next_run_at=?,last_error=?,updated_at=? WHERE tenant_id=? AND id=?",
                      (now, next_run_at, error[:2000], now, tenant_id, schedule_id))

    # ----- Events -----
    def upsert_event_rule(self, tenant_id: str, rule: dict[str, Any], actor: str) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO event_rules3(tenant_id,id,name,event_type,target_type,target_id,filter_json,payload_template_json,
                enabled,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tenant_id,id) DO UPDATE SET name=excluded.name,event_type=excluded.event_type,
                target_type=excluded.target_type,target_id=excluded.target_id,filter_json=excluded.filter_json,
                payload_template_json=excluded.payload_template_json,enabled=excluded.enabled,updated_at=excluded.updated_at""",
                (tenant_id, rule["id"], rule.get("name") or rule["id"], rule["event_type"], rule["target_type"],
                 rule["target_id"], json_dumps(rule.get("filter", {})), json_dumps(rule.get("payload_template", {})),
                 int(bool(rule.get("enabled", True))), actor, now, now),
            )
        with self.connection() as c:
            row = c.execute("SELECT * FROM event_rules3 WHERE tenant_id=? AND id=?", (tenant_id, rule["id"])).fetchone()
            return self._decode(dict(row)) if row else {}

    def list_event_rules(self, tenant_id: str, event_type: str | None = None) -> list[dict[str, Any]]:
        with self.connection() as c:
            if event_type:
                rows = c.execute("SELECT * FROM event_rules3 WHERE tenant_id=? AND event_type=? AND enabled=1 ORDER BY id",
                                 (tenant_id, event_type)).fetchall()
            else:
                rows = c.execute("SELECT * FROM event_rules3 WHERE tenant_id=? ORDER BY id", (tenant_id,)).fetchall()
            return self._rows(rows)

    def emit_event(self, tenant_id: str, event_type: str, source: str, payload: dict[str, Any], dedupe_key: str = "") -> dict[str, Any]:
        now = utcnow()
        event_id = str(uuid.uuid4())
        with self.connection() as c:
            try:
                c.execute(
                    "INSERT INTO events3(id,tenant_id,event_type,source,dedupe_key,payload_json,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
                    (event_id, tenant_id, event_type, source, dedupe_key, json_dumps(payload), "pending", now),
                )
            except Exception:
                if dedupe_key:
                    row = c.execute("SELECT * FROM events3 WHERE tenant_id=? AND source=? AND dedupe_key=?",
                                    (tenant_id, source, dedupe_key)).fetchone()
                    if row:
                        return self._decode(dict(row))
                raise
        return self.get_event(tenant_id, event_id) or {}

    def get_event(self, tenant_id: str, event_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM events3 WHERE tenant_id=? AND id=?", (tenant_id, event_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def pending_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM events3 WHERE status='pending' ORDER BY created_at LIMIT ?",
                                        (max(1, min(int(limit), 500)),)).fetchall())

    def finish_event(self, event_id: str, status: str, error: str = "") -> None:
        with self.connection() as c:
            c.execute("UPDATE events3 SET status=?,attempts=attempts+1,error=?,processed_at=? WHERE id=?",
                      (status, error[:2000], utcnow(), event_id))

    # ----- Evaluation -----
    def upsert_evaluation_suite(self, tenant_id: str, suite: dict[str, Any], actor: str) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO evaluation_suites3(tenant_id,id,name,description,agent_id,cases_json,variants_json,enabled,
                created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tenant_id,id) DO UPDATE SET name=excluded.name,description=excluded.description,
                agent_id=excluded.agent_id,cases_json=excluded.cases_json,variants_json=excluded.variants_json,
                enabled=excluded.enabled,updated_at=excluded.updated_at""",
                (tenant_id, suite["id"], suite.get("name") or suite["id"], suite.get("description", ""), suite["agent_id"],
                 json_dumps(suite["cases"]), json_dumps(suite["variants"]), int(bool(suite.get("enabled", True))),
                 actor, now, now),
            )
        return self.get_evaluation_suite(tenant_id, suite["id"]) or {}

    def get_evaluation_suite(self, tenant_id: str, suite_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM evaluation_suites3 WHERE tenant_id=? AND id=?", (tenant_id, suite_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def list_evaluation_suites(self, tenant_id: str) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM evaluation_suites3 WHERE tenant_id=? ORDER BY id", (tenant_id,)).fetchall())

    def create_evaluation_run(self, tenant_id: str, suite_id: str, actor: str) -> dict[str, Any]:
        run_id, now = str(uuid.uuid4()), utcnow()
        with self.connection() as c:
            c.execute("INSERT INTO evaluation_runs3(id,tenant_id,suite_id,status,actor,created_at) VALUES(?,?,?,?,?,?)",
                      (run_id, tenant_id, suite_id, "running", actor, now))
        return self.get_evaluation_run(tenant_id, run_id) or {}

    def get_evaluation_run(self, tenant_id: str, run_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM evaluation_runs3 WHERE tenant_id=? AND id=?", (tenant_id, run_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def active_evaluation_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM evaluation_runs3 WHERE status='running' ORDER BY created_at LIMIT ?",
                                        (max(1, min(int(limit), 500)),)).fetchall())

    def add_evaluation_result(self, tenant_id: str, run_id: str, case_id: str, variant: str, task_id: str) -> None:
        with self.connection() as c:
            c.execute(
                """INSERT INTO evaluation_results3(id,tenant_id,run_id,case_id,variant,task_id,status,created_at)
                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(run_id,case_id,variant) DO NOTHING""",
                (str(uuid.uuid4()), tenant_id, run_id, case_id, variant, task_id, "running", utcnow()),
            )

    def list_evaluation_results(self, run_id: str) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM evaluation_results3 WHERE run_id=? ORDER BY case_id,variant", (run_id,)).fetchall())

    def update_evaluation_result_from_task(self, result_id: str, task: dict[str, Any]) -> None:
        duration_ms = 0.0
        if task.get("started_at") and task.get("finished_at"):
            try:
                a = datetime.fromisoformat(task["started_at"])
                b = datetime.fromisoformat(task["finished_at"])
                duration_ms = max(0.0, (b - a).total_seconds() * 1000)
            except ValueError:
                pass
        with self.connection() as c:
            c.execute(
                """UPDATE evaluation_results3 SET status=?,outcome_status=?,outcome_score=?,cost_credits=?,duration_ms=?,
                result=?,error=?,finished_at=? WHERE id=?""",
                (task["status"], task.get("outcome_status"), task.get("outcome_score"), float(task.get("cost_credits") or 0),
                 duration_ms, task.get("result"), task.get("error") or "", utcnow(), result_id),
            )

    def finish_evaluation_run(self, run_id: str, status: str, summary: dict[str, Any], error: str = "") -> None:
        with self.connection() as c:
            c.execute("UPDATE evaluation_runs3 SET status=?,summary_json=?,error=?,finished_at=? WHERE id=?",
                      (status, json_dumps(summary), error[:2000], utcnow(), run_id))

    # ----- Artifacts / SLO / economics -----
    def register_artifact(self, tenant_id: str, artifact: dict[str, Any], actor: str) -> dict[str, Any]:
        artifact_id = artifact.get("id") or str(uuid.uuid4())
        with self.connection() as c:
            c.execute(
                """INSERT INTO artifacts3(id,tenant_id,task_id,workflow_run_id,name,content_type,storage_uri,sha256,size_bytes,
                metadata_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (artifact_id, tenant_id, artifact.get("task_id"), artifact.get("workflow_run_id"), artifact["name"],
                 artifact.get("content_type", "application/octet-stream"), artifact["storage_uri"], artifact["sha256"],
                 int(artifact["size_bytes"]), json_dumps(artifact.get("metadata", {})), actor, utcnow()),
            )
            row = c.execute("SELECT * FROM artifacts3 WHERE id=?", (artifact_id,)).fetchone()
            return self._decode(dict(row))

    def list_artifacts(self, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM artifacts3 WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",
                                        (tenant_id, max(1, min(int(limit), 500)))).fetchall())

    def set_slo_policy(self, tenant_id: str, policy: dict[str, Any]) -> None:
        with self.connection() as c:
            c.execute(
                """INSERT INTO slo_policies3(tenant_id,id,metric,comparator,target,window_hours,severity,enabled,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id,id) DO UPDATE SET metric=excluded.metric,
                comparator=excluded.comparator,target=excluded.target,window_hours=excluded.window_hours,
                severity=excluded.severity,enabled=excluded.enabled,updated_at=excluded.updated_at""",
                (tenant_id, policy["id"], policy["metric"], policy["comparator"], float(policy["target"]),
                 int(policy.get("window_hours", 24)), policy.get("severity", "warning"),
                 int(bool(policy.get("enabled", True))), utcnow()),
            )

    def list_slo_policies(self, tenant_id: str) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM slo_policies3 WHERE tenant_id=? ORDER BY id", (tenant_id,)).fetchall())

    def set_tenant_economics(self, tenant_id: str, currency: str, currency_per_credit: float, target_worker_utilization: float = .70) -> None:
        with self.connection() as c:
            c.execute(
                """INSERT INTO tenant_settings3(tenant_id,currency,currency_per_credit,target_worker_utilization,updated_at)
                VALUES(?,?,?,?,?) ON CONFLICT(tenant_id) DO UPDATE SET currency=excluded.currency,
                currency_per_credit=excluded.currency_per_credit,target_worker_utilization=excluded.target_worker_utilization,
                updated_at=excluded.updated_at""",
                (tenant_id, currency.upper()[:8], max(0.0, float(currency_per_credit)),
                 max(.1, min(float(target_worker_utilization), .95)), utcnow()),
            )

    def get_tenant_economics(self, tenant_id: str) -> dict[str, Any]:
        with self.connection() as c:
            row = c.execute("SELECT * FROM tenant_settings3 WHERE tenant_id=?", (tenant_id,)).fetchone()
            if row:
                return dict(row)
        return {"tenant_id": tenant_id, "currency": "USD", "currency_per_credit": .01, "target_worker_utilization": .70}

    def usage_summary(self, tenant_id: str, hours: int = 24) -> dict[str, Any]:
        since = (datetime.now(timezone.utc) - timedelta(hours=max(1, int(hours)))).isoformat(timespec="seconds")
        with self.connection() as c:
            row = c.execute(
                """SELECT COUNT(*) turns,COALESCE(SUM(cost_credits),0) credits,
                COALESCE(SUM(input_tokens),0) input_tokens,COALESCE(SUM(output_tokens),0) output_tokens
                FROM usage_events2 WHERE tenant_id=? AND created_at>=?""", (tenant_id, since)).fetchone()
            tasks = c.execute(
                """SELECT COUNT(*) total,
                COALESCE(SUM(CASE WHEN status='succeeded' THEN 1 ELSE 0 END),0) succeeded,
                COALESCE(SUM(CASE WHEN status='dead_letter' THEN 1 ELSE 0 END),0) dead
                FROM tasks2 WHERE tenant_id=? AND created_at>=?""", (tenant_id, since)).fetchone()
        return {"since": since, "turns": int(row["turns"]), "credits": float(row["credits"]),
                "input_tokens": int(row["input_tokens"]), "output_tokens": int(row["output_tokens"]),
                "tasks": int(tasks["total"]), "succeeded": int(tasks["succeeded"]), "dead_letter": int(tasks["dead"])}

    # ----- Service leader leases -----
    def acquire_service_lease(self, name: str, owner: str, lease_seconds: int = 30) -> bool:
        now = utcnow()
        expires = (datetime.now(timezone.utc) + timedelta(seconds=max(5, int(lease_seconds)))).isoformat(timespec="seconds")
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                changed = c.execute(
                    "UPDATE service_leases3 SET owner=?,expires_at=?,heartbeat_at=? WHERE name=? AND (owner=? OR expires_at<=?)",
                    (owner, expires, now, name, owner, now),
                ).rowcount
                if not changed:
                    c.execute(
                        "INSERT OR IGNORE INTO service_leases3(name,owner,expires_at,heartbeat_at) VALUES(?,?,?,?)",
                        (name, owner, expires, now),
                    )
                row = c.execute("SELECT owner,expires_at FROM service_leases3 WHERE name=?", (name,)).fetchone()
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        return bool(row and row["owner"] == owner and row["expires_at"] > now)

    def release_service_lease(self, name: str, owner: str) -> bool:
        with self.connection() as c:
            return bool(c.execute("DELETE FROM service_leases3 WHERE name=? AND owner=?", (name, owner)).rowcount)

    def list_service_leases(self) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM service_leases3 ORDER BY name").fetchall())

    # ----- Outbox -----
    def enqueue_outbox(self, tenant_id: str, topic: str, destination: str, payload: dict[str, Any], signature: str = "") -> str:
        item_id = str(uuid.uuid4())
        now = utcnow()
        with self.connection() as c:
            c.execute(
                "INSERT INTO outbox3(id,tenant_id,topic,destination,payload_json,signature,status,next_attempt_at,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (item_id, tenant_id, topic, destination, json_dumps(payload), signature, "pending", now, now),
            )
        return item_id

    def due_outbox(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute(
                "SELECT * FROM outbox3 WHERE status='pending' AND next_attempt_at<=? ORDER BY created_at LIMIT ?",
                (utcnow(), max(1, min(int(limit), 500))),
            ).fetchall())

    def claim_outbox(self, owner: str, lease_seconds: int = 30, limit: int = 100) -> list[dict[str, Any]]:
        now = utcnow()
        expires = (datetime.now(timezone.utc) + timedelta(seconds=max(5, int(lease_seconds)))).isoformat(timespec="seconds")
        limit = max(1, min(int(limit), 500))
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                query = (
                    "SELECT * FROM outbox3 WHERE "
                    "(status='pending' AND next_attempt_at<=?) OR "
                    "(status='processing' AND claim_expires_at<=?) "
                    "ORDER BY created_at LIMIT ?"
                )
                if self.backend_kind == "postgres":
                    query += " FOR UPDATE SKIP LOCKED"
                rows = c.execute(query, (now, now, limit)).fetchall()
                claimed: list[dict[str, Any]] = []
                for row in rows:
                    item_id = row["id"]
                    changed = c.execute(
                        """UPDATE outbox3 SET status='processing',claim_owner=?,claim_expires_at=?
                        WHERE id=? AND ((status='pending' AND next_attempt_at<=?) OR
                        (status='processing' AND claim_expires_at<=?))""",
                        (owner, expires, item_id, now, now),
                    ).rowcount
                    if changed:
                        item = dict(row)
                        item.update(status="processing", claim_owner=owner, claim_expires_at=expires)
                        claimed.append(self._decode(item))
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        return claimed

    def finish_outbox(self, item_id: str, success: bool, error: str = "", retry_seconds: int = 60, owner: str | None = None) -> bool:
        MAX_OUTBOX_ATTEMPTS = 20
        with self.connection() as c:
            owner_clause = " AND status='processing' AND claim_owner=?" if owner else ""
            owner_args = (owner,) if owner else ()
            if success:
                result = c.execute(
                    "UPDATE outbox3 SET status='delivered',attempts=attempts+1,last_error='',delivered_at=?,claim_owner=NULL,claim_expires_at=NULL WHERE id=?" + owner_clause,
                    (utcnow(), item_id) + owner_args,
                )
            else:
                attempts = int(c.execute("SELECT attempts FROM outbox3 WHERE id=?", (item_id,)).fetchone()[0] or 0) + 1
                if attempts >= MAX_OUTBOX_ATTEMPTS:
                    result = c.execute(
                        "UPDATE outbox3 SET status='dead_letter',attempts=?,last_error=?,claim_owner=NULL,claim_expires_at=NULL WHERE id=?" + owner_clause,
                        (attempts, error[:2000], item_id) + owner_args,
                    )
                else:
                    retry_at = (datetime.now(timezone.utc) + timedelta(seconds=max(1, retry_seconds))).isoformat(timespec="seconds")
                    result = c.execute(
                        "UPDATE outbox3 SET status='pending',attempts=?,last_error=?,next_attempt_at=?,claim_owner=NULL,claim_expires_at=NULL WHERE id=?" + owner_clause,
                        (attempts, error[:2000], retry_at, item_id) + owner_args,
                    )
            return bool(result.rowcount)

    # ----- Semantic memory vectors -----
    def upsert_memory_vector(self, tenant_id: str, memory_id: str, agent_id: str | None, vector: list[float]) -> None:
        with self.connection() as c:
            memory = c.execute("SELECT tenant_id FROM memories2 WHERE id=?", (memory_id,)).fetchone()
            if not memory:
                raise ValueError("memory does not exist")
            if memory[0] != tenant_id:
                raise ValueError("memory id belongs to another tenant")
            existing = c.execute("SELECT tenant_id FROM memory_vectors3 WHERE memory_id=?", (memory_id,)).fetchone()
            if existing and existing[0] != tenant_id:
                raise ValueError("memory vector belongs to another tenant")
            c.execute(
                """INSERT INTO memory_vectors3(memory_id,tenant_id,agent_id,dimension,vector_json,updated_at)
                VALUES(?,?,?,?,?,?) ON CONFLICT(memory_id) DO UPDATE SET
                agent_id=excluded.agent_id,dimension=excluded.dimension,vector_json=excluded.vector_json,updated_at=excluded.updated_at
                WHERE memory_vectors3.tenant_id=excluded.tenant_id""",
                (memory_id, tenant_id, agent_id, len(vector), json_dumps(vector), utcnow()),
            )

    def list_memory_vectors(self, tenant_id: str, agent_id: str | None = None, limit: int = 5000) -> list[dict[str, Any]]:
        with self.connection() as c:
            if agent_id:
                rows = c.execute(
                    """SELECT v.*,m.title,m.content,m.tags_json FROM memory_vectors3 v
                    JOIN memories2 m ON m.id=v.memory_id AND m.tenant_id=v.tenant_id WHERE v.tenant_id=? AND (v.agent_id IS NULL OR v.agent_id=?)
                    ORDER BY v.updated_at DESC LIMIT ?""",
                    (tenant_id, agent_id, max(1, min(int(limit), 20000))),
                ).fetchall()
            else:
                rows = c.execute(
                    """SELECT v.*,m.title,m.content,m.tags_json FROM memory_vectors3 v
                    JOIN memories2 m ON m.id=v.memory_id AND m.tenant_id=v.tenant_id WHERE v.tenant_id=? ORDER BY v.updated_at DESC LIMIT ?""",
                    (tenant_id, max(1, min(int(limit), 20000))),
                ).fetchall()
            return self._rows(rows)
