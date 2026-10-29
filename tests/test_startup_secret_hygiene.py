from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
START_SCRIPT = ROOT / "start-zworkforce.sh"


class StartupSecretHygieneTests(unittest.TestCase):
    def run_start_script(self, overrides=None, *, xtrace=False, voice_enabled="true", env_file_content=None):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            script = temp_root / "start-zworkforce.sh"
            script.write_text(START_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
            if env_file_content is not None:
                (temp_root / ".env.ai").write_text(env_file_content, encoding="utf-8")

            # Intercept the final application launch so tests never start a service.
            bin_dir = temp_root / "bin"
            bin_dir.mkdir()
            python_stub = bin_dir / "python3"
            python_stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            python_stub.chmod(0o755)

            env = os.environ.copy()
            env.pop("ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN", None)
            env.pop("Z_PLATFORM_SERVICE_TOKEN", None)
            if voice_enabled is None:
                env.pop("ZWORKFORCE_ZARVIS_VOICE_ENABLED", None)
            else:
                env["ZWORKFORCE_ZARVIS_VOICE_ENABLED"] = voice_enabled
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            if overrides:
                env.update(overrides)

            command = ["bash"]
            if xtrace:
                command.append("-x")
            command.append(str(script))
            return subprocess.run(
                command,
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
        token_assignments = [
            line
            for line in script.splitlines()
            if line.startswith("export ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN=")
        ]
        self.assertEqual(
            token_assignments,
            ['export ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN="${ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN:-}"'],
        )

    def test_voice_defaults_disabled_when_not_configured(self):
        result = self.run_start_script(voice_enabled=None)
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("Voice Disabled", result.stdout)
        self.assertNotIn("must be provisioned", result.stderr)

    def test_enabled_voice_requires_a_provisioned_token_at_runtime(self):
        result = self.run_start_script()
        self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
        self.assertIn("must be provisioned", result.stderr)
        self.assertNotIn("Starting zWorkforce", result.stdout)

    def test_tokens_with_fewer_than_32_non_whitespace_characters_are_rejected(self):
        tokens = (
            " " * 40,
            "x" * 31,
            "x" * 31 + " ",
            "x" * 16 + "\t" + "x" * 15,
        )
        for token in tokens:
            with self.subTest(token_length=len(token), non_whitespace=sum(not c.isspace() for c in token)):
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

    def test_shell_xtrace_does_not_log_provisioned_token(self):
        token = "synthetic-xtrace-secret-" + ("c" * 40)
        result = self.run_start_script(
            {"ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN": token},
            xtrace=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertNotIn(token, result.stdout)
        self.assertNotIn(token, result.stderr)

    def test_shell_xtrace_does_not_log_token_loaded_from_env_file(self):
        token = "synthetic-env-file-token-" + ("d" * 40)
        result = self.run_start_script(
            env_file_content=f"ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN='{token}'\n",
            xtrace=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("Voice Enabled", result.stdout)
        self.assertNotIn(token, result.stdout)
        self.assertNotIn(token, result.stderr)

    def test_legacy_platform_token_is_not_used_as_voice_service_token(self):
        token = "legacy-synthetic-token-" + ("b" * 40)
        result = self.run_start_script({"Z_PLATFORM_SERVICE_TOKEN": token})
        self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
        self.assertIn("must be provisioned", result.stderr)
        self.assertNotIn("Voice Enabled", result.stdout)
        self.assertNotIn(token, result.stdout + result.stderr)

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
