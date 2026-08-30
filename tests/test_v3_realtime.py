from __future__ import annotations

import json
import unittest

from common import stack
from zworkforce.scheduler import Scheduler


class DashboardEventRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.settings, self.db, self.provider, self.engine, self.auth = stack()

    def tearDown(self):
        self.engine.shutdown()
        self.temp.cleanup()

    def test_events_are_tenant_scoped_and_payloads_are_allowlisted(self):
        self.db.ensure_tenant("other", "Other")
        event_id = self.db.append_dashboard_event(
            "default",
            "task.changed",
            "task",
            "task-1",
            {"summary": {"status": "running", "attempt": 1, "secret": "must-drop"}},
        )

        self.assertGreater(event_id, 0)
        self.assertEqual(self.db.dashboard_event_cursor("default"), event_id)
        self.assertEqual(
            self.db.list_dashboard_events("default")[0]["payload"],
            {"summary": {"status": "running", "attempt": 1}},
        )
        self.assertEqual(self.db.list_dashboard_events("other"), [])

    def test_cursor_limits_and_pruning_are_bounded(self):
        event_ids = [
            self.db.append_dashboard_event("default", "task.changed", "task", f"task-{i}")
            for i in range(105)
        ]

        self.assertEqual(len(self.db.list_dashboard_events("default", limit=100)), 100)
        self.assertEqual(
            [row["id"] for row in self.db.list_dashboard_events("default", after_id=event_ids[-2])],
            [event_ids[-1]],
        )
        with self.assertRaises(ValueError):
            self.db.list_dashboard_events("default", after_id=-1)
        with self.assertRaises(ValueError):
            self.db.list_dashboard_events("default", limit=0)

        removed = self.db.prune_dashboard_events("9999-12-31T23:59:59+00:00", tenant_id="default")
        self.assertEqual(removed, 105)
        self.assertEqual(self.db.dashboard_event_bounds("default"), {"oldest": None, "latest": None})
        self.assertEqual(self.db.dashboard_event_cursor("default"), 0)

    def test_scheduler_prunes_events_using_configured_retention(self):
        event_id = self.db.append_dashboard_event("default", "task.changed", "task", "expired-task")
        with self.db.connection() as connection:
            connection.execute(
                "UPDATE dashboard_events2 SET created_at=? WHERE id=?",
                ("2000-01-01T00:00:00+00:00", event_id),
            )

        stats = Scheduler(
            self.db,
            self.engine,
            dashboard_event_retention_seconds=60,
        ).tick()

        self.assertEqual(stats["dashboard_events_pruned"], 1)
        self.assertEqual(self.db.list_dashboard_events("default"), [])

    def test_task_and_audit_transitions_emit_only_safe_summaries(self):
        task, created = self.db.create_task(
            {
                "id": "task-redaction",
                "tenant_id": "default",
                "agent_id": "researcher",
                "prompt": "private prompt must not reach the dashboard stream",
                "created_by": "operator",
                "status": "queued",
                "tier": "terra",
                "model": "mock-terra",
            }
        )
        self.assertTrue(created)
        self.db.task_event(
            "default",
            task["id"],
            "completed",
            "worker",
            {
                "status": "succeeded",
                "attempt": 1,
                "outcome_status": "passed",
                "outcome_score": 0.99,
                "prompt": "private prompt",
                "result": "private result",
                "input_tokens": 99,
                "password": "private password",
                "error": "private error",
            },
        )
        self.db.audit(
            "default",
            "operator",
            "task.completed",
            "task",
            task["id"],
            {
                "prompt": "private prompt",
                "result": "private result",
                "input_tokens": 99,
                "password": "private password",
                "error": "private error",
            },
        )

        events = self.db.list_dashboard_events("default")
        self.assertGreaterEqual(len(events), 3)
        encoded = json.dumps(events, sort_keys=True)
        for secret in ("private prompt", "private result", "private password", "private error", "input_tokens"):
            self.assertNotIn(secret, encoded)
        task_events = [event for event in events if event["resource_id"] == task["id"] and event["event_type"] == "task.changed"]
        completed = next(event for event in task_events if event["payload"]["summary"]["status"] == "succeeded")
        self.assertEqual(completed["payload"]["summary"]["outcome_status"], "passed")
        self.assertEqual(completed["payload"]["summary"]["outcome_score"], 0.99)
        self.assertTrue(any(event["event_type"] == "audit.changed" for event in events))

    def test_control_plane_transitions_emit_domain_events_without_sensitive_payloads(self):
        task, _ = self.db.create_task(
            {
                "id": "task-domain-events",
                "tenant_id": "default",
                "agent_id": "researcher",
                "prompt": "domain event task",
                "created_by": "operator",
                "status": "queued",
                "tier": "terra",
                "model": "mock-terra",
            }
        )
        self.db.record_usage(task, "mock", "mock-terra", 1, 0, 2, 0.001)
        self.db.set_budget("default", "global", "global", "daily", 10)
        self.db.record_provider_success("mock", 4.5, "default")

        workflow = self.db.upsert_workflow(
            "default",
            {"id": "workflow-live", "name": "Live", "definition": {"steps": []}},
            "operator",
        )
        run = self.db.create_workflow_run("default", workflow, "operator", {})
        self.db.finish_workflow_run(run["id"], "succeeded", {})
        self.db.upsert_schedule(
            "default",
            {
                "id": "schedule-live",
                "target_type": "workflow",
                "target_id": workflow["id"],
                "schedule_type": "interval",
                "interval_seconds": 60,
                "next_run_at": "2099-01-01T00:00:00+00:00",
            },
            "operator",
        )
        self.db.mark_schedule_run("default", "schedule-live", "2099-01-01T00:01:00+00:00")
        self.db.upsert_event_rule(
            "default",
            {
                "id": "rule-live",
                "event_type": "task.changed",
                "target_type": "workflow",
                "target_id": workflow["id"],
            },
            "operator",
        )
        event = self.db.emit_event("default", "task.changed", "test", {"private": "drop"})
        self.db.finish_event(event["id"], "processed")

        suite = self.db.upsert_evaluation_suite(
            "default",
            {
                "id": "suite-live",
                "name": "Live",
                "agent_id": "researcher",
                "cases": [],
                "variants": [],
            },
            "operator",
        )
        evaluation_run = self.db.create_evaluation_run("default", suite["id"], "operator")
        self.db.add_evaluation_result("default", evaluation_run["id"], "case-1", "terra", task["id"])
        self.db.finish_evaluation_run(evaluation_run["id"], "succeeded", {})
        artifact = self.db.register_artifact(
            "default",
            {
                "name": "report.txt",
                "storage_uri": "s3://private/report.txt",
                "sha256": "a" * 64,
                "size_bytes": 4,
                "task_id": task["id"],
            },
            "operator",
        )
        self.db.set_slo_policy(
            "default",
            {"id": "latency", "metric": "p95_duration_ms", "comparator": "lte", "target": 10},
        )

        event_types = {event["event_type"] for event in self.db.list_dashboard_events("default")}
        self.assertTrue(
            {
                "usage.changed",
                "budget.changed",
                "provider.changed",
                "workflow.changed",
                "schedule.changed",
                "event.changed",
                "evaluation.changed",
                "artifact.changed",
                "slo.changed",
            }.issubset(event_types)
        )
        encoded = json.dumps(self.db.list_dashboard_events("default"), sort_keys=True)
        self.assertNotIn("s3://private/report.txt", encoded)
        self.assertNotIn("private", encoded)
        self.assertEqual(artifact["name"], "report.txt")

    def test_expired_lease_transitions_emit_task_events(self):
        task, _ = self.db.create_task(
            {
                "id": "task-expired-lease",
                "tenant_id": "default",
                "agent_id": "researcher",
                "prompt": "lease transition",
                "created_by": "operator",
                "status": "queued",
                "tier": "terra",
                "model": "mock-terra",
            }
        )
        claimed = self.db.claim_next_task("worker", 30)
        self.assertEqual(claimed["id"], task["id"])
        self.db.update_task(task["id"], lease_expires_at="2000-01-01T00:00:00+00:00")
        self.db.requeue_expired_leases()
        events = [
            event for event in self.db.list_dashboard_events("default")
            if event["resource_id"] == task["id"] and event["event_type"] == "task.changed"
        ]
        self.assertEqual(events[-1]["payload"]["summary"]["status"], "queued")


if __name__ == "__main__":
    unittest.main()
