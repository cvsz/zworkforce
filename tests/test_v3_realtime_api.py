from __future__ import annotations

import threading
import unittest
import urllib.error
import urllib.request
from dataclasses import replace
from http.server import ThreadingHTTPServer

from common import stack
from zworkforce.api import App
from zworkforce.realtime import (
    format_dashboard_event,
    format_dashboard_heartbeat,
    parse_event_cursor,
    stream_dashboard_events,
)


class DashboardRealtimeProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.settings, self.db, self.provider, self.engine, self.auth = stack()

    def tearDown(self):
        self.engine.shutdown()
        self.temp.cleanup()

    def test_cursor_parser_and_sse_formatters_are_strict_and_compact(self):
        self.assertEqual(parse_event_cursor(None), 0)
        self.assertEqual(parse_event_cursor("42"), 42)
        with self.assertRaises(ValueError):
            parse_event_cursor("-1")
        with self.assertRaises(ValueError):
            parse_event_cursor("1.5")
        with self.assertRaises(ValueError):
            parse_event_cursor("not-a-cursor")

        event = {
            "id": 42,
            "event_type": "task.changed",
            "resource_type": "task",
            "resource_id": "task-1",
            "payload": {"summary": {"status": "running"}},
            "created_at": "2026-08-30T00:00:00+00:00",
        }
        encoded = format_dashboard_event(event).decode("utf-8")
        self.assertIn("id: 42\n", encoded)
        self.assertIn("event: task.changed\n", encoded)
        self.assertIn('"resource_id":"task-1"', encoded)
        self.assertNotIn("created_at", encoded)
        heartbeat = format_dashboard_heartbeat(42, event["created_at"]).decode("utf-8")
        self.assertEqual(
            heartbeat,
            'id: 42\nevent: heartbeat\ndata: {"cursor":42,"server_time":"2026-08-30T00:00:00+00:00"}\n\n',
        )

    def test_bounded_stream_replays_events_and_reports_stale_cursor(self):
        first_id = self.db.append_dashboard_event("default", "task.changed", "task", "task-1")
        second_id = self.db.append_dashboard_event("default", "usage.changed", "task", "task-1")
        third_id = self.db.append_dashboard_event("default", "provider.changed", "provider", "mock")
        writes: list[bytes] = []

        final_cursor = stream_dashboard_events(
            self.db,
            "default",
            first_id,
            writes.append,
            max_seconds=0,
            poll_seconds=0.001,
            heartbeat_seconds=5,
        )
        joined = b"".join(writes).decode("utf-8")
        self.assertEqual(final_cursor, third_id)
        self.assertIn(f"id: {second_id}\n", joined)
        self.assertIn("event: heartbeat\n", joined)

        with self.db.connection() as connection:
            connection.execute(
                "UPDATE dashboard_events2 SET created_at=? WHERE id IN (?,?)",
                ("2000-01-01T00:00:00+00:00", first_id, second_id),
            )
        self.db.prune_dashboard_events("2001-01-01T00:00:00+00:00")
        writes.clear()
        stream_dashboard_events(self.db, "default", first_id, writes.append, max_seconds=0)
        self.assertIn("event: resync.required\n", b"".join(writes).decode("utf-8"))
        self.assertIn(f'"cursor":{third_id}', b"".join(writes).decode("utf-8"))

    def test_stream_requires_resync_after_all_tenant_events_expire(self):
        event_id = self.db.append_dashboard_event("default", "task.changed", "task", "expired-task")
        with self.db.connection() as connection:
            connection.execute(
                "UPDATE dashboard_events2 SET created_at=? WHERE id=?",
                ("2000-01-01T00:00:00+00:00", event_id),
            )
        self.db.prune_dashboard_events("2001-01-01T00:00:00+00:00")
        writes: list[bytes] = []

        final_cursor = stream_dashboard_events(
            self.db,
            "default",
            event_id,
            writes.append,
            max_seconds=0,
        )

        body = b"".join(writes).decode("utf-8")
        self.assertEqual(final_cursor, 0)
        self.assertIn("event: resync.required\n", body)
        self.assertIn('"cursor":0', body)
        self.assertIn('"oldest":0', body)

    def test_initial_cursor_replays_sparse_tenant_without_false_resync(self):
        self.db.ensure_tenant("other", "Other")
        self.db.append_dashboard_event("other", "task.changed", "task", "other-task")
        default_id = self.db.append_dashboard_event("default", "task.changed", "task", "default-task")
        writes: list[bytes] = []

        stream_dashboard_events(self.db, "default", 0, writes.append, max_seconds=0)
        body = b"".join(writes).decode("utf-8")
        self.assertIn(f"id: {default_id}\n", body)
        self.assertIn("default-task", body)
        self.assertNotIn("resync.required", body)

    def test_stream_is_tenant_scoped(self):
        self.db.ensure_tenant("other", "Other")
        self.db.append_dashboard_event("default", "task.changed", "task", "default-task")
        other_id = self.db.append_dashboard_event("other", "task.changed", "task", "other-task")
        writes: list[bytes] = []
        stream_dashboard_events(self.db, "default", 0, writes.append, max_seconds=0)
        body = b"".join(writes).decode("utf-8")
        self.assertIn("default-task", body)
        self.assertNotIn("other-task", body)


class DashboardRealtimeApiTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.settings, self.db, self.provider, self.engine, self.auth = stack()
        self.settings = replace(self.settings, cors_origins=("https://dashboard.example",))
        self.app = App(self.settings, self.db, self.engine, self.auth, self.provider)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.app.handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.engine.shutdown()
        self.temp.cleanup()

    def _request(self, path: str, headers: dict[str, str] | None = None):
        request = urllib.request.Request(
            self.base + path,
            headers={"Authorization": "Bearer test-admin-secret", **(headers or {})},
        )
        return urllib.request.urlopen(request, timeout=5)

    def test_stream_requires_auth_and_uses_protected_headers(self):
        request = urllib.request.Request(self.base + "/api/v1/dashboard/events")
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(context.exception.code, 401)

        self.db.append_dashboard_event("default", "task.changed", "task", "task-api")
        response = self._request(
            "/api/v1/dashboard/events?cursor=999999",
            {"X-ZWorkforce-Event-Cursor": "0", "Accept": "text/event-stream"},
        )
        try:
            self.assertEqual(response.headers["Content-Type"], "text/event-stream; charset=utf-8")
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(response.headers["X-Accel-Buffering"], "no")
            first_frame = response.readline().decode("utf-8")
            self.assertTrue(first_frame.startswith("id: "))
            body = first_frame + response.readline().decode("utf-8") + response.readline().decode("utf-8")
            self.assertIn("task-api", body)
        finally:
            response.close()

    def test_viewer_stream_omits_audit_metadata(self):
        _, viewer_secret = self.auth.create_key("default", "viewer", "viewer", ["workforce:read"])
        self.db.audit("default", "operator", "api_key.revoke", "api_key", "sensitive-key-id")
        self.db.append_dashboard_event("default", "task.changed", "task", "visible-task")
        request = urllib.request.Request(
            self.base + "/api/v1/dashboard/events",
            headers={
                "Authorization": "Bearer " + viewer_secret,
                "Accept": "text/event-stream",
                "X-ZWorkforce-Event-Cursor": "0",
            },
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            body = "".join(response.readline().decode("utf-8") for _ in range(4))
        self.assertIn("event: task.changed", body)
        self.assertNotIn("audit.changed", body)
        self.assertNotIn("sensitive-key-id", body)

    def test_cors_preflight_allows_event_cursor_header(self):
        request = urllib.request.Request(
            self.base + "/api/v1/dashboard/events",
            headers={
                "Origin": "https://dashboard.example",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization,X-ZWorkforce-Event-Cursor",
            },
            method="OPTIONS",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 204)
            self.assertIn("X-ZWorkforce-Event-Cursor", response.headers["Access-Control-Allow-Headers"])

    def test_malformed_cursor_is_rejected_and_nested_static_paths_are_scoped(self):
        with self.assertRaises(urllib.error.HTTPError) as context:
            self._request("/api/v1/dashboard/events", {"X-ZWorkforce-Event-Cursor": "invalid"})
        self.assertEqual(context.exception.code, 400)

        for path in ("/dashboard/core/realtime.js", "/dashboard/packages/realtime/index.js"):
            with self._request(path) as response:
                self.assertEqual(response.status, 200)
                self.assertIn("javascript", response.headers["Content-Type"])
                self.assertGreater(len(response.read()), 100)

        with self.assertRaises(urllib.error.HTTPError) as context:
            self._request("/dashboard/%2e%2e/api.py")
        self.assertEqual(context.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
