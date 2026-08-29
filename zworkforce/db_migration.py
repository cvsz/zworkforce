from __future__ import annotations

import hashlib

from .db_base import json_dumps, json_loads, utcnow

class MigrationMixin:
    def _migrate_v1_if_needed(self) -> None:
        with self.connection() as c:
            if not self._table_exists(c, "agents") or not self._table_exists(c, "tasks"):
                return
            marker = c.execute("SELECT value FROM schema_meta WHERE key='v1_copy_complete'").fetchone()
            if marker:
                return
            if self.backend_kind == "postgres":
                c.execute("SELECT pg_advisory_xact_lock(?)", (_POSTGRES_SCHEMA_LOCK_KEY,))
            else:
                c.execute("BEGIN IMMEDIATE")
            try:
                now = utcnow()
                for row in c.execute("SELECT * FROM agents").fetchall():
                    r = dict(row)
                    allowed = ["calculator", "workspace_list", "workspace_read", "http_get", "agent_delegate"]
                    approval = ["shell_exec", "workspace_write", "memory_put", "http_request"]
                    c.execute(
                        """INSERT INTO agents2(
                        tenant_id,id,name,description,department,default_tier,max_cost_credits,max_iterations,max_subagents,
                        required_approvals,requires_approval_for_mutations,system_prompt,allowed_tools_json,approval_tools_json,
                        skill_ids_json,enabled,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(tenant_id,id) DO UPDATE SET name=excluded.name,description=excluded.description,
                        department=excluded.department,default_tier=excluded.default_tier,max_cost_credits=excluded.max_cost_credits,
                        max_iterations=excluded.max_iterations,max_subagents=excluded.max_subagents,
                        requires_approval_for_mutations=excluded.requires_approval_for_mutations,system_prompt=excluded.system_prompt,
                        enabled=excluded.enabled,updated_at=excluded.updated_at""",
                        (
                            self.default_tenant,
                            r["id"], r["name"], r.get("description", ""), r.get("department", "general"), r.get("default_tier", "terra"),
                            r.get("max_cost_credits", 50), r.get("max_iterations", 8), r.get("max_subagents", 2),
                            1, r.get("requires_approval_for_mutations", 1), r.get("system_prompt", ""), json_dumps(allowed), json_dumps(approval),
                            "[]", r.get("enabled", 1), r.get("created_at", now), r.get("updated_at", now),
                        ),
                    )
                for row in c.execute("SELECT * FROM tasks").fetchall():
                    r = dict(row)
                    run_after = r.get("created_at") or now
                    status = r.get("status", "failed")
                    if status == "running":
                        status = "queued"
                    c.execute(
                        """INSERT OR IGNORE INTO tasks2(
                        id,tenant_id,agent_id,prompt,created_by,status,tier,model,provider_name,mutating,parent_task_id,depth,
                        required_approvals,approved_at,priority,attempt,max_attempts,run_after,result,error,input_tokens,cached_tokens,
                        output_tokens,cost_credits,iterations,cancel_requested,success_criteria_json,outcome_status,outcome_score,
                        outcome_details_json,created_at,updated_at,started_at,finished_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            r["id"], self.default_tenant, r["agent_id"], r.get("prompt", ""), "legacy", status, r.get("tier", "terra"),
                            r.get("model", ""), "legacy", r.get("mutating", 0), r.get("parent_task_id"), r.get("depth", 0),
                            1 if r.get("approval_required") else 0, r.get("approved_at"), 0, 0, 3, run_after, r.get("result"), r.get("error"),
                            r.get("input_tokens", 0), r.get("cached_tokens", 0), r.get("output_tokens", 0), r.get("cost_credits", 0),
                            r.get("iterations", 0), r.get("cancel_requested", 0), "[]", "passed" if status == "succeeded" else None,
                            1.0 if status == "succeeded" else None, "{}", r.get("created_at", now), r.get("updated_at", now),
                            r.get("started_at"), r.get("finished_at"),
                        ),
                    )
                if self._table_exists(c, "usage_events"):
                    for row in c.execute("SELECT * FROM usage_events ORDER BY id").fetchall():
                        r = dict(row)
                        c.execute(
                            """INSERT INTO usage_events2(tenant_id,task_id,agent_id,department,tier,provider_name,model,input_tokens,
                            cached_tokens,output_tokens,cost_credits,created_at) SELECT ?,?,?,?,?,?,?,?,?,?,?,? WHERE NOT EXISTS(
                            SELECT 1 FROM usage_events2 WHERE task_id=? AND created_at=? AND input_tokens=? AND output_tokens=?)""",
                            (
                                self.default_tenant, r["task_id"], r["agent_id"], r.get("department", "unknown"), r.get("tier", "terra"),
                                "legacy", r.get("model", ""), r.get("input_tokens", 0), r.get("cached_tokens", 0), r.get("output_tokens", 0),
                                r.get("cost_credits", 0), r.get("created_at", now), r["task_id"], r.get("created_at", now),
                                r.get("input_tokens", 0), r.get("output_tokens", 0),
                            ),
                        )
                if self._table_exists(c, "budgets"):
                    for row in c.execute("SELECT * FROM budgets").fetchall():
                        r = dict(row)
                        c.execute(
                            """INSERT INTO budgets2(tenant_id,scope_type,scope_id,period,limit_credits,updated_at) VALUES(?,?,?,?,?,?)
                            ON CONFLICT(tenant_id,scope_type,scope_id,period) DO UPDATE SET limit_credits=excluded.limit_credits,updated_at=excluded.updated_at""",
                            (self.default_tenant, r["scope_type"], r["scope_id"], r["period"], r["limit_credits"], r.get("updated_at", now)),
                        )
                for row in c.execute("SELECT id,approved_by,approved_at,approval_required FROM tasks WHERE approved_by IS NOT NULL AND approved_at IS NOT NULL").fetchall():
                    r = dict(row)
                    if r.get("approval_required"):
                        c.execute(
                            "INSERT OR IGNORE INTO approvals2(tenant_id,task_id,actor,decision,comment,created_at) VALUES(?,?,?,?,?,?)",
                            (self.default_tenant, r["id"], r["approved_by"], "approve", "migrated from v1", r["approved_at"]),
                        )
                if self._table_exists(c, "audit_events"):
                    prev = c.execute("SELECT event_hash FROM audit_events2 WHERE tenant_id=? ORDER BY id DESC LIMIT 1", (self.default_tenant,)).fetchone()
                    prev_hash = prev[0] if prev else ""
                    for row in c.execute("SELECT * FROM audit_events ORDER BY id").fetchall():
                        r = dict(row)
                        details = json_loads(r.get("details_json"), {})
                        created = r.get("created_at", now)
                        material = json_dumps({"tenant_id": self.default_tenant, "actor": r.get("actor", "legacy"), "action": r.get("action", "legacy.event"), "target_type": r.get("target_type", "legacy"), "target_id": r.get("target_id", ""), "details": details, "prev_hash": prev_hash, "created_at": created})
                        event_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
                        c.execute(
                            "INSERT INTO audit_events2(tenant_id,actor,action,target_type,target_id,details_json,prev_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                            (self.default_tenant, r.get("actor", "legacy"), r.get("action", "legacy.event"), r.get("target_type", "legacy"), r.get("target_id", ""), json_dumps(details), prev_hash, event_hash, created),
                        )
                        prev_hash = event_hash
                c.execute("INSERT INTO schema_meta(key,value) VALUES('v1_copy_complete','1')")
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
