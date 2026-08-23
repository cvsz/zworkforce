from pathlib import Path

from app.database import Database


def schema_version(database: Database) -> int:
    with database.transaction() as connection:
        row = connection.execute("SELECT max(version) AS version FROM schema_migrations").fetchone()
        return int(row["version"])


def notification_columns(database: Database) -> set[str]:
    with database.transaction() as connection:
        rows = connection.execute("PRAGMA table_info(notification_outbox)").fetchall()
        return {row["name"] for row in rows}


def test_fresh_database_records_schema_version_and_outbox_retry_columns(tmp_path: Path):
    database = Database(str(tmp_path / "fresh.db"))

    database.initialize(seed=False)
    database.initialize(seed=False)

    assert schema_version(database) == 2
    assert {"locked_until", "locked_by", "next_attempt_at"} <= notification_columns(database)


def test_legacy_database_is_upgraded_without_replacing_existing_notification(tmp_path: Path):
    database = Database(str(tmp_path / "legacy.db"))
    with database.transaction() as connection:
        connection.execute(
            """
            CREATE TABLE notification_outbox (
              id TEXT PRIMARY KEY,
              event_type TEXT NOT NULL,
              destination TEXT NOT NULL,
              body TEXT NOT NULL,
              status TEXT NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0,
              last_error TEXT,
              created_at TEXT NOT NULL,
              sent_at TEXT
            )
            """
        )
        connection.execute(
            "INSERT INTO notification_outbox(id, event_type, destination, body, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("legacy-1", "order_confirmed", "admin-line", "body", "pending", "2026-08-10T00:00:00+00:00"),
        )

    database.initialize(seed=False)
    database.initialize(seed=False)

    with database.transaction() as connection:
        row = connection.execute("SELECT body FROM notification_outbox WHERE id = ?", ("legacy-1",)).fetchone()
    assert row["body"] == "body"
    assert schema_version(database) == 2
    assert {"locked_until", "locked_by", "next_attempt_at"} <= notification_columns(database)
