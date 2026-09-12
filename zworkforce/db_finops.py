from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from .db_base import utcnow


class FinOpsMixin:
    def record_usage(self, task: dict[str, Any], provider_name: str, model: str, inp: int, cached: int, out: int, cost: float) -> None:
        agent = self.get_agent(task["tenant_id"], task["agent_id"]) or {"department": "unknown"}
        with self.connection() as c:
            c.execute(
                """INSERT INTO usage_events2(tenant_id,task_id,agent_id,department,tier,provider_name,model,input_tokens,cached_tokens,
                output_tokens,cost_credits,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (task["tenant_id"], task["id"], task["agent_id"], agent["department"], task["tier"], provider_name, model, inp, cached, out, cost, utcnow()),
            )
        self.append_dashboard_event(
            task["tenant_id"],
            "usage.changed",
            "task",
            task["id"],
            {"summary": {"provider": provider_name}},
        )

    def set_budget(self, tenant_id: str, scope_type: str, scope_id: str, period: str, limit: float) -> None:
        with self.connection() as c:
            c.execute(
                """INSERT INTO budgets2(tenant_id,scope_type,scope_id,period,limit_credits,updated_at) VALUES(?,?,?,?,?,?)
                ON CONFLICT(tenant_id,scope_type,scope_id,period) DO UPDATE SET limit_credits=excluded.limit_credits,updated_at=excluded.updated_at""",
                (tenant_id, scope_type, scope_id, period, max(0.0, float(limit)), utcnow()),
            )
        self.append_dashboard_event(
            tenant_id,
            "budget.changed",
            "budget",
            f"{scope_type}:{scope_id}:{period}",
            {"summary": {"operation": "upsert"}},
        )

    def list_budgets(self, tenant_id: str) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM budgets2 WHERE tenant_id=? ORDER BY scope_type,scope_id,period", (tenant_id,)).fetchall())

    def spent(self, tenant_id: str, scope_type: str, scope_id: str, period: str) -> float:
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) if period == "daily" else now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        clause, args = "tenant_id=?", [tenant_id]
        if scope_type == "department":
            clause += " AND department=?"; args.append(scope_id)
        elif scope_type == "agent":
            clause += " AND agent_id=?"; args.append(scope_id)
        with self.connection() as c:
            row = c.execute(f"SELECT COALESCE(SUM(cost_credits),0) FROM usage_events2 WHERE {clause} AND created_at>=?",
                            (*args, start.isoformat(timespec="seconds"))).fetchone()
            return float(row[0] or 0)

    def budget_violation(self, tenant_id: str, agent: dict[str, Any], global_daily_limit: float = 0) -> str | None:
        checks: list[tuple[str, str, str, float]] = []
        if global_daily_limit > 0:
            checks.append(("global", "global", "daily", global_daily_limit))
        for r in self.list_budgets(tenant_id):
            if r["scope_type"] == "global" or (r["scope_type"] == "agent" and r["scope_id"] == agent["id"]) or (r["scope_type"] == "department" and r["scope_id"] == agent["department"]):
                checks.append((r["scope_type"], r["scope_id"], r["period"], float(r["limit_credits"])))
        for st, sid, period, limit in checks:
            if self.spent(tenant_id, st, sid, period) >= limit:
                return f"{st}:{sid} {period} budget exhausted ({limit:g} credits)"
        return None

    def overview(self, tenant_id: str) -> dict[str, Any]:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(timespec="seconds")
        with self.connection() as c:
            active = c.execute("SELECT COUNT(*) FROM tasks2 WHERE tenant_id=? AND status IN ('queued','running','waiting_approval')", (tenant_id,)).fetchone()[0]
            queued = c.execute("SELECT COUNT(*) FROM tasks2 WHERE tenant_id=? AND status='queued'", (tenant_id,)).fetchone()[0]
            dead = c.execute("SELECT COUNT(*) FROM tasks2 WHERE tenant_id=? AND status='dead_letter'", (tenant_id,)).fetchone()[0]
            total = c.execute("SELECT COUNT(*) FROM tasks2 WHERE tenant_id=? AND created_at>=?", (tenant_id, since)).fetchone()[0]
            success = c.execute("SELECT COUNT(*) FROM tasks2 WHERE tenant_id=? AND created_at>=? AND status='succeeded'", (tenant_id, since)).fetchone()[0]
            outcomes = c.execute("SELECT COUNT(*) total,SUM(CASE WHEN outcome_status='passed' THEN 1 ELSE 0 END) passed FROM tasks2 WHERE tenant_id=? AND created_at>=? AND outcome_status IS NOT NULL", (tenant_id, since)).fetchone()
            cost = c.execute("SELECT COALESCE(SUM(cost_credits),0) FROM usage_events2 WHERE tenant_id=? AND created_at>=?", (tenant_id, since)).fetchone()[0]
            mix = self._rows(c.execute("SELECT tier,COALESCE(SUM(cost_credits),0) cost,COUNT(*) turns FROM usage_events2 WHERE tenant_id=? AND created_at>=? GROUP BY tier ORDER BY tier", (tenant_id, since)).fetchall())
            providers = self._rows(c.execute("SELECT provider_name,COALESCE(SUM(cost_credits),0) cost,COUNT(*) turns FROM usage_events2 WHERE tenant_id=? AND created_at>=? GROUP BY provider_name ORDER BY turns DESC", (tenant_id, since)).fetchall())
            top = self._rows(c.execute("SELECT agent_id,COALESCE(SUM(cost_credits),0) cost,COUNT(*) turns FROM usage_events2 WHERE tenant_id=? AND created_at>=? GROUP BY agent_id ORDER BY cost DESC LIMIT 8", (tenant_id, since)).fetchall())
            timing_rows = c.execute("SELECT created_at,started_at,finished_at FROM tasks2 WHERE tenant_id=? AND created_at>=?", (tenant_id, since)).fetchall()
        durations = [_seconds(r["started_at"], r["finished_at"]) for r in timing_rows if r["started_at"] and r["finished_at"]]
        queues = [_seconds(r["created_at"], r["started_at"]) for r in timing_rows if r["started_at"]]
        outcome_total = int(outcomes["total"] or 0)
        outcome_passed = int(outcomes["passed"] or 0)
        return {
            "active_tasks": active,
            "queued_tasks": queued,
            "dead_letter_tasks": dead,
            "tasks_24h": total,
            "success_rate": round(success / total * 100 if total else 100.0, 2),
            "outcome_pass_rate": round(outcome_passed / outcome_total * 100 if outcome_total else 100.0, 2),
            "credits_24h": round(float(cost or 0), 6),
            "cost_per_success": round(float(cost or 0) / max(1, outcome_passed), 6) if outcome_passed else 0.0,
            "p95_duration_seconds": round(percentile(durations, .95), 3) if durations else 0.0,
            "avg_queue_seconds": round(sum(queues) / len(queues), 3) if queues else 0.0,
            "model_mix": mix,
            "provider_mix": providers,
            "top_cost_agents": top,
        }

    def recommendations(self, tenant_id: str, days: int = 7) -> list[dict[str, Any]]:
        since = (datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 90)))).isoformat(timespec="seconds")
        with self.connection() as c:
            rows = c.execute(
                """SELECT agent_id,tier,COUNT(*) n,AVG(iterations) avg_iterations,AVG(cost_credits) avg_cost,
                AVG(CASE WHEN outcome_status='passed' THEN 1.0 WHEN outcome_status='failed' THEN 0.0 ELSE NULL END) pass_rate
                FROM tasks2 WHERE tenant_id=? AND created_at>=? AND status='succeeded' GROUP BY agent_id,tier""",
                (tenant_id, since),
            ).fetchall()
        recs = []
        for r in rows:
            n, pass_rate = int(r["n"]), r["pass_rate"]
            if n < 3 or pass_rate is None:
                continue
            if r["tier"] == "sol" and float(pass_rate) >= .95 and float(r["avg_iterations"] or 0) <= 2.5:
                recs.append({"agent_id": r["agent_id"], "action": "try_lower_tier", "from": "sol", "to": "terra", "confidence": "medium",
                             "evidence": {"tasks": n, "pass_rate": round(float(pass_rate), 3), "avg_iterations": round(float(r["avg_iterations"] or 0), 2), "avg_cost": round(float(r["avg_cost"] or 0), 6)}})
            if r["tier"] == "terra" and float(pass_rate) >= .98 and float(r["avg_iterations"] or 0) <= 1.5:
                recs.append({"agent_id": r["agent_id"], "action": "try_lower_tier", "from": "terra", "to": "luna", "confidence": "medium",
                             "evidence": {"tasks": n, "pass_rate": round(float(pass_rate), 3), "avg_iterations": round(float(r["avg_iterations"] or 0), 2), "avg_cost": round(float(r["avg_cost"] or 0), 6)}})
            if r["tier"] == "luna" and float(pass_rate) < .75:
                recs.append({"agent_id": r["agent_id"], "action": "raise_default_tier", "from": "luna", "to": "terra", "confidence": "medium",
                             "evidence": {"tasks": n, "pass_rate": round(float(pass_rate), 3)}})
        return recs


def _seconds(start: str, end: str) -> float:
    try:
        return max(0.0, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())
    except (TypeError, ValueError):
        return 0.0


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * p))))
    return ordered[idx]
