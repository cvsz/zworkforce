from __future__ import annotations

import os
import unittest

from common import stack


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self._previous_env = {
            name: os.environ.get(name)
            for name in (
                "ZWORKFORCE_RELEASE_GATE_RECORDER",
                "ZWORKFORCE_RELEASE_INDEPENDENT_APPROVER",
                "ZWORKFORCE_RELEASE_AUTHORITY",
            )
        }
        os.environ["ZWORKFORCE_RELEASE_GATE_RECORDER"] = "arin-z"
        os.environ["ZWORKFORCE_RELEASE_INDEPENDENT_APPROVER"] = "policedbc"
        os.environ["ZWORKFORCE_RELEASE_AUTHORITY"] = "cvsz"
        self.temp, self.settings, self.db, self.provider, self.engine, self.auth = stack()

    def tearDown(self):
        self.engine.shutdown()
        self.temp.cleanup()
        for name, value in self._previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    @staticmethod
    def evidence(gate_id: str) -> dict:
        evidence = {
            "environment": "staging",
            "observed_at_utc": "2026-10-29T01:00:00Z",
            "command": f"python scripts/verify_release_stage.py --stage {gate_id}",
            "run_url": "https://github.com/cvsz/zworkforce/actions/runs/12345",
            "artifact_uri": "https://github.com/cvsz/zworkforce/actions/runs/12345/artifacts/67890",
            "artifact_sha256": "a" * 64,
            "result_summary": "Operator evidence bundle captured for independent review.",
        }
        stage_fields = {
            "A": {
                "deployed_image_digest": "sha256:" + "b" * 64,
                "ingress_hostname": "staging.zeaz.dev",
                "database_endpoint_class": "managed-postgresql",
                "secret_store_ref": "vault://release/zworkforce",
                "egress_policy_ref": "policy://release/staging",
            },
            "B": {
                "backup_id": "backup-2026-10-29T0100Z",
                "restore_run_url": "https://github.com/cvsz/zworkforce/actions/runs/12346",
                "observed_rpo_seconds": 30,
                "observed_rto_seconds": 300,
                "target_rpo_seconds": 60,
                "target_rto_seconds": 600,
                "pitr_verified": True,
            },
            "C": {
                "issuer": "https://idp.example.com",
                "jwks_kid": "release-test-key-1",
                "positive_auth_passed": True,
                "negative_auth_rejected": True,
                "api_key_lifecycle_verified": True,
            },
            "D": {
                "provider_failover_verified": True,
                "bounded_execution_verified": True,
                "mutation_deny_by_default_verified": True,
            },
            "E": {
                "scheduler_lease_exclusive": True,
                "worker_failover_verified": True,
                "outbox_claim_exclusive": True,
                "dead_letter_verified": True,
            },
            "F": {
                "put_object_succeeded": True,
                "get_object_succeeded": True,
                "sha256_verified": True,
            },
            "G": {
                "trace_correlation_verified": True,
                "alert_receipt_verified": True,
                "operator_owned_receiver": True,
            },
            "H": {
                "signature_verified": True,
                "publisher_verified": True,
                "timestamp_verified": True,
                "live_install_smoke_passed": True,
                "signed_msix_sha256": "c" * 64,
            },
        }
        evidence.update(stage_fields[gate_id])
        return evidence

    def record_all_pass(self, candidate_sha: str = "a" * 40) -> None:
        for gate_id in "ABCDEFGH":
            result = self.db.record_release_gate_evidence(
                "default", "3.0.4", candidate_sha, gate_id, self.evidence(gate_id),
                "arin-z", "arin-z-key",
            )
            self.assertTrue(result["recorded"])
            self.assertEqual(result["status"], "PASS", gate_id)

    def test_evaluator_records_pending_fail_and_blocked(self):
        pending = self.db.record_release_gate_evidence(
            "default", "3.0.4", "a" * 40, "A", {"environment": "staging"},
            "arin-z", "arin-z-key",
        )
        self.assertEqual(pending["status"], "PENDING")

        failing = self.evidence("D")
        failing["provider_failover_verified"] = False
        failed = self.db.record_release_gate_evidence(
            "default", "3.0.4", "b" * 40, "D", failing, "arin-z", "arin-z-key",
        )
        self.assertEqual(failed["status"], "FAIL")

        blocked = self.db.record_release_gate_evidence(
            "default", "3.0.4", "c" * 40, "F", {"blocked_reason": "S3 PutObject returned HTTP 403"},
            "arin-z", "arin-z-key",
        )
        self.assertEqual(blocked["status"], "BLOCKED")

    def test_go_requires_all_gates_independent_approval_and_audit(self):
        sha = "a" * 40
        self.record_all_pass(sha)
        snapshot = self.db.get_release_gate_snapshot("default", "3.0.4", sha)
        self.assertTrue(snapshot["all_gates_pass"])

        approval = self.db.approve_release_candidate(
            "default", "3.0.4", sha, "APPROVE", snapshot["gate_bundle_digest"],
            "policedbc", "policedbc-key", "Independent review of the exact candidate.",
        )
        self.assertEqual(approval["decision"], "APPROVE")

        decision = self.db.decide_release_candidate(
            "default", "3.0.4", sha, "GO", "v3.0.3", "cvsz", "cvsz-release-key",
        )
        self.assertEqual(decision["decision"], "GO")
        verified = self.db.verify_release_candidate("default", "3.0.4", sha)
        self.assertTrue(verified["release_ready"], verified["reasons"])
        self.assertTrue(verified["ledger_valid"])
        self.assertTrue(verified["audit_chain"]["ok"])

    def test_stale_digest_and_self_approval_fail_closed(self):
        sha = "d" * 40
        self.record_all_pass(sha)
        stale = self.db.get_release_gate_snapshot("default", "3.0.4", sha)["gate_bundle_digest"]

        changed = self.evidence("A")
        changed["result_summary"] = "Updated evidence bundle; digest must change."
        self.db.record_release_gate_evidence("default", "3.0.4", sha, "A", changed, "arin-z", "arin-z-key")
        current = self.db.get_release_gate_snapshot("default", "3.0.4", sha)
        self.assertNotEqual(stale, current["gate_bundle_digest"])

        stale_approval = self.db.approve_release_candidate(
            "default", "3.0.4", sha, "APPROVE", stale, "policedbc", "policedbc-key",
        )
        self.assertEqual(stale_approval["decision"], "BLOCKED")

        self_approval = self.db.approve_release_candidate(
            "default", "3.0.4", sha, "APPROVE", current["gate_bundle_digest"], "policedbc", "arin-z-key",
        )
        self.assertEqual(self_approval["decision"], "BLOCKED")

        decision = self.db.decide_release_candidate(
            "default", "3.0.4", sha, "GO", "v3.0.3", "cvsz", "cvsz-release-key",
        )
        self.assertEqual(decision["decision"], "NO_GO")

    def test_candidate_is_frozen_after_go_until_no_go_is_recorded(self):
        sha = "e" * 40
        self.record_all_pass(sha)
        snapshot = self.db.get_release_gate_snapshot("default", "3.0.4", sha)
        self.db.approve_release_candidate(
            "default", "3.0.4", sha, "APPROVE", snapshot["gate_bundle_digest"],
            "policedbc", "policedbc-key",
        )
        go = self.db.decide_release_candidate(
            "default", "3.0.4", sha, "GO", "v3.0.3", "cvsz", "cvsz-release-key",
        )
        self.assertEqual(go["decision"], "GO")

        attempted = self.db.record_release_gate_evidence(
            "default", "3.0.4", sha, "A", self.evidence("A"), "arin-z", "arin-z-key",
        )
        self.assertFalse(attempted["recorded"])
        self.assertEqual(
            self.db.get_release_gate_snapshot("default", "3.0.4", sha)["gate_bundle_digest"],
            snapshot["gate_bundle_digest"],
        )
        self.assertTrue(self.db.verify_release_candidate("default", "3.0.4", sha)["release_ready"])

        revoked = self.db.decide_release_candidate(
            "default", "3.0.4", sha, "NO_GO", "v3.0.3", "cvsz", "cvsz-release-key",
            "Operator revoked the GO decision for a controlled re-evaluation.",
        )
        self.assertEqual(revoked["decision"], "NO_GO")
        self.assertFalse(self.db.verify_release_candidate("default", "3.0.4", sha)["release_ready"])

    def test_invalid_sha_is_rejected_and_tampering_is_detected(self):
        with self.assertRaises(ValueError):
            self.db.get_release_gate_snapshot("default", "3.0.4", "abc123")

        sha = "f" * 40
        self.record_all_pass(sha)
        snapshot = self.db.get_release_gate_snapshot("default", "3.0.4", sha)
        self.db.approve_release_candidate(
            "default", "3.0.4", sha, "APPROVE", snapshot["gate_bundle_digest"],
            "policedbc", "policedbc-key",
        )
        self.db.decide_release_candidate(
            "default", "3.0.4", sha, "GO", "v3.0.3", "cvsz", "cvsz-release-key",
        )
        with self.db.connection() as c:
            c.execute(
                "UPDATE release_gate_evidence2 SET status='FAIL' WHERE tenant_id=? AND release_version=? AND candidate_sha=? AND gate_id='A'",
                ("default", "3.0.4", sha),
            )
        verified = self.db.verify_release_candidate("default", "3.0.4", sha)
        self.assertFalse(verified["release_ready"])
        self.assertFalse(verified["ledger_valid"])


if __name__ == "__main__":
    unittest.main()
