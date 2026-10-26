from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
START_SCRIPT = ROOT / "start-zworkforce.sh"


class StartupSecretHygieneTests(unittest.TestCase):
    def test_voice_service_token_has_no_literal_secret_fallback(self):
        script = START_SCRIPT.read_text(encoding="utf-8")
        self.assertNotRegex(
            script,
            r"Z_PLATFORM_SERVICE_TOKEN:-[0-9a-fA-F]{32,}",
            "Startup scripts must never embed a service-token fallback.",
        )
        self.assertIn(
            'ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN:-${Z_PLATFORM_SERVICE_TOKEN:-}',
            script,
        )

    def test_enabled_voice_requires_a_provisioned_minimum_length_token(self):
        script = START_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('if [[ "$ZWORKFORCE_ZARVIS_VOICE_ENABLED" == "true" ]]', script)
        self.assertIn("${#ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN} -lt 32", script)
        self.assertIn("no default token is provided", script)
        self.assertIn("exit 1", script)

    def test_start_script_is_valid_bash(self):
        result = subprocess.run(
            ["bash", "-n", str(START_SCRIPT)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)


if __name__ == "__main__":
    unittest.main()
