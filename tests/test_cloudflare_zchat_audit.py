import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cloudflare-zchat-audit.sh"


class CloudflareZChatAuditTests(unittest.TestCase):
    def _stub_http_tools(self, directory: Path) -> tuple[Path, Path]:
        bin_dir = directory / "bin"
        bin_dir.mkdir()
        curl_log = directory / "curl.log"
        cloudflared_log = directory / "cloudflared.log"
        curl = bin_dir / "curl"
        curl.write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s\\n' \"$*\" >> \"$ZCHAT_CURL_LOG\"\n"
            "printf '200'\n",
            encoding="utf-8",
        )
        curl.chmod(0o700)
        cloudflared = bin_dir / "cloudflared"
        cloudflared.write_text(
            "#!/usr/bin/env bash\nprintf 'called\\n' >> \"$ZCHAT_CLOUDFLARED_LOG\"\nprintf 'token: TEST_SENTINEL\\n'\nprintf 'secret=TEST_SENTINEL\\n' >&2\n",
            encoding="utf-8",
        )
        cloudflared.chmod(0o700)
        return bin_dir, curl_log, cloudflared_log

    def test_origin_rejects_non_loopback_urls_before_network_requests(self):
        invalid_origins = (
            "http://127.0.0.1:8000@attacker.example",
            "http://127.0.0.1:8000.attacker.example",
            "http://127.0.0.1:65536",
            "http://127.0.0.1:0",
            "https://127.0.0.1:8000",
        )
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            bin_dir, curl_log, cloudflared_log = self._stub_http_tools(directory)
            for origin in invalid_origins:
                with self.subTest(origin=origin):
                    env = os.environ.copy()
                    env.update(
                        {
                            "PATH": f"{bin_dir}:{os.environ['PATH']}",
                            "ZCHAT_ORIGIN": origin,
                            "ZCHAT_CURL_LOG": str(curl_log),
                            "ZCHAT_CLOUDFLARED_LOG": str(cloudflared_log),
                        }
                    )
                    result = subprocess.run(
                        ["bash", str(SCRIPT)],
                        cwd=ROOT,
                        env=env,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("Origin", result.stderr)
                    self.assertNotIn("HTTP status comparison", result.stdout)
            self.assertFalse(curl_log.exists(), "invalid origins must exit before HTTP requests")
            self.assertFalse(cloudflared_log.exists(), "invalid origins must not inspect the tunnel")

    def test_valid_loopback_origin_uses_stubbed_http_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            bin_dir, curl_log, cloudflared_log = self._stub_http_tools(directory)
            caddyfile = directory / "Caddyfile"
            caddyfile.write_text("zchat.zeaz.dev { respond 200 }\n", encoding="utf-8")

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "ZCHAT_ORIGIN": "http://127.0.0.1:8000",
                    "ZCHAT_CADDYFILE": str(caddyfile),
                    "ZCHAT_CURL_LOG": str(curl_log),
                    "ZCHAT_CLOUDFLARED_LOG": str(cloudflared_log),
                }
            )
            result = subprocess.run(
                ["bash", str(SCRIPT)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(curl_log.read_text(encoding="utf-8").splitlines()), 5)
            self.assertFalse(cloudflared_log.exists(), "default audit must not use cloudflared credentials")

            env["ZCHAT_INCLUDE_TUNNEL_INFO"] = "1"
            explicit = subprocess.run(
                ["bash", str(SCRIPT)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(explicit.returncode, 0, explicit.stderr)
            self.assertEqual(cloudflared_log.read_text(encoding="utf-8").splitlines(), ["called"])
            self.assertIn("cloudflared credentials may be used", explicit.stdout)
            self.assertNotIn("TEST_SENTINEL", explicit.stdout + explicit.stderr)


if __name__ == "__main__":
    unittest.main()
