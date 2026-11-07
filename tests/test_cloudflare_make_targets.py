from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APPROVAL_DIGEST = "a" * 64


class CloudflareMakeTargetAdmissionTests(unittest.TestCase):
    def run_make(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["make", "--no-print-directory", *arguments],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_plan_target_delegates_to_guarded_non_reconciling_wrapper(self) -> None:
        result = self.run_make("-n", "cloudflare-plan")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "./scripts/cloudflare-apply.sh --skip-import --plan-file",
            result.stdout,
        )
        self.assertNotIn("verify_terraform_plan.py", result.stdout)
        self.assertNotIn("terraform plan", result.stdout)
        self.assertNotIn("terraform apply", result.stdout)

    def test_apply_target_delegates_to_manifest_guard(self) -> None:
        result = self.run_make(
            "-n",
            "cloudflare-apply",
            f"approved_plan_sha256={APPROVAL_DIGEST}",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("./scripts/cloudflare-apply.sh --apply", result.stdout)
        self.assertIn("--plan-file", result.stdout)
        self.assertIn("--approved-plan-sha256", result.stdout)
        self.assertIn("CLOUDFLARE_APPROVED_PLAN_SHA256", result.stdout)
        self.assertNotIn("terraform apply", result.stdout)
        self.assertNotIn("-auto-approve", result.stdout)
        self.assertNotIn("verify_terraform_plan.py", result.stdout)

    def test_missing_approval_digest_fails_before_wrapper(self) -> None:
        result = self.run_make("cloudflare-apply", "approved_plan_sha256=")

        self.assertEqual(result.returncode, 2)
        self.assertIn("set approved_plan_sha256", result.stderr)
        self.assertNotIn("scripts/cloudflare-apply.sh", result.stdout)


if __name__ == "__main__":
    unittest.main()
