"""Fail-closed contract tests for read-only release attestations."""
import unittest
from tools.portfolio_gate.attestation import verify_attestation


class AttestationFailClosedTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {"repositories": {"cvsz/example": {"main_sha": "a" * 40}}}
        self.evidence = {"claims": {}}
        self.trust = {"schema_version": 1, "verifiers": {}, "operators": {}}

    def test_missing_receipt(self):
        self.assertEqual(verify_attestation(self.snapshot, self.evidence, None, self.trust),
                         "ATTESTATION_SCHEMA")

    def test_missing_signers(self):
        self.assertEqual(verify_attestation(self.snapshot, self.evidence,
                         {"schema_version": 1}, self.trust),
                         "ATTESTATION_UNTRUSTED_OR_MALFORMED")

    def test_unpinned_trust_store(self):
        self.assertEqual(verify_attestation(self.snapshot, self.evidence,
                         {"schema_version": 1}, {}),
                         "TRUST_STORE_INVALID")


if __name__ == "__main__":
    unittest.main()
