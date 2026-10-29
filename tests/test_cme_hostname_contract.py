#!/usr/bin/env python3
"""Behavioral regression test for the canonical CMe Terraform hostname."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def extract_block(source: str, marker: str) -> str:
    start = source.index(marker)
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Unterminated HCL block: {marker}")


class CMeHostnameContractTests(unittest.TestCase):
    def test_canonical_hostname_is_accepted_and_override_is_rejected(self):
        terraform = shutil.which("terraform")
        if terraform is None:
            self.skipTest(
                "Terraform is installed and this contract is exercised by "
                "the dedicated CMe operator contract workflow"
            )

        variables = (ROOT / "infrastructure/terraform/cloudflare/variables.tf").read_text(
            encoding="utf-8"
        )
        block = extract_block(variables, 'variable "cmeerp_hostname" {')

        with tempfile.TemporaryDirectory(prefix="cme-hostname-contract-") as temp:
            module = Path(temp)
            (module / "main.tf").write_text(
                block + '\n\noutput "hostname" { value = var.cmeerp_hostname }\n',
                encoding="utf-8",
            )

            initialized = subprocess.run(
                [terraform, "init", "-backend=false", "-input=false"],
                cwd=module,
                text=True,
                capture_output=True,
                check=False,
                timeout=60,
            )
            self.assertEqual(
                initialized.returncode, 0, initialized.stdout + initialized.stderr
            )

            accepted = subprocess.run(
                [
                    terraform,
                    "plan",
                    "-input=false",
                    "-refresh=false",
                    "-var=cmeerp_hostname=cme.zeaz.dev",
                ],
                cwd=module,
                text=True,
                capture_output=True,
                check=False,
                timeout=60,
            )
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

            rejected = subprocess.run(
                [
                    terraform,
                    "plan",
                    "-input=false",
                    "-refresh=false",
                    "-var=cmeerp_hostname=unexpected.zeaz.dev",
                ],
                cwd=module,
                text=True,
                capture_output=True,
                check=False,
                timeout=60,
            )
            self.assertNotEqual(rejected.returncode, 0, "Non-canonical CMe hostname was accepted")
            self.assertIn(
                "cmeerp_hostname must be cme.zeaz.dev",
                rejected.stdout + rejected.stderr,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
