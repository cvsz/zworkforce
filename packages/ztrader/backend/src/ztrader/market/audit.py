from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    message: str
    request_id: str
    actor: str = "system"
    metadata: dict[str, str | int | float | bool] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class InMemoryAuditLog:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> AuditEvent:
        self._events.append(event)
        return event

    def list_events(self, *, limit: int = 100) -> list[AuditEvent]:
        return self._events[-limit:]
