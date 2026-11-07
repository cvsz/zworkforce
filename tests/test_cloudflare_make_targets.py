from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APPROVAL_DIGEST = "a" * 64


class CloudflareMakeTargetAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.scripts = self.root / "scripts"
        self.scripts.mkdir()
        shutil.copy2(ROOT / "Makefile", self.root / "Makefile")

        self.capture_file = self.root / "wrapper-args.txt"
        self.invocation_marker = self.root / "wrapper-invoked"
        wrapper = self.scripts / "cloudflare-apply.sh"
        wrapper.write_text(
            """#!/usr/bin/env bash
set -euo pipefail
: "${CAPTURE_FILE:?}"
: "${WRAPPER_MARKER:?}"
printf '%s\\n' "$@" > "$CAPTURE_FILE"
: > "$WRAPPER_MARKER"
""",
            encoding="utf-8",
        )
        wrapper.chmod(0o700)

        self.env = os.environ.copy()
        self.env["CAPTURE_FILE"] = str(self.capture_file)
        self.env["WRAPPER_MARKER"] = str(self.invocation_marker)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_make(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["make", "--no-print-directory", *arguments],
            cwd=self.root,
            env=self.env,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_plan_target_uses_guarded_wrapper_and_skips_dns_reconciliation(self) -> None:
        plan_path = "review plans/approved candidate.tfplan"
        result = self.run_make("cloudflare-plan", f"CLOUDFLARE_PLAN_FILE={plan_path}")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.invocation_marker.exists())
        self.assertEqual(
            self.capture_file.read_text(encoding="utf-8").splitlines(),
            ["--skip-import", "--plan-file", plan_path],
        )

    def test_apply_forwards_exact_approval_and_saved_plan_to_guard(self) -> None:
        plan_path = "review plans/approved candidate.tfplan"
        result = self.run_make(
            "cloudflare-apply",
            f"approved_plan_sha256={APPROVAL_DIGEST}",
            f"CLOUDFLARE_PLAN_FILE={plan_path}",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.invocation_marker.exists())
        self.assertEqual(
            self.capture_file.read_text(encoding="utf-8").splitlines(),
            [
                "--apply",
                "--plan-file",
                plan_path,
                "--approved-plan-sha256",
                APPROVAL_DIGEST,
            ],
        )

    def test_missing_approval_digest_fails_before_wrapper(self) -> None:
        result = self.run_make("cloudflare-apply", "approved_plan_sha256=")

        self.assertEqual(result.returncode, 2)
        self.assertIn("set approved_plan_sha256", result.stderr)
        self.assertFalse(self.invocation_marker.exists())


if __name__ == "__main__":
    unittest.main()
