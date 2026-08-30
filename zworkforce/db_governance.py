from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import sqlite3
import uuid
from typing import Any

from .db_base import json_dumps, json_loads, utc_after, utcnow

class GovernanceMixin:
    def audit(self, tenant_id: str, actor: str, action: str, target_type: str, target_id: str, details: dict[str, Any] | None = None) -> str:
        now = utcnow()
        details_json = json_dumps(details or {})
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            prev = c.execute("SELECT event_hash FROM audit_events2 WHERE tenant_id=? ORDER BY id DESC LIMIT 1", (tenant_id,)).fetchone()
            prev_hash = prev[0] if prev else ""
            material = json_dumps({"tenant_id": tenant_id, "actor": actor, "action": action, "target_type": target_type, "target_id": target_id, "details": json_loads(details_json, {}), "prev_hash": prev_hash, "created_at": now})
            event_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
            c.execute("INSERT INTO audit_events2(tenant_id,actor,action,target_type,target_id,details_json,prev_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (tenant_id, actor, action, target_type, target_id, details_json, prev_hash, event_hash, now))
            self._append_dashboard_event_cursor(
                c,
                tenant_id,
                "audit.changed",
                target_type,
                target_id,
                {"summary": {"action": action}},
            )
            c.execute("COMMIT")
        return event_hash

    def list_audit(self, tenant_id: str, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM audit_events2 WHERE tenant_id=? ORDER BY id DESC LIMIT ? OFFSET ?", (tenant_id, max(1, min(limit, 500)), max(0, offset))).fetchall())

    def verify_audit_chain(self, tenant_id: str) -> dict[str, Any]:
        with self.connection() as c:
            rows = c.execute("SELECT * FROM audit_events2 WHERE tenant_id=? ORDER BY id ASC", (tenant_id,)).fetchall()
        prev_hash = ""
        for row in rows:
            r = dict(row)
            material = json_dumps({"tenant_id": r["tenant_id"], "actor": r["actor"], "action": r["action"], "target_type": r["target_type"], "target_id": r["target_id"], "details": json_loads(r["details_json"], {}), "prev_hash": prev_hash, "created_at": r["created_at"]})
            expected = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if r["prev_hash"] != prev_hash or r["event_hash"] != expected:
                return {"ok": False, "events": len(rows), "bad_event_id": r["id"]}
            prev_hash = r["event_hash"]
        return {"ok": True, "events": len(rows), "head": prev_hash}

    def upsert_api_key(self, key_id: str, tenant_id: str, name: str, key_hash: str, role: str, scopes: list[str]) -> None:
        self.ensure_tenant(tenant_id)
        now = utcnow()
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                if key_id.startswith("bootstrap-"):
                    c.execute(
                        "UPDATE api_keys2 SET disabled=1,revoked_at=? WHERE tenant_id=? AND name=? AND id LIKE ? AND id<>?",
                        (now, tenant_id, name, "bootstrap-%", key_id),
                    )
                conflict_target = "id" if key_id.startswith("bootstrap-") else "key_hash"
                c.execute(
                    f"""INSERT INTO api_keys2(id,tenant_id,name,key_hash,role,scopes_json,disabled,created_at) VALUES(?,?,?,?,?,?,0,?)
                    ON CONFLICT({conflict_target}) DO UPDATE SET tenant_id=excluded.tenant_id,name=excluded.name,
                    key_hash=excluded.key_hash,role=excluded.role,scopes_json=excluded.scopes_json,disabled=0,revoked_at=NULL""",
                    (key_id, tenant_id, name, key_hash, role, json_dumps(scopes or ["*"]), now),
                )
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise

    def create_api_key_record(self, tenant_id: str, name: str, key_hash: str, role: str, scopes: list[str]) -> str:
        key_id = str(uuid.uuid4())
        self.upsert_api_key(key_id, tenant_id, name, key_hash, role, scopes)
        return key_id

    def find_api_key(self, key_hash: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM api_keys2 WHERE key_hash=? AND disabled=0", (key_hash,)).fetchone()
            return self._decode(dict(row)) if row else None

    def list_active_api_keys(self, limit: int = 10_000) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(int(limit), 10_000))
        with self.connection() as c:
            rows = c.execute(
                "SELECT * FROM api_keys2 WHERE disabled=0 ORDER BY created_at LIMIT ?",
                (bounded_limit,),
            ).fetchall()
            return self._rows(rows)

    def touch_api_key(self, key_id: str) -> None:
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(minutes=1)).isoformat(timespec="seconds")
        with self.connection() as c:
            c.execute("UPDATE api_keys2 SET last_used_at=? WHERE id=? AND (last_used_at IS NULL OR last_used_at<?)", (now.isoformat(timespec="seconds"), key_id, cutoff))

    def list_api_keys(self, tenant_id: str) -> list[dict[str, Any]]:
        with self.connection() as c:
            rows = self._rows(c.execute("SELECT id,tenant_id,name,role,scopes_json,disabled,created_at,last_used_at,revoked_at FROM api_keys2 WHERE tenant_id=? ORDER BY created_at DESC", (tenant_id,)).fetchall())
            return rows

    def revoke_api_key(self, tenant_id: str, key_id: str) -> bool:
        with self.connection() as c:
            return bool(c.execute("UPDATE api_keys2 SET disabled=1,revoked_at=? WHERE tenant_id=? AND id=?", (utcnow(), tenant_id, key_id)).rowcount)

    def put_memory(self, tenant_id: str, agent_id: str | None, title: str, content: str, tags: list[str], actor: str, memory_id: str | None = None) -> dict[str, Any]:
        memory_id = str(memory_id).strip() if memory_id is not None else str(uuid.uuid4())
        if not memory_id:
            raise ValueError("memory id must not be empty")
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO memories2(id,tenant_id,agent_id,title,content,tags_json,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title,content=excluded.content,tags_json=excluded.tags_json,updated_at=excluded.updated_at
                WHERE memories2.tenant_id=excluded.tenant_id""",
                (memory_id, tenant_id, agent_id, title[:300], content, json_dumps(tags[:50]), actor, now, now),
            )
        memory = self.get_memory(tenant_id, memory_id)
        if memory:
            self.append_dashboard_event(
                tenant_id,
                "memory.changed",
                "memory",
                memory_id,
                {"summary": {"operation": "upsert"}},
            )
            return memory
        with self.connection() as c:
            owner = c.execute("SELECT tenant_id FROM memories2 WHERE id=?", (memory_id,)).fetchone()
        if owner and owner[0] != tenant_id:
            raise ValueError("memory id belongs to another tenant")
        raise RuntimeError("memory could not be stored")

    def get_memory(self, tenant_id: str, memory_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM memories2 WHERE tenant_id=? AND id=?", (tenant_id, memory_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def search_memories(self, tenant_id: str, query: str, agent_id: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        q = f"%{query.strip().lower()}%"
        clauses = ["tenant_id=?", "(lower(title) LIKE ? OR lower(content) LIKE ? OR lower(tags_json) LIKE ?)"]
        args: list[Any] = [tenant_id, q, q, q]
        if agent_id:
            clauses.append("(agent_id IS NULL OR agent_id=?)")
            args.append(agent_id)
        sql = "SELECT id,tenant_id,agent_id,title,content,tags_json,created_by,created_at,updated_at FROM memories2 WHERE " + " AND ".join(clauses) + " ORDER BY updated_at DESC LIMIT ?"
        args.append(max(1, min(limit, 50)))
        with self.connection() as c:
            rows = self._rows(c.execute(sql, tuple(args)).fetchall())
        for row in rows:
            if len(row["content"]) > 2000:
                row["content"] = row["content"][:2000] + "…"
        return rows

    def list_memories(self, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM memories2 WHERE tenant_id=? ORDER BY updated_at DESC LIMIT ?", (tenant_id, max(1, min(limit, 500)))).fetchall())

    def upsert_skill(self, tenant_id: str, manifest: dict[str, Any], signature: str, actor: str, enabled: bool = True) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO skills2(tenant_id,id,version,manifest_json,signature,enabled,created_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id,id) DO UPDATE SET version=excluded.version,manifest_json=excluded.manifest_json,
                signature=excluded.signature,enabled=excluded.enabled,updated_at=excluded.updated_at""",
                (tenant_id, manifest["id"], manifest["version"], json_dumps(manifest), signature, int(enabled), actor, now, now),
            )
        self.append_dashboard_event(
            tenant_id,
            "skill.changed",
            "skill",
            manifest["id"],
            {"summary": {"enabled": bool(enabled)}},
        )
        return self.get_skill(tenant_id, manifest["id"]) or {}

    def get_skill(self, tenant_id: str, skill_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM skills2 WHERE tenant_id=? AND id=?", (tenant_id, skill_id)).fetchone()
            if not row:
                return None
            result = dict(row)
            result["manifest"] = json_loads(result.pop("manifest_json"), {})
            return result

    def list_skills(self, tenant_id: str) -> list[dict[str, Any]]:
        with self.connection() as c:
            rows = c.execute("SELECT * FROM skills2 WHERE tenant_id=? ORDER BY id", (tenant_id,)).fetchall()
        out = []
        for row in rows:
            r = dict(row)
            r["manifest"] = json_loads(r.pop("manifest_json"), {})
            out.append(r)
        return out

    def record_tool_event(self, tenant_id: str, task_id: str, agent_id: str, tool_name: str, mutating: bool, success: bool, duration_ms: float, args: dict[str, Any], error: str = "") -> None:
        with self.connection() as c:
            c.execute(
                "INSERT INTO tool_events2(tenant_id,task_id,agent_id,tool_name,mutating,success,duration_ms,args_json,error,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (tenant_id, task_id, agent_id, tool_name, int(mutating), int(success), float(duration_ms), json_dumps(args), error[:1000], utcnow()),
            )
        self.append_dashboard_event(
            tenant_id,
            "task.changed",
            "task",
            task_id,
            {"summary": {"success": bool(success)}},
        )

    def list_tool_events(self, tenant_id: str, task_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as c:
            if task_id:
                rows = c.execute("SELECT * FROM tool_events2 WHERE tenant_id=? AND task_id=? ORDER BY id DESC LIMIT ?", (tenant_id, task_id, max(1, min(limit, 500)))).fetchall()
            else:
                rows = c.execute("SELECT * FROM tool_events2 WHERE tenant_id=? ORDER BY id DESC LIMIT ?", (tenant_id, max(1, min(limit, 500)))).fetchall()
            return self._rows(rows)

    def provider_available(self, name: str) -> bool:
        with self.connection() as c:
            row = c.execute("SELECT open_until FROM provider_health2 WHERE name=?", (name,)).fetchone()
        return not row or not row[0] or row[0] <= utcnow()

    def record_provider_success(self, name: str, latency_ms: float, tenant_id: str | None = None) -> None:
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO provider_health2(name,consecutive_failures,successes,failures,last_latency_ms,last_error,last_success_at,open_until,updated_at)
                VALUES(?,0,1,0,?,'',?,NULL,?) ON CONFLICT(name) DO UPDATE SET consecutive_failures=0,successes=successes+1,
                last_latency_ms=excluded.last_latency_ms,last_error='',last_success_at=excluded.last_success_at,open_until=NULL,updated_at=excluded.updated_at""",
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
        now = utcnow()
        with self.connection() as c:
            row = c.execute("SELECT consecutive_failures FROM provider_health2 WHERE name=?", (name,)).fetchone()
            failures = (int(row[0]) if row else 0) + 1
            open_until = utc_after(circuit_seconds) if failures >= threshold else None
            c.execute(
                """INSERT INTO provider_health2(name,consecutive_failures,successes,failures,last_latency_ms,last_error,last_failure_at,open_until,updated_at)
                VALUES(?,?,0,1,?,?,?, ?,?) ON CONFLICT(name) DO UPDATE SET consecutive_failures=?,failures=failures+1,
                last_latency_ms=?,last_error=?,last_failure_at=?,open_until=?,updated_at=?""",
                (name, failures, latency_ms, error[:1000], now, open_until, now, failures, latency_ms, error[:1000], now, open_until, now),
            )
        if tenant_id:
            self.append_dashboard_event(
                tenant_id,
                "provider.changed",
                "provider",
                name,
                {"summary": {"provider": name, "available": not bool(open_until), "latency_ms": latency_ms}},
            )

    def list_provider_health(self) -> list[dict[str, Any]]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM provider_health2 ORDER BY name").fetchall())

    def ready(self) -> bool:
        try:
            with self.connection() as c:
                return c.execute("SELECT 1").fetchone()[0] == 1
        except sqlite3.Error:
            return False
