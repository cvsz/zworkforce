from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any


@dataclass
class BotRuntimeState:
    """Thread-safe readiness and liveness state for the Omega bot process."""

    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    db_ready: bool = False
    stream_ready: bool = False
    stopping: bool = False
    last_snapshot_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    last_error: str | None = None
    _lock: Lock = field(default_factory=Lock, repr=False)

    def mark_db_ready(self) -> None:
        with self._lock:
            self.db_ready = True

    def mark_stream_ready(self) -> None:
        with self._lock:
            self.stream_ready = True

    def mark_stopping(self) -> None:
        with self._lock:
            self.stopping = True

    def mark_snapshot(self) -> None:
        with self._lock:
            self.last_snapshot_at = datetime.now(timezone.utc)
            self.stream_ready = True

    def mark_heartbeat(self) -> None:
        with self._lock:
            self.last_heartbeat_at = datetime.now(timezone.utc)

    def mark_error(self, error: BaseException | str) -> None:
        with self._lock:
            self.last_error = str(error)

    def as_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "started_at": self.started_at.isoformat(),
                "db_ready": self.db_ready,
                "stream_ready": self.stream_ready,
                "stopping": self.stopping,
                "last_snapshot_at": (
                    self.last_snapshot_at.isoformat() if self.last_snapshot_at else None
                ),
                "last_heartbeat_at": (
                    self.last_heartbeat_at.isoformat()
                    if self.last_heartbeat_at
                    else None
                ),
                "last_error": self.last_error,
            }

    @property
    def live(self) -> bool:
        with self._lock:
            return not self.stopping

    @property
    def ready(self) -> bool:
        with self._lock:
            return self.db_ready and self.stream_ready and not self.stopping
