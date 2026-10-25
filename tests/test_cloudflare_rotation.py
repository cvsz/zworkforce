import json
import os
import subprocess
import tempfile
import time
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
CLOUDFLARE_GLOBAL=global-key-must-not-print
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
            self.assertIn("CLOUDFLARE_GLOBAL", result.stdout)
            self.assertNotIn("api-value-must-not-print", result.stdout)
            self.assertNotIn("secret-value-must-not-print", result.stdout)
            self.assertNotIn("global-key-must-not-print", result.stdout)

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

    def test_status_parses_quoted_rotation_interval_without_awk_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            env_file, content = self._env_file(directory)
            env_file.write_text(
                content.replace("CLOUDFLARE_ROTATION_INTERVAL_DAYS=30", "CLOUDFLARE_ROTATION_INTERVAL_DAYS='45'"),
                encoding="utf-8",
            )
            state_file = directory / "rotation.json"

            result = self._run(
                "--status",
                "--env-file",
                str(env_file),
                "--state-file",
                str(state_file),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            self.assertIn("interval_days=45", result.stdout)

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

    def test_execute_rejects_concurrent_rotation(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            env_file, _ = self._env_file(directory)
            state_file = directory / "rotation.json"
            hook_dir = directory / "hooks"
            out_dir = directory / "rotation-output"
            hook_dir.mkdir()
            hook = hook_dir / "01-slow.sh"
            hook.write_text(
                "#!/usr/bin/env bash\n"
                "set -Eeuo pipefail\n"
                "touch \"$ROTATION_OUT_DIR/hook.started\"\n"
                "sleep 1.5\n"
                "printf 'run\\n' >> \"$ROTATION_OUT_DIR/hook-runs\"\n",
                encoding="utf-8",
            )
            os.chmod(hook, 0o700)

            initialized = self._run(
                "--initialize",
                "--env-file",
                str(env_file),
                "--state-file",
                str(state_file),
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            state = json.loads(state_file.read_text(encoding="utf-8"))
            state["next_rotation_epoch"] = 0
            state_file.write_text(json.dumps(state), encoding="utf-8")

            execute_env = os.environ.copy()
            execute_env["ROTATION_APPROVED"] = "YES"
            execute_args = [
                "--execute",
                "--env-file",
                str(env_file),
                "--state-file",
                str(state_file),
                "--hook-dir",
                str(hook_dir),
                "--out-dir",
                str(out_dir),
            ]
            first = subprocess.Popen(
                ["bash", str(SCRIPT), *execute_args],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=execute_env,
            )
            started = out_dir / "hook.started"
            deadline = time.monotonic() + 5
            while not started.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(started.exists(), "first invocation should enter the provider hook")

            second = subprocess.run(
                ["bash", str(SCRIPT), *execute_args],
                check=False,
                capture_output=True,
                text=True,
                env=execute_env,
                timeout=3,
            )
            self.assertEqual(second.returncode, 6, second.stderr)
            self.assertIn("another rotation operation is already in progress", second.stderr)

            first_stdout, first_stderr = first.communicate(timeout=5)
            self.assertEqual(first.returncode, 0, first_stderr or first_stdout)
            self.assertEqual((out_dir / "hook-runs").read_text().splitlines(), ["run"])
            lock_file = Path(f"{state_file}.lock")
            self.assertEqual(lock_file.stat().st_mode & 0o777, 0o600)

    def test_systemd_timer_is_daily_due_check_with_30_day_state(self):
        service = SERVICE.read_text(encoding="utf-8")
        timer = TIMER.read_text(encoding="utf-8")
        self.assertIn("--execute", service)
        self.assertIn("ROTATION_APPROVED=YES", service)
        self.assertIn("OnUnitActiveSec=24h", timer)
        self.assertIn("Persistent=true", timer)

    def test_account_token_hook_keeps_tokens_out_of_argv_and_preserves_recovery_copy(self):
        hook = ROOT / "scripts" / "cloudflare-rotation.d" / "10-account-api-token.sh"
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            env_file = directory / ".env.cloudflare"
            bootstrap_file = directory / "bootstrap.env"
            records_file = directory / "curl-records.jsonl"
            shim_dir = directory / "bin"
            output_dir = directory / "evidence"
            shim_dir.mkdir()
            env_file.write_text(
                "CLOUDFLARE_API_TOKEN=runtime-secret-value\n"
                "CLOUDFLARE_ACCOUNT_ID=account-id\n"
                "CLOUDFLARE_TUNNEL_ID=tunnel-id\n",
                encoding="utf-8",
            )
            bootstrap_file.write_text(
                "CLOUDFLARE_ROTATION_BOOTSTRAP_TOKEN=bootstrap-secret-value\n",
                encoding="utf-8",
            )
            os.chmod(env_file, 0o600)
            os.chmod(bootstrap_file, 0o600)

            curl_shim = shim_dir / "curl"
            curl_shim.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, pathlib, sys\n"
                "args = sys.argv[1:]\n"
                "headers = [args[i + 1] for i, value in enumerate(args[:-1]) if value == '-H']\n"
                "auth_ref = next(value[1:] for value in headers if value.startswith('@'))\n"
                "auth_path = pathlib.Path(auth_ref)\n"
                "auth = auth_path.read_text().strip()\n"
                "record = {'args': args, 'auth': auth, 'mode': auth_path.stat().st_mode & 0o777}\n"
                "with open(os.environ['CURL_RECORDS_FILE'], 'a', encoding='utf-8') as out: out.write(json.dumps(record) + '\\n')\n"
                "url = args[-1]\n"
                "if url.endswith('/tokens/verify') and 'replacement-secret-value' in auth and os.environ.get('FAIL_NEW_TOKEN_VERIFY') == '1':\n"
                "    print(json.dumps({'success': False, 'errors': [{'message': 'verification unavailable'}]})); sys.exit(0)\n"
                "elif url.endswith('/tokens/verify') and 'runtime-secret-value' in auth: result = {'id': 'runtime-id', 'status': 'active'}\n"
                "elif url.endswith('/tokens/verify') and 'bootstrap-secret-value' in auth: result = {'id': 'bootstrap-id', 'status': 'active'}\n"
                "elif url.endswith('/tokens/runtime-id/value'): result = 'replacement-secret-value'\n"
                "elif url.endswith('/tokens/verify'): result = {'id': 'runtime-id', 'status': 'active'}\n"
                "else: result = {'id': 'tunnel-id'}\n"
                "print(json.dumps({'success': True, 'result': result}))\n",
                encoding="utf-8",
            )
            os.chmod(curl_shim, 0o700)
            run_env = os.environ.copy()
            run_env.update(
                {
                    "PATH": f"{shim_dir}:{run_env['PATH']}",
                    "ROTATION_BOOTSTRAP_ENV_FILE": str(bootstrap_file),
                    "ROTATION_OUT_DIR": str(output_dir),
                    "CLOUDFLARE_API_ROOT": "https://api.cloudflare.test/client/v4",
                    "CURL_RECORDS_FILE": str(records_file),
                }
            )

            env_file.write_text(
                "CLOUDFLARE_API_TOKEN=runtime-secret-value\n"
                "CLOUDFLARE_API_TOKEN=duplicate-value\n"
                "CLOUDFLARE_ACCOUNT_ID=account-id\n"
                "CLOUDFLARE_TUNNEL_ID=tunnel-id\n",
                encoding="utf-8",
            )
            duplicate = subprocess.run(
                ["bash", str(hook), str(env_file)],
                check=False,
                capture_output=True,
                text=True,
                env=run_env,
            )
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("exactly one CLOUDFLARE_API_TOKEN assignment", duplicate.stderr)
            self.assertFalse(records_file.exists(), "preflight must fail before any Cloudflare API call")
            env_file.write_text(
                "CLOUDFLARE_API_TOKEN=runtime-secret-value\n"
                "CLOUDFLARE_ACCOUNT_ID=account-id\n"
                "CLOUDFLARE_TUNNEL_ID=tunnel-id\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                ["bash", str(hook), str(env_file)],
                check=False,
                capture_output=True,
                text=True,
                env=run_env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("account_api_token_rotated=true", result.stdout)
            records = [json.loads(line) for line in records_file.read_text().splitlines()]
            self.assertEqual(len(records), 5)
            for record in records:
                self.assertEqual(record["mode"], 0o600)
                self.assertTrue(any(arg.startswith("@") for arg in record["args"]))
                self.assertNotIn("runtime-secret-value", " ".join(record["args"]))
                self.assertNotIn("bootstrap-secret-value", " ".join(record["args"]))
            self.assertEqual(records[0]["auth"], "Authorization: Bearer runtime-secret-value")
            self.assertEqual(records[2]["auth"], "Authorization: Bearer bootstrap-secret-value")
            self.assertFalse(any(Path(arg[1:]).exists() for record in records for arg in record["args"] if arg.startswith("@")))
            self.assertIn("CLOUDFLARE_API_TOKEN=replacement-secret-value", env_file.read_text())
            self.assertEqual(list(output_dir.glob(".account-api-token-recovery.*")), [])

            # Simulate a transient verification failure after Cloudflare has
            # already invalidated the old value. The replacement must remain
            # recoverable without being printed or passed in process arguments.
            env_file.write_text(
                "CLOUDFLARE_API_TOKEN=runtime-secret-value\n"
                "CLOUDFLARE_ACCOUNT_ID=account-id\n"
                "CLOUDFLARE_TUNNEL_ID=tunnel-id\n",
                encoding="utf-8",
            )
            fail_env = run_env.copy()
            fail_env["FAIL_NEW_TOKEN_VERIFY"] = "1"
            failed = subprocess.run(
                ["bash", str(hook), str(env_file)],
                check=False,
                capture_output=True,
                text=True,
                env=fail_env,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertNotIn("replacement-secret-value", failed.stdout + failed.stderr)
            self.assertIn("replacement token saved in mode-0600 recovery file", failed.stderr)
            recovery_files = list(output_dir.glob(".account-api-token-recovery.*"))
            self.assertEqual(len(recovery_files), 1)
            recovery_file = recovery_files[0]
            self.assertEqual(recovery_file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(recovery_file.read_text(), "CLOUDFLARE_API_TOKEN=replacement-secret-value\n")
            self.assertEqual(env_file.read_text().splitlines()[0], "CLOUDFLARE_API_TOKEN=runtime-secret-value")
            self.assertFalse(any(Path(arg[1:]).exists() for record in [json.loads(line) for line in records_file.read_text().splitlines()] for arg in record["args"] if arg.startswith("@")))


            # Simulate recovery-copy verification failure after the remote roll.
            recovery_file.unlink()
            cmp_shim = shim_dir / "cmp"
            cmp_shim.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
            os.chmod(cmp_shim, 0o700)
            persistence_env = run_env.copy()
            persistence_env.pop("FAIL_NEW_TOKEN_VERIFY", None)
            persistence_failure = subprocess.run(
                ["bash", str(hook), str(env_file)],
                check=False,
                capture_output=True,
                text=True,
                env=persistence_env,
            )
            self.assertNotEqual(persistence_failure.returncode, 0)
            self.assertIn("recovery persistence could not be verified", persistence_failure.stderr)
            self.assertIn("manual bootstrap recovery is required", persistence_failure.stderr)
            self.assertNotIn("replacement token saved in mode-0600 recovery file", persistence_failure.stderr)
            self.assertNotIn("replacement-secret-value", persistence_failure.stdout + persistence_failure.stderr)
            self.assertEqual(list(output_dir.glob(".account-api-token-recovery.*")), [])
            self.assertEqual(env_file.read_text().splitlines()[0], "CLOUDFLARE_API_TOKEN=runtime-secret-value")


    def test_execute_surfaces_recovery_path_without_leaking_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            env_file, _ = self._env_file(directory)
            state_file = directory / "rotation.json"
            hook_dir = directory / "hooks"
            out_dir = directory / "rotation-output"
            hook_dir.mkdir()
            recovery_file = out_dir / ".account-api-token-recovery.test"
            hook = hook_dir / "10-failing-rotation.sh"
            hook.write_text(
                "#!/usr/bin/env bash\n"
                "set -Eeuo pipefail\n"
                "printf 'CLOUDFLARE_API_TOKEN=%s\\n' \"$RECOVERY_TOKEN\" > \"$RECOVERY_FILE\"\n"
                "chmod 600 \"$RECOVERY_FILE\"\n"
                "printf 'cloudflare account-token rotation: replacement token saved in mode-0600 recovery file: %s\\n' \"$RECOVERY_FILE\" >&2\n"
                "printf 'sensitive-provider-diagnostic-must-not-leak\\n' >&2\n"
                "exit 1\n",
                encoding="utf-8",
            )
            os.chmod(hook, 0o700)

            initialized = self._run(
                "--initialize",
                "--env-file",
                str(env_file),
                "--state-file",
                str(state_file),
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            state = json.loads(state_file.read_text(encoding="utf-8"))
            state["next_rotation_epoch"] = 0
            state_file.write_text(json.dumps(state), encoding="utf-8")

            execute_env = os.environ.copy()
            execute_env.update({
                "ROTATION_APPROVED": "YES",
                "RECOVERY_FILE": str(recovery_file),
                "RECOVERY_TOKEN": "replacement-token-secret-must-not-leak",
            })
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

            self.assertEqual(result.returncode, 5)
            self.assertIn(str(recovery_file), result.stderr)
            self.assertIn("replacement token saved in mode-0600 recovery file", result.stderr)
            self.assertIn("hook failed: 10-failing-rotation.sh", result.stderr)
            self.assertNotIn("replacement-token-secret-must-not-leak", result.stdout + result.stderr)
            self.assertNotIn("sensitive-provider-diagnostic-must-not-leak", result.stdout + result.stderr)
            self.assertTrue(recovery_file.is_file())
            self.assertEqual(recovery_file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(
                recovery_file.read_text(encoding="utf-8"),
                "CLOUDFLARE_API_TOKEN=replacement-token-secret-must-not-leak\n",
            )
            updated_state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(updated_state["next_rotation_epoch"], 0)
            self.assertEqual(list(out_dir.glob(".rotation-hook-stderr.*")), [])


if __name__ == "__main__":
    unittest.main()
