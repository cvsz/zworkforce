from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.verify_terraform_plan import (
    PlanValidationError,
    compute_sha256,
    verify_and_copy_plan,
)


class TerraformPlanApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.plan = self.root / "tfplan"
        self.plan.write_bytes(b"immutable terraform plan fixture\nresource=cloudflare-test\n")
        self.copy = self.root / "tfplan.approved"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_printed_digest_matches_plan_bytes(self):
        expected = hashlib.sha256(self.plan.read_bytes()).hexdigest()
        self.assertEqual(expected, compute_sha256(self.plan))

    def test_exact_approved_digest_copies_the_verified_bytes(self):
        expected = hashlib.sha256(self.plan.read_bytes()).hexdigest()
        actual = verify_and_copy_plan(self.plan, expected, self.copy)
        self.assertEqual(expected, actual)
        self.assertEqual(self.plan.read_bytes(), self.copy.read_bytes())

    def test_changed_plan_is_rejected_and_verified_copy_removed(self):
        expected = hashlib.sha256(self.plan.read_bytes()).hexdigest()
        self.plan.write_bytes(b"changed after approval\n")
        with self.assertRaisesRegex(PlanValidationError, "digest mismatch"):
            verify_and_copy_plan(self.plan, expected, self.copy)
        self.assertFalse(self.copy.exists())

    def test_malformed_digest_is_rejected(self):
        with self.assertRaisesRegex(PlanValidationError, "64 lowercase hexadecimal"):
            verify_and_copy_plan(self.plan, "not-a-digest", self.copy)
        self.assertFalse(self.copy.exists())

    def test_empty_plan_is_rejected(self):
        self.plan.write_bytes(b"")
        with self.assertRaisesRegex(PlanValidationError, "empty"):
            compute_sha256(self.plan)

    def test_symlink_plan_is_rejected(self):
        link = self.root / "tfplan-link"
        link.symlink_to(self.plan)
        with self.assertRaisesRegex(PlanValidationError, "cannot safely open"):
            compute_sha256(link)

    def test_copy_target_must_be_a_distinct_regular_file(self):
        with self.assertRaisesRegex(PlanValidationError, "different file"):
            verify_and_copy_plan(self.plan, hashlib.sha256(self.plan.read_bytes()).hexdigest(), self.plan)


if __name__ == "__main__":
    unittest.main()
