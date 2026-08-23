"""Small, additive SQLite schema migration runner."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Callable


CURRENT_SCHEMA_VERSION = 2
Migration = Callable[[sqlite3.Connection], None]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _add_notification_retry_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(notification_outbox)").fetchall()
    }
    for name, definition in (
        ("locked_until", "TEXT"),
        ("locked_by", "TEXT"),
        ("next_attempt_at", "TEXT"),
    ):
        if name not in columns:
            connection.execute(f"ALTER TABLE notification_outbox ADD COLUMN {name} {definition}")


MIGRATIONS: tuple[tuple[int, Migration], ...] = (
    (2, _add_notification_retry_columns),
)


def apply_migrations(connection: sqlite3.Connection) -> int:
    """Record the existing schema as v1, then apply each missing migration."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY,
          applied_at TEXT NOT NULL
        )
        """
    )
    current = connection.execute("SELECT max(version) AS version FROM schema_migrations").fetchone()["version"]
    if current is None:
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (1, ?)",
            (_now(),),
        )
        current = 1

    for version, migration in MIGRATIONS:
        if current >= version:
            continue
        migration(connection)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, _now()),
        )
        current = version
    return int(current)
