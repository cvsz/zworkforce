import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rotate-cloudflare-secrets.sh"
SERVICE = ROOT / "deploy" / "systemd" / "cloudflare-rotation.service"
TIMER = ROOT / "deploy" / "systemd" / "cloudflare-rotation.timer"


class CloudflareRotationTests(unittest.TestCase):
    def _env_file(self, directory: Path) -> tuple[Path, str]:
        content = """# test-only values
CLOUDFLARE_API_TOKEN=api-value-must-not-print
CLOUDFLARE_TUNNEL_TOKEN=tunnel-value-must-not-print
CLOUDFLARE_ACCESS_KEY_ID=access-value-must-not-print
CLOUDFLARE_SECRET_ACCESS_KEY=secret-value-must-not-print
CLOUDFLARE_ROTATION_INTERVAL_DAYS=30
"""
        path = directory / ".env.cloudflare"
        path.write_text(content, encoding="utf-8")
        os.chmod(path, 0o600)
        return path, content

    def _run(self, *args, env=None):
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_status_lists_secret_names_without_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            env_file, _ = self._env_file(directory)
            state_file = directory / "rotation.json"

            result = self._run(
                "--status",
                "--env-file",
                str(env_file),
                "--state-file",
                str(state_file),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("interval_days=30", result.stdout)
            self.assertIn("status=uninitialized", result.stdout)
            self.assertIn("CLOUDFLARE_API_TOKEN", result.stdout)
            self.assertIn("CLOUDFLARE_TUNNEL_TOKEN", result.stdout)
            self.assertNotIn("api-value-must-not-print", result.stdout)
            self.assertNotIn("secret-value-must-not-print", result.stdout)

    def test_initialize_uses_env_mtime_and_sets_30_day_due_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            env_file, content = self._env_file(directory)
            state_file = directory / "rotation.json"

            result = self._run(
                "--initialize",
                "--env-file",
                str(env_file),
                "--state-file",
                str(state_file),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(
                state["next_rotation_epoch"] - state["last_rotation_epoch"],
                30 * 24 * 60 * 60,
            )
            self.assertEqual(env_file.read_text(encoding="utf-8"), content)
            self.assertEqual(oct(state_file.stat().st_mode & 0o777), "0o600")

    def test_execute_requires_explicit_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            env_file, _ = self._env_file(directory)
            state_file = directory / "rotation.json"
            hook_dir = directory / "hooks"
            hook_dir.mkdir()
            self._run(
                "--initialize",
                "--env-file",
                str(env_file),
                "--state-file",
                str(state_file),
            )
            state = json.loads(state_file.read_text(encoding="utf-8"))
            state["next_rotation_epoch"] = 0
            state_file.write_text(json.dumps(state), encoding="utf-8")

            clean_env = os.environ.copy()
            clean_env.pop("ROTATION_APPROVED", None)
            result = self._run(
                "--execute",
                "--env-file",
                str(env_file),
                "--state-file",
                str(state_file),
                "--hook-dir",
                str(hook_dir),
                env=clean_env,
            )

            self.assertEqual(result.returncode, 3)
            self.assertIn("ROTATION_APPROVED=YES", result.stderr)

    def test_due_execute_runs_reviewed_hook_and_advances_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            env_file, _ = self._env_file(directory)
            state_file = directory / "rotation.json"
            hook_dir = directory / "hooks"
            out_dir = directory / "rotation-output"
            hook_dir.mkdir()
            hook = hook_dir / "01-test.sh"
            hook.write_text(
                "#!/usr/bin/env bash\n"
                "set -Eeuo pipefail\n"
                "[[ -f \"$1\" ]]\n"
                "mkdir -p \"$ROTATION_OUT_DIR\"\n"
                "printf verified > \"$ROTATION_OUT_DIR/hook.verified\"\n",
                encoding="utf-8",
            )
            os.chmod(hook, 0o700)
            self._run(
                "--initialize",
                "--env-file",
                str(env_file),
                "--state-file",
                str(state_file),
            )
            state = json.loads(state_file.read_text(encoding="utf-8"))
            state["next_rotation_epoch"] = 0
            state_file.write_text(json.dumps(state), encoding="utf-8")

            execute_env = os.environ.copy()
            execute_env["ROTATION_APPROVED"] = "YES"
            result = self._run(
                "--execute",
                "--env-file",
                str(env_file),
                "--state-file",
                str(state_file),
                "--hook-dir",
                str(hook_dir),
                "--out-dir",
                str(out_dir),
                env=execute_env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            updated = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertGreater(updated["last_rotation_epoch"], 0)
            self.assertEqual(
                updated["next_rotation_epoch"] - updated["last_rotation_epoch"],
                30 * 24 * 60 * 60,
            )
            self.assertTrue((out_dir / "hook.verified").exists())
            self.assertNotIn("api-value-must-not-print", result.stdout + result.stderr)

    def test_systemd_timer_is_daily_due_check_with_30_day_state(self):
        service = SERVICE.read_text(encoding="utf-8")
        timer = TIMER.read_text(encoding="utf-8")
        self.assertIn("--execute", service)
        self.assertIn("ROTATION_APPROVED=YES", service)
        self.assertIn("OnUnitActiveSec=24h", timer)
        self.assertIn("Persistent=true", timer)


if __name__ == "__main__":
    unittest.main()
