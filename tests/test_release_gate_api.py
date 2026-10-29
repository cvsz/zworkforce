from __future__ import annotations

import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from common import stack
from zworkforce.api import App


class ReleaseGateApiTests(unittest.TestCase):
    def setUp(self):
        self._previous_env = {
            name: os.environ.get(name)
            for name in (
                "ZWORKFORCE_RELEASE_GATE_RECORDER",
                "ZWORKFORCE_RELEASE_INDEPENDENT_APPROVER",
                "ZWORKFORCE_RELEASE_AUTHORITY",
                "ZWORKFORCE_RELEASE_GATE_RECORDER_KEY_ID",
                "ZWORKFORCE_RELEASE_INDEPENDENT_APPROVER_KEY_ID",
                "ZWORKFORCE_RELEASE_AUTHORITY_KEY_ID",
            )
        }
        os.environ["ZWORKFORCE_RELEASE_GATE_RECORDER"] = "arin-z"
        os.environ["ZWORKFORCE_RELEASE_INDEPENDENT_APPROVER"] = "policedbc"
        os.environ["ZWORKFORCE_RELEASE_AUTHORITY"] = "cvsz"
        os.environ.pop("ZWORKFORCE_RELEASE_GATE_RECORDER_KEY_ID", None)
        os.environ.pop("ZWORKFORCE_RELEASE_INDEPENDENT_APPROVER_KEY_ID", None)
        os.environ.pop("ZWORKFORCE_RELEASE_AUTHORITY_KEY_ID", None)
        self.temp, self.settings, self.db, self.provider, self.engine, self.auth = stack()
        self.app = App(self.settings, self.db, self.engine, self.auth, self.provider)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.app.handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

        self.recorder_key_id, self.recorder_secret = self.auth.create_key("default", "arin-z", "operator", ["release:record"])
        self.reviewer_key_id, self.reviewer_secret = self.auth.create_key("default", "policedbc", "admin", ["release:approve"])
        self.authority_key_id, self.authority_secret = self.auth.create_key("default", "cvsz", "admin", ["release:decide"])
        os.environ["ZWORKFORCE_RELEASE_GATE_RECORDER_KEY_ID"] = self.recorder_key_id
        os.environ["ZWORKFORCE_RELEASE_INDEPENDENT_APPROVER_KEY_ID"] = self.reviewer_key_id
        os.environ["ZWORKFORCE_RELEASE_AUTHORITY_KEY_ID"] = self.authority_key_id
        _, self.reader_secret = self.auth.create_key("default", "gate-reader", "viewer", ["release:read"])
        _, self.verifier_secret = self.auth.create_key("default", "gate-verifier", "viewer", ["release:verify"])

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.engine.shutdown()
        self.temp.cleanup()
        for name, value in self._previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def request(self, path, secret, method="GET", body=None):
        headers = {"Authorization": "Bearer " + secret}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    @staticmethod
    def stage_a_evidence():
        return {
            "environment": "staging",
            "observed_at_utc": "2026-10-29T01:00:00Z",
            "command": "python scripts/verify_release_stage.py --stage A",
            "run_url": "https://github.com/cvsz/zworkforce/actions/runs/12345",
            "artifact_uri": "https://github.com/cvsz/zworkforce/actions/runs/12345/artifacts/67890",
            "artifact_sha256": "a" * 64,
            "result_summary": "Staging evidence captured for the test candidate.",
            "deployed_image_digest": "sha256:" + "b" * 64,
            "ingress_hostname": "staging.zeaz.dev",
            "database_endpoint_class": "managed-postgresql",
            "secret_store_ref": "vault://release/zworkforce",
            "egress_policy_ref": "policy://release/staging",
        }

    def test_gate_routes_enforce_scopes_and_recorder_identity(self):
        sha = "a" * 40
        status, _ = self.request(f"/api/v1/release-gates/3.0.4/{sha}", self.verifier_secret)
        self.assertEqual(status, 403)

        _, impostor_secret = self.auth.create_key("default", "not-arin-z", "operator", ["release:record"])
        status, _ = self.request(
            "/api/v1/release-gates/evidence",
            impostor_secret,
            "POST",
            {
                "release_version": "3.0.4",
                "candidate_sha": sha,
                "gate_id": "A",
                "evidence": self.stage_a_evidence(),
            },
        )
        self.assertEqual(status, 403)
        self.assertTrue(self.db.verify_audit_chain("default")["ok"])
        events = self.db.list_audit("default", limit=20)
        self.assertTrue(any(item["action"] == "release_gate.authorization.denied" for item in events))

    def test_record_snapshot_and_incomplete_approval_are_audited(self):
        sha = "c" * 40
        status, record = self.request(
            "/api/v1/release-gates/evidence",
            self.recorder_secret,
            "POST",
            {
                "release_version": "3.0.4",
                "candidate_sha": sha,
                "gate_id": "A",
                "evidence": self.stage_a_evidence(),
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(record["evaluated_by"], "ARIN-Z/deterministic-v1")

        status, snapshot = self.request(
            f"/api/v1/release-gates/3.0.4/{sha}", self.reader_secret
        )
        self.assertEqual(status, 200)
        self.assertEqual(snapshot["candidate_sha"], sha)
        self.assertEqual(snapshot["gates"][0]["status"], "PASS")

        status, approval = self.request(
            f"/api/v1/release-gates/3.0.4/{sha}/approval",
            self.reviewer_secret,
            "POST",
            {
                "decision": "APPROVE",
                "expected_gate_bundle_digest": snapshot["gate_bundle_digest"],
                "rationale": "Attempted before all mandatory gates passed.",
            },
        )
        self.assertEqual(status, 409)
        self.assertEqual(approval["decision"], "BLOCKED")

        status, decision = self.request(
            f"/api/v1/release-gates/3.0.4/{sha}/decision",
            self.authority_secret,
            "POST",
            {"decision": "GO", "rollback_target": "v3.0.3"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(decision["decision"], "NO_GO")

        status, verification = self.request(
            f"/api/v1/release-gates/3.0.4/{sha}/verify", self.verifier_secret
        )
        self.assertEqual(status, 200)
        self.assertFalse(verification["release_ready"])
        self.assertTrue(verification["audit_chain"]["ok"])
        self.assertTrue(verification["ledger_valid"])


if __name__ == "__main__":
    unittest.main()
