from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
START_SCRIPT = ROOT / "start-zworkforce.sh"


class StartupSecretHygieneTests(unittest.TestCase):
    def run_start_script(self, overrides=None):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            script = temp_root / "start-zworkforce.sh"
            script.write_text(START_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")

            # Intercept the final application launch so tests never start a service.
            bin_dir = temp_root / "bin"
            bin_dir.mkdir()
            python_stub = bin_dir / "python3"
            python_stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            python_stub.chmod(0o755)

            env = os.environ.copy()
            env.pop("ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN", None)
            env.pop("Z_PLATFORM_SERVICE_TOKEN", None)
            env["ZWORKFORCE_ZARVIS_VOICE_ENABLED"] = "true"
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            if overrides:
                env.update(overrides)

            return subprocess.run(
                ["bash", str(script)],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

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

    def test_enabled_voice_requires_a_provisioned_token_at_runtime(self):
        result = self.run_start_script()
        self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
        self.assertIn("must be provisioned", result.stderr)
        self.assertNotIn("Starting zWorkforce", result.stdout)

    def test_whitespace_only_and_short_tokens_are_rejected(self):
        for token in (" " * 40, "x" * 31):
            with self.subTest(token_length=len(token)):
                result = self.run_start_script(
                    {"ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN": token}
                )
                self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
                self.assertIn("must be provisioned", result.stderr)

    def test_supported_truthy_values_fail_closed_without_a_token(self):
        for value in ("1", "true", "yes", "on", "TRUE"):
            with self.subTest(value=value):
                result = self.run_start_script({"ZWORKFORCE_ZARVIS_VOICE_ENABLED": value})
                self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)

    def test_explicit_false_values_allow_start_without_voice_token(self):
        for value in ("false", "0", "no", "off"):
            with self.subTest(value=value):
                result = self.run_start_script({"ZWORKFORCE_ZARVIS_VOICE_ENABLED": value})
                self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
                self.assertIn("Voice Disabled", result.stdout)

    def test_provisioned_environment_token_allows_voice_start(self):
        token = "synthetic-test-token-" + ("a" * 40)
        result = self.run_start_script(
            {"ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN": token}
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("Voice Enabled", result.stdout)

    def test_legacy_environment_token_remains_backward_compatible(self):
        token = "legacy-synthetic-token-" + ("b" * 40)
        result = self.run_start_script({"Z_PLATFORM_SERVICE_TOKEN": token})
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("Voice Enabled", result.stdout)

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
