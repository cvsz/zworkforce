"""SQLite reference adapter for atomic, replay-safe computer-use approval claims.

Experimental local backend only. Production must bind to the canonical
zWorkforce approval repository and PostgreSQL lease/fencing mechanisms.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from zworkforce.sagi_computer_use import ComputerUseIntent, ComputerAction


class AtomicApprovalStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS sagi_action_claims (
                request_digest TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                plan_digest TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('approved','claimed','completed','failed')),
                result_digest TEXT
            )""")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.execute("PRAGMA busy_timeout=5000")
        return db

    @staticmethod
    def _timestamp(value: datetime) -> int:
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ValueError("timezone-aware datetime required")
        return int(value.astimezone(timezone.utc).timestamp())

    def register_approved(self, intent: ComputerUseIntent, *, expires_at: datetime) -> None:
        """Record *externally approved* request metadata; this does not approve anything.

        Call exclusively from the canonical approval authority adapter after
        identity/four-eyes/policy checks; this prototype does not validate those.
        """
        if not isinstance(intent, ComputerUseIntent) or intent.action is ComputerAction.OBSERVE:
            raise ValueError("mutation intent required")
        expiry = self._timestamp(expires_at)
        with self._connect() as db:
            db.execute("""INSERT INTO sagi_action_claims
                (request_digest,tenant_id,actor_id,session_id,plan_digest,action,target,expires_at,state)
                VALUES (?,?,?,?,?,?,?,?, 'approved')""", (
                intent.request_digest, intent.tenant_id, intent.actor_id,
                intent.session_id, intent.plan_digest, intent.action.value,
                intent.target, expiry,
            ))

    def claim_once(self, intent: ComputerUseIntent, *, now: datetime) -> bool:
        """Single atomic conditional update; at most one caller obtains the claim."""
        if not isinstance(intent, ComputerUseIntent) or intent.action is ComputerAction.OBSERVE:
            return False
        timestamp = self._timestamp(now)
        with self._connect() as db:
            cursor = db.execute("""UPDATE sagi_action_claims SET state='claimed'
                WHERE request_digest=? AND tenant_id=? AND actor_id=?
                  AND session_id=? AND plan_digest=? AND action=? AND target=?
                  AND expires_at>? AND state='approved'""", (
                intent.request_digest, intent.tenant_id, intent.actor_id,
                intent.session_id, intent.plan_digest, intent.action.value,
                intent.target, timestamp,
            ))
            return cursor.rowcount == 1

    def finish(self, intent: ComputerUseIntent, *, result_digest: str, success: bool) -> bool:
        """Final state; failed/uncertain actions are never automatically retried."""
        if not isinstance(result_digest, str) or len(result_digest) != 64 or any(
            ch not in "0123456789abcdef" for ch in result_digest
        ):
            raise ValueError("result digest must be lowercase sha256")
        with self._connect() as db:
            cursor = db.execute("""UPDATE sagi_action_claims
                SET state=?, result_digest=? WHERE request_digest=?
                AND tenant_id=? AND actor_id=? AND state='claimed'""", (
                "completed" if success else "failed", result_digest,
                intent.request_digest, intent.tenant_id, intent.actor_id,
            ))
            return cursor.rowcount == 1

    def get_state(self, digest: str) -> str | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT state FROM sagi_action_claims WHERE request_digest=?", (digest,)
            ).fetchone()
            return row[0] if row else None
