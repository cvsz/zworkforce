from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify-zarvis-online.sh"


class ZarvisOnlineVerifierTests(unittest.TestCase):
    def run_verifier(self, http_code: int) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            fake_bin = Path(directory)
            (fake_bin / "getent").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            (fake_bin / "curl").write_text(
                "#!/usr/bin/env bash\nprintf '%s' \"${FAKE_HTTP_CODE}\"\n",
                encoding="utf-8",
            )
            for executable in (fake_bin / "getent", fake_bin / "curl"):
                executable.chmod(0o755)

            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
                    "FAKE_HTTP_CODE": str(http_code),
                    "ZARVIS_ONLINE_HOST": "zarvis.test",
                }
            )
            return subprocess.run(
                ["bash", str(SCRIPT)],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_accepts_successful_public_responses(self):
        result = self.run_verifier(204)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS: Z.A.R.V.I.S. is online", result.stdout)

    def test_rejects_redirect_responses(self):
        result = self.run_verifier(302)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected HTTP 2xx", result.stderr)


if __name__ == "__main__":
    unittest.main()
