from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

from .db_base import utcnow
from .db_realtime import (
    MAX_DASHBOARD_CURSOR,
    MAX_DASHBOARD_EVENTS,
    _bounded_text,
    _dashboard_cursor,
    _safe_summary,
)


_CURSOR_RE = re.compile(r"^[0-9]+$")


def parse_event_cursor(value: str | None) -> int:
    if value is None:
        return 0
    if not isinstance(value, str):
        raise ValueError("event cursor must be an integer")
    raw = value.strip()
    if not raw or not _CURSOR_RE.fullmatch(raw):
        raise ValueError("event cursor must be a non-negative integer")
    try:
        cursor = int(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("event cursor is outside the supported range") from exc
    if cursor > MAX_DASHBOARD_CURSOR:
        raise ValueError("event cursor is outside the supported range")
    return cursor


def _sse_data(event_type: str, event_id: int, data: dict[str, Any]) -> bytes:
    event = _bounded_text(event_type, "event_type")
    cursor = _dashboard_cursor(event_id, "event_id")
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
    if "\n" in encoded or "\r" in encoded:
        raise ValueError("SSE data must be a single line")
    return f"id: {cursor}\nevent: {event}\ndata: {encoded}\n\n".encode("utf-8")


def format_dashboard_event(event: dict[str, Any]) -> bytes:
    if not isinstance(event, dict):
        raise ValueError("dashboard event must be an object")
    event_id = _dashboard_cursor(event.get("id"), "event_id")
    event_type = _bounded_text(event.get("event_type"), "event_type")
    resource_type = _bounded_text(event.get("resource_type"), "resource_type")
    resource_id = _bounded_text(event.get("resource_id"), "resource_id")
    payload = _safe_summary(event.get("payload"))
    data = {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "summary": payload.get("summary", {}),
    }
    return _sse_data(event_type, event_id, data)


def format_dashboard_heartbeat(cursor: int, created_at: str) -> bytes:
    safe_cursor = _dashboard_cursor(cursor, "cursor")
    return _sse_data(
        "heartbeat",
        safe_cursor,
        {"cursor": safe_cursor, "server_time": _bounded_text(created_at, "server_time")},
    )


def _format_resync(cursor: int, oldest: int) -> bytes:
    return _sse_data(
        "resync.required",
        _dashboard_cursor(cursor, "cursor"),
        {"cursor": _dashboard_cursor(cursor, "cursor"), "oldest": _dashboard_cursor(oldest, "oldest")},
    )


def stream_dashboard_events(
    db,
    tenant_id: str,
    after_id: int,
    write: Callable[[bytes], None],
    is_closed: Callable[[], bool] | None = None,
    *,
    max_seconds: float = 20.0,
    poll_seconds: float = 0.5,
    heartbeat_seconds: float = 5.0,
) -> int:
    cursor = _dashboard_cursor(after_id, "after_id")
    duration = max(0.0, float(max_seconds))
    poll = max(0.05, float(poll_seconds))
    heartbeat_interval = max(0.1, float(heartbeat_seconds))
    started = time.monotonic()
    last_heartbeat = started - heartbeat_interval

    def closed() -> bool:
        return bool(is_closed and is_closed())

    while not closed():
        bounds = db.dashboard_event_bounds(tenant_id)
        oldest = bounds["oldest"]
        latest = int(bounds["latest"] or 0)
        # Cursor zero is the initial full-snapshot path. The durable event IDs
        # are global, so a tenant whose first retained event follows another
        # tenant's events would otherwise look stale even though no event for
        # this tenant was missed. The dashboard refreshes its authoritative
        # REST snapshot before opening this stream.
        if cursor > 0 and oldest is not None and cursor < int(oldest) - 1:
            write(_format_resync(latest, int(oldest)))
            return latest

        events = db.list_dashboard_events(tenant_id, after_id=cursor, limit=MAX_DASHBOARD_EVENTS)
        for event in events:
            if closed():
                return cursor
            write(format_dashboard_event(event))
            cursor = _dashboard_cursor(event["id"], "event_id")

        now = time.monotonic()
        if now - last_heartbeat >= heartbeat_interval:
            write(format_dashboard_heartbeat(cursor, utcnow()))
            last_heartbeat = now

        if duration <= 0 or now - started >= duration:
            return cursor
        remaining = duration - (now - started)
        time.sleep(min(poll, max(0.0, remaining)))

    return cursor


__all__ = [
    "format_dashboard_event",
    "format_dashboard_heartbeat",
    "parse_event_cursor",
    "stream_dashboard_events",
]
