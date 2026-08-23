"""Polling worker for the local U.Perfect notification outbox."""

from __future__ import annotations

import os
import time
from collections.abc import Callable

from app.config import Settings
from app.database import Database
from app.repositories import Repository
from app.schemas import DeliverySummary
from app.services.line import LineNotificationSender
from app.services.notifications import NotificationSender, NotificationService


DEFAULT_INTERVAL_SECONDS = 15


def _interval_seconds() -> int:
    try:
        return max(1, int(os.getenv("UPERFECT_WORKER_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)))
    except ValueError:
        return DEFAULT_INTERVAL_SECONDS


class NotificationWorker:
    def __init__(
        self,
        *,
        settings: Settings,
        notifications: NotificationService,
        sender: NotificationSender | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.settings = settings
        self.notifications = notifications
        self.sender = sender or LineNotificationSender(settings.line_channel_access_token)
        self.worker_id = worker_id or f"uperfect-worker-{os.getpid()}"

    def run_once(self) -> DeliverySummary:
        if not self.settings.line_channel_access_token or not self.settings.line_admin_destination:
            return DeliverySummary(sent=0, failed=0, remaining=self.notifications.pending_count())
        return self.notifications.deliver_pending(self.sender, worker_id=self.worker_id)

    def run_forever(self, sleep: Callable[[float], None] = time.sleep) -> None:
        while True:
            self.run_once()
            sleep(_interval_seconds())


def build_worker() -> NotificationWorker:
    settings = Settings.from_environment()
    database = Database(settings.database_path)
    database.initialize()
    return NotificationWorker(
        settings=settings,
        notifications=NotificationService(Repository(database)),
    )


def main() -> None:
    build_worker().run_forever()


if __name__ == "__main__":
    main()
