import os
import sqlite3
from pathlib import Path
import unittest
from unittest.mock import patch

from common import stack
from zworkforce.config import Settings
from zworkforce.db import Database, SCHEMA_VERSION
from zworkforce.outbox import OutboxDispatcher
from zworkforce.scheduler import Scheduler
from zworkforce.workflow import WorkflowOrchestrator


class ProductionFixesTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.settings, self.db, self.provider, self.engine, self.auth = stack()

    def tearDown(self):
        self.engine.shutdown()
        self.temp.cleanup()

    def test_memory_id_cannot_overwrite_another_tenant(self):
        self.db.ensure_tenant("acme")
        memory = self.db.put_memory("default", None, "Default", "default secret", [], "alice", "shared")

        with self.assertRaises(ValueError):
            self.db.put_memory("acme", None, "Acme", "acme secret", [], "bob", "shared")

        self.assertEqual(self.db.get_memory("default", memory["id"])["content"], "default secret")
        self.assertIsNone(self.db.get_memory("acme", "shared"))

    def test_memory_id_is_validated_before_persisting(self):
        memory_id = "m" * 129
        with self.assertRaisesRegex(ValueError, "memory_id is too long"):
            self.db.put_memory("default", None, "Too long", "content", [], "alice", memory_id)
        self.assertIsNone(self.db.get_memory("default", memory_id))

    def test_workflow_id_is_validated_before_persisting(self):
        workflow_id = "w" * 129
        with self.assertRaisesRegex(ValueError, "workflow_id is too long"):
            self.db.upsert_workflow(
                "default",
                {"id": workflow_id, "name": "Too long", "definition": {"steps": []}},
                "alice",
            )
        self.assertIsNone(self.db.get_workflow("default", workflow_id))

    def test_workflow_occurrence_key_returns_existing_run(self):
        workflow = WorkflowOrchestrator(self.db, self.engine)
        workflow.upsert("default", {
            "id": "scheduled",
            "definition": {"steps": [{"id": "a", "agent_id": "researcher", "prompt": "run"}]},
        }, "test")

        first = workflow.start("default", "scheduled", {}, "scheduler", idempotency_key="schedule:scheduled:occurrence-1")
        second = workflow.start("default", "scheduled", {}, "scheduler", idempotency_key="schedule:scheduled:occurrence-1")

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.db.list_workflow_runs("default")), 1)

    def test_workflow_idempotency_key_rejects_a_different_request(self):
        workflow = WorkflowOrchestrator(self.db, self.engine)
        workflow.upsert("default", {
            "id": "scheduled",
            "definition": {"steps": [{"id": "a", "agent_id": "researcher", "prompt": "run"}]},
        }, "test")

        workflow.start("default", "scheduled", {"occurrence": 1}, "scheduler", idempotency_key="same-key")
        with self.assertRaisesRegex(ValueError, "different workflow request"):
            workflow.start("default", "scheduled", {"occurrence": 2}, "scheduler", idempotency_key="same-key")

    def test_scheduler_dispatch_passes_workflow_occurrence_key(self):
        workflow = WorkflowOrchestrator(self.db, self.engine)
        workflow.upsert("default", {
            "id": "scheduled",
            "definition": {"steps": [{"id": "a", "agent_id": "researcher", "prompt": "run"}]},
        }, "test")
        scheduler = Scheduler(self.db, self.engine)

        scheduler._dispatch("default", "workflow", "scheduled", {}, "scheduler", "event:event-1:rule-1")
        scheduler._dispatch("default", "workflow", "scheduled", {}, "scheduler", "event:event-1:rule-1")

        self.assertEqual(len(self.db.list_workflow_runs("default")), 1)

    def test_outbox_claim_is_exclusive_and_reclaimable(self):
        item_id = self.db.enqueue_outbox("default", "topic", "http://localhost/hook", {"ok": True})

        first = self.db.claim_outbox("outbox-a", 30)
        self.assertEqual([item_id], [item["id"] for item in first])
        self.assertEqual([], self.db.claim_outbox("outbox-b", 30))

        with self.db.connection() as connection:
            connection.execute("UPDATE outbox3 SET claim_expires_at=? WHERE id=?", ("2000-01-01T00:00:00+00:00", item_id))

        reclaimed = self.db.claim_outbox("outbox-b", 30)
        self.assertEqual([item_id], [item["id"] for item in reclaimed])
        self.assertEqual("outbox-b", reclaimed[0]["claim_owner"])

    def test_production_rejects_mock_provider(self):
        environment = {
            "ZWORKFORCE_ENV": "production",
            "ZWORKFORCE_PROVIDER": "mock",
            "ZWORKFORCE_API_KEYS": "a-production-secret-that-is-long-enough:admin",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(ValueError, "mock providers are not allowed in production"):
                Settings.from_env()

    def test_outbox_dispatcher_uses_claimed_items(self):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, _limit):
                return b"ok"

        class ClaimOnlyDB:
            def __init__(self):
                self.finished = []

            def due_outbox(self, _limit):
                raise AssertionError("dispatcher must claim items")

            def claim_outbox(self, owner, lease_seconds, limit):
                self.claim = (owner, lease_seconds, limit)
                return [{
                    "id": "delivery-1", "topic": "topic", "tenant_id": "default",
                    "destination": "http://localhost/hook", "payload": {"ok": True},
                    "signature": "", "attempts": 0,
                }]

            def finish_outbox(self, item_id, success, error="", retry_seconds=60, owner=None):
                self.finished.append((item_id, success, owner))
                return True

        db = ClaimOnlyDB()
        dispatcher = OutboxDispatcher(db)
        with patch("urllib.request.urlopen", return_value=Response()):
            result = dispatcher.tick(owner_id="outbox-test")

        self.assertEqual(result["delivered"], 1)
        self.assertEqual(db.claim, ("outbox-test", dispatcher.claim_lease_seconds, dispatcher._claim_limit(100)))
        self.assertEqual(db.finished, [("delivery-1", True, "outbox-test")])

    def test_existing_v3_database_gets_v4_columns(self):
        path = Path(self.temp.name) / "legacy-v3.sqlite3"
        connection = sqlite3.connect(path)
        connection.executescript("""
            CREATE TABLE schema_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE workflow_runs3(
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, workflow_id TEXT NOT NULL,
                workflow_version INTEGER NOT NULL, status TEXT NOT NULL, actor TEXT NOT NULL,
                input_json TEXT NOT NULL DEFAULT '{}', context_json TEXT NOT NULL DEFAULT '{}',
                error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, started_at TEXT NULL,
                finished_at TEXT NULL
            );
            CREATE TABLE outbox3(
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, topic TEXT NOT NULL,
                destination TEXT NOT NULL, payload_json TEXT NOT NULL, signature TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at TEXT NOT NULL, last_error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL, delivered_at TEXT NULL
            );
        """)
        connection.close()

        database = Database(path)
        with database.connection() as connection:
            workflow_columns = {row[1] for row in connection.execute("PRAGMA table_info(workflow_runs3)").fetchall()}
            outbox_columns = {row[1] for row in connection.execute("PRAGMA table_info(outbox3)").fetchall()}
            schema_version = connection.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0]

        self.assertIn("idempotency_key", workflow_columns)
        self.assertIn("claim_owner", outbox_columns)
        self.assertIn("claim_expires_at", outbox_columns)
        self.assertEqual(schema_version, str(SCHEMA_VERSION))


if __name__ == "__main__":
    unittest.main()
