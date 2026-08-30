import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest
import uuid
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from zworkforce.config import ProviderConfig, Settings
from zworkforce.db import Database, SCHEMA_VERSION, utcnow
from zworkforce.engine import Engine
from zworkforce.workflow import WorkflowOrchestrator
from zworkforce.providers import build_provider


@unittest.skipUnless(os.getenv("ZWORKFORCE_TEST_POSTGRES_URL"), "postgres integration URL not configured")
class PostgresIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.url=os.environ["ZWORKFORCE_TEST_POSTGRES_URL"]
        self.tenant_id=f"ci-{uuid.uuid4().hex}"
        self.db=Database(self.url,self.tenant_id)
        self.task_ids=[]
        self.settings=Settings(default_tenant=self.tenant_id,embedded_workers=0,providers=(
            ProviderConfig(name="mock",kind="mock",models={"luna":"mock-luna","terra":"mock-terra","sol":"mock-sol"}),))
        self.engine=Engine(self.settings,self.db,build_provider(self.settings,self.db))

    def test_fixture_uses_isolated_tenant(self):
        self.assertNotEqual(self.db.default_tenant, "ci")

    def test_dashboard_events_round_trip_and_tenant_isolation(self):
        other_tenant = f"other-{uuid.uuid4().hex}"
        self.db.ensure_tenant(other_tenant, "Other")
        event_id = self.db.append_dashboard_event(
            self.tenant_id,
            "task.changed",
            "task",
            "pg-task",
            {"summary": {"status": "running", "password": "drop"}},
        )
        self.assertGreater(event_id, 0)
        self.assertEqual(self.db.dashboard_event_cursor(self.tenant_id), event_id)
        self.assertEqual(self.db.list_dashboard_events(other_tenant), [])
        self.assertEqual(self.db.list_dashboard_events(self.tenant_id)[0]["payload"], {"summary": {"status": "running"}})

    def tearDown(self):
        self.engine.shutdown()
        for task_id in self.task_ids:
            self.db.update_task(task_id,status="canceled",cancel_requested=1,finished_at=utcnow(),lease_owner=None,lease_expires_at=None,heartbeat_at=None)

    def _submit(self,*args,**kwargs):
        task,created=self.engine.submit(*args,**kwargs)
        self.task_ids.append(task["id"])
        return task,created

    def test_queue_and_runtime(self):
        task,_=self._submit(self.tenant_id,"researcher","postgres integration task",actor=self.tenant_id)
        self.assertEqual(self.engine.worker_loop("pg-worker",once=True),1)
        self.assertEqual(self.db.get_task(self.tenant_id,task["id"])["status"],"succeeded")
        self.assertEqual(self.db.backend_kind,"postgres")

    def test_skip_locked_claims_a_different_task(self):
        first,_=self._submit(self.tenant_id,"researcher","first queued task",actor=self.tenant_id,idempotency_key="pg-first")
        second,_=self._submit(self.tenant_id,"researcher","second queued task",actor=self.tenant_id,idempotency_key="pg-second")
        with self.db.connection() as locker:
            locker.execute("BEGIN")
            locked=locker.execute("SELECT id FROM tasks2 WHERE id=? FOR UPDATE",(first["id"],)).fetchone()
            self.assertEqual(locked[0],first["id"])
            claimed=self.db.claim_next_task("skip-locked-worker",30)
            self.assertIsNotNone(claimed)
            self.assertEqual(claimed["id"],second["id"])
            locker.execute("ROLLBACK")

    def test_bootstrap_api_key_upsert_supports_postgres_literal_like_pattern(self):
        key_id = f"bootstrap-{uuid.uuid4().hex}"
        key_hash = f"test-hash-{uuid.uuid4().hex}"
        self.db.upsert_api_key(key_id, self.tenant_id, "bootstrap", key_hash, "superadmin", ["*"])
        stored = self.db.find_api_key(key_hash)
        self.assertIsNotNone(stored)
        self.assertEqual(stored["id"], key_id)

    def test_concurrent_initialization_serializes_postgres_schema_ddl(self):
        schema = f"ci_init_{uuid.uuid4().hex}"
        import psycopg

        def schema_target():
            parsed = urlsplit(self.url)
            query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "options"]
            query.append(("options", f"-csearch_path={schema}"))
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))

        with psycopg.connect(self.url, autocommit=True) as connection:
            connection.execute(f'CREATE SCHEMA "{schema}"')
        target = schema_target()
        failures = []
        start = Barrier(4)

        def initialize(index):
            start.wait(timeout=10)
            return Database(target, f"init-{index}-{uuid.uuid4().hex}")

        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [pool.submit(initialize, index) for index in range(4)]
                for future in futures:
                    try:
                        future.result()
                    except Exception as exc:
                        failures.append(exc)
            self.assertEqual(failures, [], [str(exc) for exc in failures])
            with psycopg.connect(self.url, autocommit=True) as connection:
                relations = connection.execute(
                    "SELECT to_regclass(%s), to_regclass(%s), to_regclass(%s), to_regclass(%s), to_regclass(%s), to_regclass(%s)",
                    (
                        f"{schema}.tenants",
                        f"{schema}.tasks2",
                        f"{schema}.event_rules3",
                        f"{schema}.workspace_conversations5",
                        f"{schema}.workspace_grants6",
                        f"{schema}.workspace_worktrees7",
                    ),
                ).fetchone()
                schema_version = connection.execute(
                    f'SELECT value FROM "{schema}".schema_meta WHERE key=%s',
                    ("schema_version",),
                ).fetchone()[0]
            self.assertEqual(
                relations,
                (
                    f"{schema}.tenants",
                    f"{schema}.tasks2",
                    f"{schema}.event_rules3",
                    f"{schema}.workspace_conversations5",
                    f"{schema}.workspace_grants6",
                    f"{schema}.workspace_worktrees7",
                ),
            )
            self.assertEqual(schema_version, str(SCHEMA_VERSION))
        finally:
            with psycopg.connect(self.url, autocommit=True) as connection:
                connection.execute(f'DROP SCHEMA "{schema}" CASCADE')

    def test_v4_workflow_occurrence_and_outbox_claims(self):
        workflows = WorkflowOrchestrator(self.db, self.engine)
        workflows.upsert(self.tenant_id, {
            "id": "scheduled",
            "definition": {"steps": [{"id": "a", "agent_id": "researcher", "prompt": "run"}]},
        }, self.tenant_id)
        first = workflows.start(self.tenant_id, "scheduled", {}, self.tenant_id, idempotency_key="schedule:pg:1")
        second = workflows.start(self.tenant_id, "scheduled", {}, self.tenant_id, idempotency_key="schedule:pg:1")
        self.assertEqual(first["id"], second["id"])

        item_id = self.db.enqueue_outbox(self.tenant_id, "topic", "http://localhost/hook", {"ok": True})
        claimed = self.db.claim_outbox("pg-outbox-a", 30)
        self.assertEqual([item_id], [item["id"] for item in claimed])
        self.assertEqual([], self.db.claim_outbox("pg-outbox-b", 30))

    def test_workspace_v5_round_trip_and_tenant_isolation(self):
        project = self.db.create_workspace_project(self.tenant_id, "Postgres workspace", self.tenant_id)
        conversation = self.db.create_workspace_conversation(
            self.tenant_id,
            self.tenant_id,
            project_id=project["id"],
            title="Postgres conversation",
        )
        first = self.db.append_workspace_message(
            self.tenant_id,
            conversation["id"],
            "user",
            self.tenant_id,
            content="first",
        )
        second = self.db.append_workspace_message(
            self.tenant_id,
            conversation["id"],
            "assistant",
            "agent",
            content="second",
        )
        self.assertEqual([first["ordinal"], second["ordinal"]], [1, 2])
        self.assertEqual(
            [item["content"] for item in self.db.list_workspace_messages(self.tenant_id, conversation["id"])],
            ["first", "second"],
        )

        other_tenant = f"other-{uuid.uuid4().hex}"
        self.db.ensure_tenant(other_tenant, "Other")
        self.assertIsNone(self.db.get_workspace_project(other_tenant, project["id"]))
        with self.assertRaisesRegex(ValueError, "project not found"):
            self.db.create_workspace_conversation(
                other_tenant,
                other_tenant,
                project_id=project["id"],
                title="cross tenant",
            )

    def test_workspace_grants_v6_round_trip_and_tenant_isolation(self):
        grant = self.db.upsert_workspace_grant(
            self.tenant_id,
            {
                "name": "Postgres grant",
                "root_rel": "repo",
                "read": True,
                "write": False,
                "commands": ["git"],
                "network_policy": "deny",
                "enabled": True,
                "expires_at": "2099-01-01T00:00:00+00:00",
            },
            self.tenant_id,
        )
        self.assertEqual(grant["root_rel"], "repo")
        self.assertEqual(grant["commands"], ["git"])
        self.assertTrue(grant["read"])
        self.assertFalse(grant["write"])
        self.assertEqual(self.db.get_workspace_grant(self.tenant_id, grant["id"])["id"], grant["id"])

        other_tenant = f"grant-other-{uuid.uuid4().hex}"
        self.db.ensure_tenant(other_tenant, "Grant Other")
        self.assertIsNone(self.db.get_workspace_grant(other_tenant, grant["id"]))

    def test_workspace_worktrees_v7_round_trip_and_tenant_isolation(self):
        grant = self.db.upsert_workspace_grant(
            self.tenant_id,
            {
                "name": "Worktree grant",
                "root_rel": "repo",
                "read": True,
                "write": True,
                "commands": ["git"],
                "network_policy": "deny",
                "enabled": True,
                "expires_at": "2099-01-01T00:00:00+00:00",
            },
            self.tenant_id,
        )
        record = self.db.create_workspace_worktree_record(
            self.tenant_id,
            grant["id"],
            self.tenant_id,
            repo_relative="repo",
            worktree_relative="worktrees/feature-a",
            branch="feat/a",
            start_ref="HEAD",
            expires_at=grant["expires_at"],
        )
        self.assertEqual(record["status"], "active")
        self.assertEqual(record["grant_id"], grant["id"])
        self.assertIsNone(record["task_id"])
        self.assertEqual(len(self.db.list_workspace_worktrees(self.tenant_id)), 1)

        other_tenant = f"worktree-other-{uuid.uuid4().hex}"
        self.db.ensure_tenant(other_tenant, "Worktree Other")
        self.assertIsNone(self.db.get_workspace_worktree_record(other_tenant, record["id"]))
        self.assertEqual(self.db.list_workspace_worktrees(other_tenant), [])


if __name__ == "__main__": unittest.main()
