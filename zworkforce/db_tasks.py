from __future__ import annotations

from typing import Any

from .db_base import json_dumps, utc_after, utcnow

class TaskMixin:
    def create_task(self, t: dict[str, Any], idempotency_key: str | None = None, request_hash: str = "") -> tuple[dict[str, Any], bool]:
        now = utcnow()
        tenant_id, actor = t["tenant_id"], t["created_by"]
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                if idempotency_key:
                    hit = c.execute(
                        "SELECT task_id,request_hash FROM idempotency_keys2 WHERE tenant_id=? AND actor=? AND key=?",
                        (tenant_id, actor, idempotency_key),
                    ).fetchone()
                    if hit:
                        if request_hash and hit["request_hash"] != request_hash:
                            raise ValueError("idempotency key was already used with a different request")
                        row = c.execute("SELECT * FROM tasks2 WHERE id=? AND tenant_id=?", (hit["task_id"], tenant_id)).fetchone()
                        c.execute("COMMIT")
                        return self._decode(dict(row)), False
                c.execute(
                    """INSERT INTO tasks2(id,tenant_id,agent_id,prompt,created_by,status,tier,model,provider_name,mutating,parent_task_id,
                    depth,required_approvals,priority,attempt,max_attempts,run_after,success_criteria_json,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        t["id"], tenant_id, t["agent_id"], t["prompt"], actor, t["status"], t["tier"], t["model"],
                        t.get("provider_name", ""), int(t.get("mutating", False)), t.get("parent_task_id"), int(t.get("depth", 0)),
                        int(t.get("required_approvals", 0)), int(t.get("priority", 0)), 0, int(t.get("max_attempts", 3)),
                        t.get("run_after", now), json_dumps(t.get("success_criteria", [])), now, now,
                    ),
                )
                if idempotency_key:
                    c.execute(
                        "INSERT INTO idempotency_keys2(tenant_id,actor,key,task_id,request_hash,created_at) VALUES(?,?,?,?,?,?)",
                        (tenant_id, actor, idempotency_key, t["id"], request_hash, now),
                    )
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        self.task_event(tenant_id, t["id"], "created", actor, {"status": t["status"], "tier": t["tier"]})
        return self.get_task(tenant_id, t["id"]) or {}, True

    def get_task(self, tenant_id: str, task_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM tasks2 WHERE tenant_id=? AND id=?", (tenant_id, task_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def get_task_any_tenant(self, task_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM tasks2 WHERE id=?", (task_id,)).fetchone()
            return self._decode(dict(row)) if row else None

    def list_tasks(self, tenant_id: str, limit: int = 100, offset: int = 0, status: str | None = None, agent_id: str | None = None) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        clauses, args = ["tenant_id=?"], [tenant_id]
        if status:
            clauses.append("status=?")
            args.append(status)
        if agent_id:
            clauses.append("agent_id=?")
            args.append(agent_id)
        sql = "SELECT * FROM tasks2 WHERE " + " AND ".join(clauses) + " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        args += [limit, offset]
        with self.connection() as c:
            return self._rows(c.execute(sql, tuple(args)).fetchall())

    def update_task(self, task_id: str, **fields: Any) -> None:
        allowed = {
            "status", "tier", "model", "provider_name", "approved_at", "result", "error", "input_tokens", "cached_tokens",
            "output_tokens", "cost_credits", "iterations", "cancel_requested", "started_at", "finished_at", "priority", "run_after",
            "attempt", "lease_owner", "lease_expires_at", "heartbeat_at", "outcome_status", "outcome_score", "outcome_details_json",
        }
        items = [(k, v) for k, v in fields.items() if k in allowed]
        if not items:
            return
        items.append(("updated_at", utcnow()))
        sql = "UPDATE tasks2 SET " + ",".join(f"{k}=?" for k, _ in items) + " WHERE id=?"
        with self.connection() as c:
            c.execute(sql, tuple(v for _, v in items) + (task_id,))

    def claim_next_task(self, worker_id: str, lease_seconds: int) -> dict[str, Any] | None:
        now = utcnow()
        lease_until = utc_after(lease_seconds)
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                row = c.execute(
                    """SELECT * FROM tasks2 WHERE status='queued' AND cancel_requested=0 AND run_after<=?
                    ORDER BY priority DESC,created_at ASC LIMIT 1""",
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
                changed = c.execute(
                    """UPDATE tasks2 SET status='running',attempt=?,lease_owner=?,lease_expires_at=?,heartbeat_at=?,
                    started_at=COALESCE(started_at,?),updated_at=? WHERE id=? AND status='queued'""",
                    (next_attempt, worker_id, lease_until, now, now, now, task_id),
                ).rowcount
                if not changed:
                    c.execute("ROLLBACK")
                    return None
                row = c.execute("SELECT * FROM tasks2 WHERE id=?", (task_id,)).fetchone()
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        task = self._decode(dict(row))
        self.task_event(task["tenant_id"], task_id, "claimed", worker_id, {"attempt": next_attempt, "lease_expires_at": lease_until})
        return task

    def heartbeat(self, task_id: str, worker_id: str, lease_seconds: int) -> bool:
        now = utcnow()
        with self.connection() as c:
            changed = c.execute(
                """UPDATE tasks2 SET heartbeat_at=?,lease_expires_at=?,updated_at=?
                WHERE id=? AND status='running' AND lease_owner=?""",
                (now, utc_after(lease_seconds), now, task_id, worker_id),
            ).rowcount
            return bool(changed)

    def release_for_retry(self, task: dict[str, Any], error: str, delay_seconds: int) -> str:
        now = utcnow()
        if int(task["attempt"]) >= int(task["max_attempts"]):
            self.update_task(task["id"], status="dead_letter", error=error, finished_at=now, lease_owner=None, lease_expires_at=None, heartbeat_at=None)
            status = "dead_letter"
        else:
            self.update_task(task["id"], status="queued", error=error, run_after=utc_after(delay_seconds), lease_owner=None, lease_expires_at=None, heartbeat_at=None)
            status = "queued"
        self.task_event(task["tenant_id"], task["id"], "retry" if status == "queued" else "dead_letter", "runtime", {"error": error[:500], "attempt": task["attempt"]})
        return status

    def requeue_expired_leases(self) -> dict[str, int]:
        now = utcnow()
        requeued = dead = 0
        with self.connection() as c:
            rows = c.execute("SELECT id,tenant_id,attempt,max_attempts FROM tasks2 WHERE status='running' AND lease_expires_at IS NOT NULL AND lease_expires_at<?", (now,)).fetchall()
            for row in rows:
                if int(row["attempt"]) >= int(row["max_attempts"]):
                    c.execute("UPDATE tasks2 SET status='dead_letter',error='worker lease expired',finished_at=?,lease_owner=NULL,lease_expires_at=NULL,updated_at=? WHERE id=?", (now, now, row["id"]))
                    dead += 1
                else:
                    c.execute("UPDATE tasks2 SET status='queued',error='worker lease expired; requeued',run_after=?,lease_owner=NULL,lease_expires_at=NULL,heartbeat_at=NULL,updated_at=? WHERE id=?", (now, now, row["id"]))
                    requeued += 1
        return {"requeued": requeued, "dead_lettered": dead}

    def task_event(self, tenant_id: str, task_id: str, event_type: str, actor: str, details: dict[str, Any] | None = None) -> None:
        with self.connection() as c:
            safe_details = details or {}
            c.execute(
                "INSERT INTO task_events2(tenant_id,task_id,event_type,actor,details_json,created_at) VALUES(?,?,?,?,?,?)",
                (tenant_id, task_id, event_type, actor, json_dumps(safe_details), utcnow()),
            )
            summary = {
                key: safe_details[key]
                for key in ("status", "attempt", "outcome_status", "outcome_score")
                if key in safe_details
            }
            if "status" not in summary:
                inferred_status = {
                    "claimed": "running",
                    "created": "queued",
                    "retry": "queued",
                    "manual_retry": "queued",
                    "succeeded": "succeeded",
                    "failed": "failed",
                    "canceled": "canceled",
                    "dead_letter": "dead_letter",
                }.get(event_type)
                if inferred_status:
                    summary["status"] = inferred_status
            self._append_dashboard_event_cursor(
                c,
                tenant_id,
                "task.changed",
                "task",
                task_id,
                {"summary": summary},
            )

    def list_task_events(self, tenant_id: str, task_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM task_events2 WHERE tenant_id=? AND task_id=? ORDER BY id ASC LIMIT ?", (tenant_id, task_id, max(1, min(limit, 1000)))).fetchall())

    def approval_decision(self, tenant_id: str, task_id: str, actor: str, decision: str, comment: str = "") -> dict[str, Any]:
        now = utcnow()
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                task = c.execute("SELECT * FROM tasks2 WHERE tenant_id=? AND id=?", (tenant_id, task_id)).fetchone()
                if not task:
                    raise ValueError("task not found")
                if task["status"] != "waiting_approval":
                    raise ValueError("task is not waiting for approval")
                if actor == task["created_by"]:
                    raise ValueError("requester cannot approve or reject their own task")
                c.execute(
                    "INSERT INTO approvals2(tenant_id,task_id,actor,decision,comment,created_at) VALUES(?,?,?,?,?,?)",
                    (tenant_id, task_id, actor, decision, comment[:2000], now),
                )
                if decision == "reject":
                    c.execute("UPDATE tasks2 SET status='canceled',error='approval rejected',finished_at=?,updated_at=? WHERE id=?", (now, now, task_id))
                else:
                    count = c.execute("SELECT COUNT(*) FROM approvals2 WHERE task_id=? AND decision='approve'", (task_id,)).fetchone()[0]
                    if count >= int(task["required_approvals"]):
                        c.execute("UPDATE tasks2 SET status='queued',approved_at=?,run_after=?,updated_at=? WHERE id=?", (now, now, now, task_id))
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        self.task_event(tenant_id, task_id, f"approval.{decision}", actor, {"comment": comment[:500]})
        return self.get_task(tenant_id, task_id) or {}

    def list_approvals(self, tenant_id: str, task_id: str) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM approvals2 WHERE tenant_id=? AND task_id=? ORDER BY id", (tenant_id, task_id)).fetchall())
