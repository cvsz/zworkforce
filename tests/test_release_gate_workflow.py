from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseGateWorkflowTests(unittest.TestCase):
    def test_tag_release_and_manual_container_publication_fail_closed(self):
        release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        trusted_verifier = 'git show refs/remotes/origin/main:scripts/verify_release_gate.py > "$RUNNER_TEMP/verify_release_gate.py"'
        self.assertEqual(release.count(trusted_verifier), 2)
        self.assertEqual(release.count('python "$RUNNER_TEMP/verify_release_gate.py" --version "$RELEASE_VERSION" --sha "$CANDIDATE_SHA"'), 3)
        self.assertNotIn("python scripts/verify_release_gate.py", release)
        self.assertIn("git fetch origin main:refs/remotes/origin/main", release)
        publish = release[release.index("  publish:"):]
        self.assertLess(
            publish.index("Fetch trusted main release gate verifier"),
            publish.index("Re-verify ARIN-Z gate immediately before OCI publication"),
        )
        self.assertLess(
            release.index(trusted_verifier),
            release.index("Verify ARIN-Z exact-SHA release gate"),
        )
        self.assertLess(
            release.index("Verify ARIN-Z exact-SHA release gate"),
            release.index("Build Python distributions"),
        )
        self.assertLess(
            release.index("Re-verify ARIN-Z gate immediately before OCI publication"),
            release.index("Build and push OCI image"),
        )
        self.assertLess(
            release.index("Re-verify ARIN-Z gate immediately before GitHub Release publication"),
            release.index("Create or update GitHub Release with all platform assets"),
        )

        manual = (ROOT / ".github" / "workflows" / "publish-container.yml").read_text(encoding="utf-8")
        self.assertIn("steps.meta.outputs.candidate_sha", manual)
        self.assertIn("refs/remotes/origin/main:scripts/verify_release_gate.py", manual)
        self.assertLess(
            manual.index("Verify ARIN-Z exact-SHA release gate"),
            manual.index("Login to GitHub Container Registry"),
        )
        runbook = (ROOT / "docs" / "GITHUB-OPERATIONS.md").read_text(encoding="utf-8")
        self.assertIn("ZWORKFORCE_RELEASE_GATE_URL", runbook)
        self.assertIn("ZWORKFORCE_RELEASE_GATE_TOKEN", runbook)

    def test_current_release_requires_gate_configuration(self):
        env = dict(os.environ)
        env.pop("ZWORKFORCE_RELEASE_GATE_URL", None)
        env.pop("ZWORKFORCE_RELEASE_GATE_TOKEN", None)
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_release_gate.py"), "--version", "3.0.4", "--sha", "a" * 40],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fail-closed", result.stderr)

    def test_older_release_does_not_require_new_gate_endpoint(self):
        env = dict(os.environ)
        env.pop("ZWORKFORCE_RELEASE_GATE_URL", None)
        env.pop("ZWORKFORCE_RELEASE_GATE_TOKEN", None)
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_release_gate.py"), "--version", "3.0.3", "--sha", "a" * 40],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["skipped"])

    def test_release_gate_client_never_follows_redirects_with_authorization(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        from urllib.error import HTTPError
        from urllib.request import Request, build_opener

        from scripts.verify_release_gate import _NoRedirectHandler

        observed = []

        class RedirectHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                observed.append((self.path, self.headers.get("Authorization")))
                if self.path == "/start":
                    self.send_response(302)
                    self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/collect")
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()

            def log_message(self, format, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.server_port}/start",
                headers={"Authorization": "Bearer synthetic-release-gate-token"},
            )
            with self.assertRaises(HTTPError) as raised:
                build_opener(_NoRedirectHandler).open(request, timeout=2)
            self.assertEqual(raised.exception.code, 302)
            self.assertEqual(observed, [("/start", "Bearer synthetic-release-gate-token")])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

if __name__ == "__main__":
    unittest.main()
