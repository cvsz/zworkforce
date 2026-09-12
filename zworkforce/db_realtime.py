from __future__ import annotations

import math
from typing import Any

from .db_base import json_dumps, utcnow


MAX_DASHBOARD_CURSOR = (1 << 63) - 1
MAX_DASHBOARD_FIELD_LENGTH = 128
MAX_DASHBOARD_EVENTS = 100

_SUMMARY_STRING_FIELDS = frozenset({
    "action",
    "event_type",
    "operation",
    "outcome_status",
    "provider",
    "schedule_type",
    "status",
    "target_type",
})
_SUMMARY_INTEGER_FIELDS = frozenset({"attempt", "count"})
_SUMMARY_FLOAT_FIELDS = frozenset({"latency_ms", "outcome_score"})
_SUMMARY_BOOLEAN_FIELDS = frozenset({"available", "enabled", "success"})
_SUMMARY_KEYS = (
    _SUMMARY_STRING_FIELDS
    | _SUMMARY_INTEGER_FIELDS
    | _SUMMARY_FLOAT_FIELDS
    | _SUMMARY_BOOLEAN_FIELDS
)


def _bounded_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} must not be empty")
    if len(text) > MAX_DASHBOARD_FIELD_LENGTH:
        raise ValueError(f"{field} is too long")
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise ValueError(f"{field} contains control characters")
    return text


def _safe_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("dashboard event payload must be an object")
    raw_summary = payload.get("summary", {})
    if raw_summary is None:
        return {}
    if not isinstance(raw_summary, dict):
        raise ValueError("dashboard event summary must be an object")

    summary: dict[str, Any] = {}
    for key in _SUMMARY_KEYS:
        if key not in raw_summary:
            continue
        value = raw_summary[key]
        if key in _SUMMARY_STRING_FIELDS:
            if not isinstance(value, str):
                continue
            summary[key] = value[:MAX_DASHBOARD_FIELD_LENGTH]
        elif key in _SUMMARY_INTEGER_FIELDS:
            if isinstance(value, bool):
                continue
            try:
                integer = int(value)
            except (TypeError, ValueError, OverflowError):
                continue
            if 0 <= integer <= MAX_DASHBOARD_CURSOR:
                summary[key] = integer
        elif key in _SUMMARY_FLOAT_FIELDS:
            if isinstance(value, bool):
                continue
            try:
                number = float(value)
            except (TypeError, ValueError, OverflowError):
                continue
            if math.isfinite(number) and abs(number) <= float(MAX_DASHBOARD_CURSOR):
                summary[key] = number
        elif key in _SUMMARY_BOOLEAN_FIELDS and isinstance(value, bool):
            summary[key] = value
    return {"summary": summary} if summary else {}


def _dashboard_cursor(value: Any, field: str = "cursor") -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    try:
        cursor = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if cursor < 0 or cursor > MAX_DASHBOARD_CURSOR:
        raise ValueError(f"{field} is outside the supported range")
    return cursor


class DashboardEventMixin:
    def _append_dashboard_event_cursor(
        self,
        connection: Any,
        tenant_id: str,
        event_type: str,
        resource_type: str,
        resource_id: str,
        payload: dict[str, Any] | None = None,
    ) -> int:
        tenant = _bounded_text(tenant_id, "tenant_id")
        event = _bounded_text(event_type, "event_type")
        resource = _bounded_text(resource_type, "resource_type")
        identifier = _bounded_text(resource_id, "resource_id")
        safe_payload = _safe_summary(payload)
        row = connection.execute(
            """INSERT INTO dashboard_events2(
                tenant_id,event_type,resource_type,resource_id,payload_json,created_at
            ) VALUES(?,?,?,?,?,?) RETURNING id""",
            (tenant, event, resource, identifier, json_dumps(safe_payload), utcnow()),
        ).fetchone()
        if not row:
            raise RuntimeError("dashboard event insert did not return an id")
        return int(row[0])

    def append_dashboard_event(
        self,
        tenant_id: str,
        event_type: str,
        resource_type: str,
        resource_id: str,
        payload: dict[str, Any] | None = None,
    ) -> int:
        with self.connection() as connection:
            return self._append_dashboard_event_cursor(
                connection, tenant_id, event_type, resource_type, resource_id, payload
            )

    def list_dashboard_events(
        self,
        tenant_id: str,
        after_id: int = 0,
        limit: int = MAX_DASHBOARD_EVENTS,
    ) -> list[dict[str, Any]]:
        tenant = _bounded_text(tenant_id, "tenant_id")
        cursor = _dashboard_cursor(after_id, "after_id")
        if isinstance(limit, bool):
            raise ValueError("limit must be an integer")
        try:
            bounded_limit = int(limit)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("limit must be an integer") from exc
        if bounded_limit < 1:
            raise ValueError("limit must be at least 1")
        bounded_limit = min(bounded_limit, MAX_DASHBOARD_EVENTS)
        with self.connection() as connection:
            return self._rows(
                connection.execute(
                    """SELECT id,tenant_id,event_type,resource_type,resource_id,payload_json,created_at
                    FROM dashboard_events2 WHERE tenant_id=? AND id>? ORDER BY id ASC LIMIT ?""",
                    (tenant, cursor, bounded_limit),
                ).fetchall()
            )

    def dashboard_event_bounds(self, tenant_id: str) -> dict[str, int | None]:
        tenant = _bounded_text(tenant_id, "tenant_id")
        with self.connection() as connection:
            row = connection.execute(
                "SELECT MIN(id) oldest,MAX(id) latest FROM dashboard_events2 WHERE tenant_id=?",
                (tenant,),
            ).fetchone()
        return {
            "oldest": int(row[0]) if row and row[0] is not None else None,
            "latest": int(row[1]) if row and row[1] is not None else None,
        }

    def dashboard_event_cursor(self, tenant_id: str) -> int:
        latest = self.dashboard_event_bounds(tenant_id)["latest"]
        return int(latest or 0)

    def prune_dashboard_events(self, older_than: str, tenant_id: str | None = None) -> int:
        cutoff = _bounded_text(older_than, "older_than")
        args: tuple[Any, ...]
        if tenant_id is None:
            query = "DELETE FROM dashboard_events2 WHERE created_at<?"
            args = (cutoff,)
        else:
            tenant = _bounded_text(tenant_id, "tenant_id")
            query = "DELETE FROM dashboard_events2 WHERE created_at<? AND tenant_id=?"
            args = (cutoff, tenant)
        with self.connection() as connection:
            return int(connection.execute(query, args).rowcount)


__all__ = [
    "DashboardEventMixin",
    "MAX_DASHBOARD_CURSOR",
    "MAX_DASHBOARD_EVENTS",
]
