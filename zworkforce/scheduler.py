from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
import re
import socket
import time
from typing import Any
from zoneinfo import ZoneInfo

from .db import utcnow
from .config import DASHBOARD_EVENT_DEFAULT_RETENTION_SECONDS, DASHBOARD_EVENT_MAX_RETENTION_SECONDS
from .workflow import WorkflowOrchestrator


class ScheduleError(ValueError):
    pass


def _field(spec: str, minimum: int, maximum: int) -> set[int]:
    values: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            raise ScheduleError("empty cron field")
        base, slash, step_raw = part.partition("/")
        try:
            step = int(step_raw) if slash else 1
        except ValueError as exc:
            raise ScheduleError("invalid cron step") from exc
        if step <= 0:
            raise ScheduleError("cron step must be positive")
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            a, b = base.split("-", 1)
            start, end = int(a), int(b)
        else:
            start = end = int(base)
        if start < minimum or end > maximum or start > end:
            raise ScheduleError(f"cron value outside {minimum}..{maximum}")
        values.update(range(start, end + 1, step))
    return values


def parse_cron(expr: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    parts = expr.split()
    if len(parts) != 5:
        raise ScheduleError("cron expression must have 5 fields: minute hour day month weekday")
    return (_field(parts[0], 0, 59), _field(parts[1], 0, 23), _field(parts[2], 1, 31),
            _field(parts[3], 1, 12), _field(parts[4], 0, 6))


def next_cron_at(expr: str, after: datetime, timezone_name: str = "UTC") -> str:
    minute, hour, day, month, weekday = parse_cron(expr)
    parts = expr.split()
    dom_wildcard, dow_wildcard = parts[2] == "*", parts[4] == "*"
    try:
        tz = ZoneInfo(timezone_name)
    except Exception as exc:
        raise ScheduleError(f"invalid timezone: {timezone_name}") from exc
    local = after.astimezone(tz).replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(366 * 24 * 60 * 2):
        cron_weekday = (local.weekday() + 1) % 7
        dom_match, dow_match = local.day in day, cron_weekday in weekday
        calendar_match = True if dom_wildcard and dow_wildcard else dow_match if dom_wildcard else dom_match if dow_wildcard else dom_match or dow_match
        if local.minute in minute and local.hour in hour and local.month in month and calendar_match:
            return local.astimezone(timezone.utc).isoformat(timespec="seconds")
        local += timedelta(minutes=1)
    raise ScheduleError("cron expression has no matching time within search horizon")


def schedule_next(item: dict[str, Any], after: datetime | None = None) -> str:
    after = after or datetime.now(timezone.utc)
    if item["schedule_type"] == "interval":
        seconds = int(item.get("interval_seconds") or 0)
        if seconds < 1:
            raise ScheduleError("interval_seconds must be >= 1")
        return (after + timedelta(seconds=seconds)).isoformat(timespec="seconds")
    if item["schedule_type"] == "cron":
        return next_cron_at(str(item.get("cron_expr") or ""), after, str(item.get("timezone") or "UTC"))
    raise ScheduleError("schedule_type must be cron or interval")


def _subset(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and _subset(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and all(any(_subset(x, y) for y in actual) for x in expected)
    return actual == expected


_TOKEN = re.compile(r"\{\{\s*event\.([A-Za-z0-9_.-]+)\s*\}\}")


def _render(value: Any, event: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {k: _render(v, event) for k, v in value.items()}
    if isinstance(value, list):
        return [_render(v, event) for v in value]
    if not isinstance(value, str):
        return value
    def repl(match: re.Match[str]) -> str:
        current: Any = event
        for part in match.group(1).split("."):
            if not isinstance(current, dict) or part not in current:
                return ""
            current = current[part]
        return str(current)
    return _TOKEN.sub(repl, value)


class Scheduler:
    def __init__(
        self,
        db,
        engine,
        *,
        owner: str | None = None,
        lease_seconds: int = 30,
        dashboard_event_retention_seconds: int = DASHBOARD_EVENT_DEFAULT_RETENTION_SECONDS,
    ):
        self.db = db
        self.engine = engine
        self.workflows = WorkflowOrchestrator(db, engine)
        self.owner = owner or f"scheduler-{socket.gethostname()}"
        self.lease_seconds = max(5, int(lease_seconds))
        self.dashboard_event_retention_seconds = min(
            max(60, int(dashboard_event_retention_seconds)),
            DASHBOARD_EVENT_MAX_RETENTION_SECONDS,
        )
        self._dashboard_event_prune_interval_seconds = min(300, self.dashboard_event_retention_seconds)
        self._last_dashboard_event_prune = 0.0

    def _prune_dashboard_events(self) -> int:
        now = time.monotonic()
        if now - self._last_dashboard_event_prune < self._dashboard_event_prune_interval_seconds:
            return 0
        self._last_dashboard_event_prune = now
        cutoff = (
            datetime.now(timezone.utc) - timedelta(seconds=self.dashboard_event_retention_seconds)
        ).isoformat(timespec="seconds")
        return self.db.prune_dashboard_events(cutoff)

    def upsert_schedule(self, tenant_id: str, item: dict[str, Any], actor: str) -> dict[str, Any]:
        payload = dict(item)
        if not str(payload.get("id", "")).strip():
            raise ScheduleError("schedule id is required")
        if payload.get("target_type") not in {"agent", "workflow"}:
            raise ScheduleError("target_type must be agent or workflow")
        now = datetime.now(timezone.utc)
        payload["next_run_at"] = schedule_next(payload, now)
        return self.db.upsert_schedule(tenant_id, payload, actor)

    def _dispatch(self, tenant_id: str, target_type: str, target_id: str, payload: dict[str, Any], actor: str, key: str):
        if target_type == "workflow":
            return self.workflows.start(tenant_id, target_id, payload if isinstance(payload, dict) else {}, actor, idempotency_key=key)
        prompt = str(payload.get("prompt", "")) if isinstance(payload, dict) else str(payload)
        if not prompt.strip():
            raise ScheduleError("agent target requires payload.prompt")
        return self.engine.submit(tenant_id, target_id, prompt, actor=actor,
                                  mutating=bool(payload.get("mutating", False)),
                                  tier_override=payload.get("tier"),
                                  priority=int(payload.get("priority", 0)),
                                  idempotency_key=key)[0]

    def tick(self) -> dict[str, int]:
        stats = {"schedules": 0, "events": 0, "tasks_submitted": 0, "workflows": 0, "dashboard_events_pruned": 0}
        stats["dashboard_events_pruned"] = self._prune_dashboard_events()
        now = utcnow()
        for item in self.db.due_schedules(now):
            try:
                self._dispatch(item["tenant_id"], item["target_type"], item["target_id"], item.get("payload") or {},
                               "scheduler", f"schedule:{item['tenant_id']}:{item['id']}:{item['next_run_at']}")
                self.db.mark_schedule_run(item["tenant_id"], item["id"], schedule_next(item))
                stats["schedules"] += 1
            except Exception as exc:
                try:
                    self.db.mark_schedule_run(item["tenant_id"], item["id"], schedule_next(item), str(exc))
                except Exception:
                    pass

        for event in self.db.pending_events():
            try:
                matched = 0
                for rule in self.db.list_event_rules(event["tenant_id"], event["event_type"]):
                    if not _subset(rule.get("filter") or {}, event.get("payload") or {}):
                        continue
                    payload = _render(rule.get("payload_template") or {}, event.get("payload") or {})
                    self._dispatch(event["tenant_id"], rule["target_type"], rule["target_id"], payload,
                                   "event:" + event.get("source", "system"), f"event:{event['id']}:{rule['id']}")
                    matched += 1
                self.db.finish_event(event["id"], "processed")
                stats["events"] += 1
                stats["tasks_submitted"] += matched
            except Exception as exc:
                self.db.finish_event(event["id"], "failed", str(exc))

        wf_stats = self.workflows.tick()
        stats["workflows"] = wf_stats.get("completed", 0)
        stats["tasks_submitted"] += wf_stats.get("tasks_submitted", 0)
        return stats

    def loop(self, poll: float = 1.0, once: bool = False, owner_id: str | None = None):
        owner = owner_id or self.owner
        aggregate = {"ticks": 0, "schedules": 0, "events": 0, "tasks_submitted": 0, "workflows": 0, "dashboard_events_pruned": 0}
        try:
            while True:
                if self.db.acquire_service_lease("scheduler", owner, self.lease_seconds):
                    result = self.tick()
                    aggregate["ticks"] += 1
                    for key in ("schedules", "events", "tasks_submitted", "workflows", "dashboard_events_pruned"):
                        aggregate[key] += int(result.get(key, 0))
                if once:
                    return aggregate
                time.sleep(max(0.1, float(poll)))
        finally:
            try:
                self.db.release_service_lease("scheduler", owner)
            except Exception:
                pass
