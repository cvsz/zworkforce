import unittest
from datetime import datetime, timedelta, timezone

from zworkforce.sagi_production_gate import (
    REQUIRED, DeploymentEvidence, assert_sagi_production_ready,
)


class ProductionGateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 10, tzinfo=timezone.utc)
        self.sha = "a" * 40
        self.items = tuple(DeploymentEvidence(
            gate=gate, reference="evidence://staging/" + gate,
            attested_at=self.now, reviewed_by="independent-operator",
            deployment_sha=self.sha,
        ) for gate in sorted(REQUIRED))

    def verify(self, evidence=None, **kw):
        return assert_sagi_production_ready(
            evidence=self.items if evidence is None else evidence,
            deployment_sha=kw.pop("deployment_sha", self.sha), now=self.now, **kw,
        )

    def test_complete_evidence_contract(self):
        self.assertIsNone(self.verify())

    def test_missing_gate_fails_closed(self):
        with self.assertRaises(PermissionError):
            self.verify(self.items[:-1])

    def test_duplicate_or_unknown_gate_fails_closed(self):
        with self.assertRaises(PermissionError):
            self.verify(self.items + (self.items[0],))
        wrong = DeploymentEvidence(
            "nonexistent", "evidence://x", self.now, "reviewer", self.sha
        )
        with self.assertRaises(PermissionError):
            self.verify(self.items + (wrong,))

    def test_other_release_sha_or_expired_attestation_denied(self):
        changed = self.items[0]
        expired = DeploymentEvidence(
            changed.gate, changed.reference, self.now - timedelta(days=8),
            changed.reviewed_by, changed.deployment_sha,
        )
        with self.assertRaises(PermissionError):
            self.verify((expired,) + self.items[1:])
        with self.assertRaises(PermissionError):
            self.verify(deployment_sha="not-a-sha")

    def test_future_dated_evidence_denied(self):
        first = self.items[0]
        future = DeploymentEvidence(
            first.gate, first.reference, self.now + timedelta(seconds=1),
            first.reviewed_by, first.deployment_sha,
        )
        with self.assertRaises(PermissionError):
            self.verify((future,) + self.items[1:])


if __name__ == "__main__":
    unittest.main()
