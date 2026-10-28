import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CloudflareApplyApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name) / "repo"
        self.script_dir = self.root / "scripts"
        self.nested_script_dir = self.script_dir / "cloudflare"
        self.lib_dir = self.script_dir / "lib"
        self.stack = self.root / "infrastructure" / "terraform" / "cloudflare"
        self.bin_dir = Path(self.temp_dir.name) / "bin"
        self.marker = Path(self.temp_dir.name) / "applied"
        self.log = Path(self.temp_dir.name) / "terraform.log"
        self.script_dir.mkdir(parents=True)
        self.nested_script_dir.mkdir(parents=True)
        (self.lib_dir / "cloudflare").mkdir(parents=True)
        self.stack.mkdir(parents=True)
        self.bin_dir.mkdir()
        shutil.copy2(ROOT / "scripts" / "cloudflare-apply.sh", self.script_dir)
        shutil.copy2(
            ROOT / "scripts" / "cloudflare" / "cloudflare-apply.sh",
            self.nested_script_dir,
        )
        shutil.copy2(ROOT / "scripts" / "cloudflare-plan-manifest.py", self.script_dir)
        shutil.copy2(ROOT / "scripts" / "verify-zarvis-online.sh", self.script_dir)
        shutil.copy2(
            ROOT / "scripts" / "lib" / "cloudflare-terraform-env.sh", self.lib_dir
        )
        (self.stack / "providers.tf").write_text("# test fixture\n", encoding="utf-8")
        env_file = self.root / ".env.cloudflare"
        env_file.write_text(
            "CLOUDFLARE_API_TOKEN=test-token\n"
            "CLOUDFLARE_ACCOUNT_ID=account-test\n"
            "CLOUDFLARE_ZONE_ID=zone-test\n"
            "CLOUDFLARE_TUNNEL_ID=tunnel-test\n"
            "CME_ACCESS_ALLOWED_EMAILS=[\"operator@example.com\"]\n"
            "CME_ACCESS_SERVICE_TOKEN_ID=test-service-token-id\n"
            "PIEWDASH_ACCESS_ALLOWED_EMAILS=[\"operator@example.com\"]\n",
            encoding="utf-8",
        )
        env_file.chmod(0o600)
        self.terraform = self.bin_dir / "terraform"
        self.terraform.write_text(
            "#!/usr/bin/env bash\n"
            "set -Eeuo pipefail\n"
            "printf '%s\\n' \"$*\" >> \"$TF_LOG\"\n"
            "if [[ \"${1:-}\" == -chdir=* ]]; then shift; fi\n"
            "command_name=\"${1:-}\"\n"
            "shift || true\n"
            "case \"$command_name\" in\n"
            "  init|fmt|validate) exit 0 ;;\n"
            "  workspace) printf 'default\\n' ;;\n"
            "  state)\n"
            "    if [[ \"${1:-}\" == pull ]]; then printf '{\\\"version\\\":4,\\\"resources\\\":[]}\\n'; fi\n"
            "    ;;\n"
            "  plan)\n"
            "    out=\"\"\n"
            "    for argument in \"$@\"; do [[ \"$argument\" == -out=* ]] && out=\"${argument#-out=}\"; done\n"
            "    [[ -n \"$out\" ]] || exit 2\n"
            "    printf 'fake terraform plan bytes\\n' > \"$out\"\n"
            "    ;;\n"
            "  show)\n"
            "    if [[ \"${1:-}\" == -json ]]; then\n"
            "      python3 - <<'PY'\n"
            "import json\n"
            "import os\n"
            "values = {\n"
            "    'cloudflare_account_id': os.environ['TF_VAR_cloudflare_account_id'],\n"
            "    'cloudflare_zone_id': os.environ['TF_VAR_cloudflare_zone_id'],\n"
            "    'cloudflare_tunnel_id': os.environ['TF_VAR_cloudflare_tunnel_id'],\n"
            "    'enable_zeaz_one': os.environ['TF_VAR_enable_zeaz_one'] == 'true',\n"
            "    'enable_zeaz_one_api_route': os.environ['TF_VAR_enable_zeaz_one_api_route'] == 'true',\n"
            "    'zeaz_one_origin': os.environ['TF_VAR_zeaz_one_origin'],\n"
            "    'zeaz_one_hostname': os.environ['TF_VAR_zeaz_one_hostname'],\n"
            "    'zeaz_one_api_origin': os.environ['TF_VAR_zeaz_one_api_origin'],\n"
            "    'zeaz_one_api_hostname': os.environ['TF_VAR_zeaz_one_api_hostname'],\n"
            "    'zeaz_one_support_origin': os.environ['TF_VAR_zeaz_one_support_origin'],\n"
            "    'zeaz_one_support_hostname': os.environ['TF_VAR_zeaz_one_support_hostname'],\n"
            "}\n"
            "print(json.dumps({'variables': {key: {'value': value} for key, value in values.items()}}))\n"
            "PY\n"
            "      exit 0\n"
            "    fi\n"
            "    plan_path=\"${@: -1}\"\n"
            "    cat -- \"$plan_path\"\n"
            "    ;;\n"
            "  apply)\n"
            "    plan_path=\"${@: -1}\"\n"
            "    [[ -r \"$plan_path\" ]] || exit 3\n"
            "    touch \"$APPLIED_MARKER\"\n"
            "    ;;\n"
            "  *) echo \"unexpected terraform command: $command_name\" >&2; exit 4 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        self.terraform.chmod(0o755)
        for command in ("curl", "jq", "getent"):
            stub = self.bin_dir / command
            if command == "curl":
                stub.write_text(
            "#!/usr/bin/env bash\n"
            "if [[ \" $* \" == *\" --write-out \"* ]]; then printf '200'; fi\n"
            "if [[ -n \"${CURL_FAIL_FOR:-}\" && \"$*\" == *\"$CURL_FAIL_FOR\"* ]]; then exit 22; fi\n"
            "exit 0\n",
                    encoding="utf-8",
                )
            else:
                stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            stub.chmod(0o755)

    def _run(self, *args, script_path=None):
        env = os.environ.copy()
        env.update(
            {
                "CLOUDFLARE_ROOT": str(self.root),
                "CLOUDFLARE_STACK": str(self.stack),
                "CLOUDFLARE_ENV_FILE": str(self.root / ".env.cloudflare"),
                "TERRAFORM_BIN": str(self.terraform),
                "TF_LOG": str(self.log),
                "APPLIED_MARKER": str(self.marker),
                "CURL_FAIL_FOR": getattr(self, "curl_fail_for", ""),
                "PATH": f"{self.bin_dir}:/usr/bin:/bin",
            }
        )
        script_path = script_path or self.script_dir / "cloudflare-apply.sh"
        return subprocess.run(
            ["bash", str(script_path), *args],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_apply_uses_only_the_existing_plan_when_digest_matches(self):
        plan_path = self.stack / "tfplan.reviewed"
        planned = self._run("--skip-import", "--plan-file", str(plan_path))
        self.assertEqual(planned.returncode, 0, planned.stderr)
        self.assertFalse(self.marker.exists(), "plan mode must never apply")
        digest = hashlib.sha256(plan_path.read_bytes()).hexdigest()
        self.assertIn(f"Plan SHA-256: {digest}", planned.stdout)
        approval_digest = re.search(r"Approval SHA-256: ([0-9a-f]{64})", planned.stdout)
        self.assertIsNotNone(approval_digest)
        approval_digest = approval_digest.group(1)
        manifest_path = Path(f"{plan_path}.manifest.json")
        self.assertTrue(manifest_path.is_file())
        self.assertEqual(manifest_path.stat().st_mode & 0o777, 0o600)
        self.assertNotEqual(approval_digest, digest)
        self.assertRegex(
            planned.stdout,
            re.compile(r"--approved-plan-sha256 " + re.escape(approval_digest)),
        )

        before_apply = self.log.read_text(encoding="utf-8").splitlines()
        applied = self._run(
            "--apply",
            "--plan-file",
            str(plan_path),
            "--approved-plan-sha256",
            approval_digest,
        )
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertTrue(self.marker.exists())
        apply_calls = self.log.read_text(encoding="utf-8").splitlines()[len(before_apply) :]
        self.assertTrue(any(" apply " in f" {call} " for call in apply_calls))
        self.assertFalse(any(" plan " in f" {call} " for call in apply_calls))
        self.assertFalse(any("state pull" in call for call in apply_calls))
        self.assertIn("Applying the exact saved Terraform plan", applied.stdout)
        self.assertIn("HA-A public health check passed", applied.stdout)
        self.assertIn("PASS: Z.A.R.V.I.S. is online", applied.stdout)

    def test_nested_apply_entrypoint_uses_shared_root_helpers(self):
        plan_path = self.stack / "tfplan.nested-entrypoint"
        planned = self._run(
            "--skip-import",
            "--plan-file",
            str(plan_path),
            script_path=self.nested_script_dir / "cloudflare-apply.sh",
        )

        self.assertEqual(planned.returncode, 0, planned.stderr)
        self.assertTrue(Path(f"{plan_path}.manifest.json").is_file())

    def test_digest_mismatch_refuses_apply(self):
        plan_path = self.stack / "tfplan.reviewed"
        planned = self._run("--skip-import", "--plan-file", str(plan_path))
        self.assertEqual(planned.returncode, 0, planned.stderr)

        rejected = self._run(
            "--apply",
            "--plan-file",
            str(plan_path),
            "--approved-plan-sha256",
            "0" * 64,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("does not match", rejected.stderr)
        self.assertFalse(self.marker.exists())
        calls = self.log.read_text(encoding="utf-8").splitlines()
        self.assertFalse(any(" apply " in f" {call} " for call in calls))

    def test_existing_plan_path_is_rejected_before_terraform_or_dns_import(self):
        plan_path = self.stack / "tfplan.reviewed"
        plan_path.write_text("existing reviewed plan\n", encoding="utf-8")
        plan_path.chmod(0o600)

        rejected = self._run("--plan-file", str(plan_path))

        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("Refusing to overwrite an existing plan file", rejected.stderr)
        self.assertFalse(self.log.exists(), "plan-path guard must precede Terraform init")

    def test_changed_target_environment_rejects_before_backend_init(self):
        plan_path = self.stack / "tfplan.reviewed"
        planned = self._run("--skip-import", "--plan-file", str(plan_path))
        self.assertEqual(planned.returncode, 0, planned.stderr)
        approval_digest = re.search(r"Approval SHA-256: ([0-9a-f]{64})", planned.stdout).group(1)
        before_apply = self.log.read_text(encoding="utf-8").splitlines()

        env_file = self.root / ".env.cloudflare"
        content = env_file.read_text(encoding="utf-8").replace(
            "CLOUDFLARE_ZONE_ID=zone-test", "CLOUDFLARE_ZONE_ID=zone-changed"
        )
        env_file.write_text(content, encoding="utf-8")
        env_file.chmod(0o600)
        rejected = self._run(
            "--apply",
            "--plan-file",
            str(plan_path),
            "--approved-plan-sha256",
            approval_digest,
        )

        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("target differs", rejected.stderr)
        calls = self.log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(calls, before_apply, "target mismatch must fail before Terraform init")

    def test_manifest_changes_invalidate_the_approval_digest(self):
        plan_path = self.stack / "tfplan.reviewed"
        planned = self._run("--skip-import", "--plan-file", str(plan_path))
        self.assertEqual(planned.returncode, 0, planned.stderr)
        approval_digest = re.search(r"Approval SHA-256: ([0-9a-f]{64})", planned.stdout).group(1)
        before_apply = self.log.read_text(encoding="utf-8").splitlines()

        manifest_path = Path(f"{plan_path}.manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["metadata"]["target"]["zone_id"] = "zone-changed"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        manifest_path.chmod(0o600)
        rejected = self._run(
            "--apply",
            "--plan-file",
            str(plan_path),
            "--approved-plan-sha256",
            approval_digest,
        )

        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("manifest approval digest is invalid", rejected.stderr)
        calls = self.log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(calls, before_apply, "changed manifest must fail before Terraform init")

    def test_configuration_changes_invalidate_the_approval_digest(self):
        plan_path = self.stack / "tfplan.config-change"
        planned = self._run("--skip-import", "--plan-file", str(plan_path))
        self.assertEqual(planned.returncode, 0, planned.stderr)
        approval_digest = re.search(r"Approval SHA-256: ([0-9a-f]{64})", planned.stdout).group(1)
        before_apply = self.log.read_text(encoding="utf-8").splitlines()

        providers_file = self.stack / "providers.tf"
        providers_file.write_text(
            providers_file.read_text(encoding="utf-8") + "\n",
            encoding="utf-8",
        )
        rejected = self._run(
            "--apply",
            "--plan-file",
            str(plan_path),
            "--approved-plan-sha256",
            approval_digest,
        )

        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("target differs", rejected.stderr)
        calls = self.log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(calls, before_apply, "configuration change must fail before Terraform init")

    def test_environment_file_changes_invalidate_the_approval_digest(self):
        plan_path = self.stack / "tfplan.environment-change"
        planned = self._run("--skip-import", "--plan-file", str(plan_path))
        self.assertEqual(planned.returncode, 0, planned.stderr)
        approval_digest = re.search(r"Approval SHA-256: ([0-9a-f]{64})", planned.stdout).group(1)
        before_apply = self.log.read_text(encoding="utf-8").splitlines()

        env_file = self.root / ".env.cloudflare"
        with env_file.open("a", encoding="utf-8") as stream:
            stream.write("ZEAZ_ONE_ORIGIN=http://127.0.0.1:29999\n")
        env_file.chmod(0o600)
        rejected = self._run(
            "--apply",
            "--plan-file",
            str(plan_path),
            "--approved-plan-sha256",
            approval_digest,
        )

        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("target differs", rejected.stderr)
        calls = self.log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(calls, before_apply, "environment change must fail before Terraform init")

    def test_post_apply_health_checks_follow_approved_zeaz_one_features(self):
        plan_path = self.stack / "tfplan.zeaz-one"
        planned = self._run("--skip-import", "--zeaz-one", "--plan-file", str(plan_path))
        self.assertEqual(planned.returncode, 0, planned.stderr)
        approval_digest = re.search(r"Approval SHA-256: ([0-9a-f]{64})", planned.stdout).group(1)

        applied = self._run(
            "--apply",
            "--plan-file",
            str(plan_path),
            "--approved-plan-sha256",
            approval_digest,
        )

        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertIn("ZEAZ One origin healthy", applied.stdout)
        self.assertIn("ZEAZ One API origin healthy", applied.stdout)
        self.assertIn("http://127.0.0.1:18081/", applied.stdout)
        self.assertNotIn("http://127.0.0.1:29999/", applied.stdout)

    def test_ha_health_check_failure_fails_the_apply_command(self):
        plan_path = self.stack / "tfplan.health-check"
        planned = self._run("--skip-import", "--plan-file", str(plan_path))
        self.assertEqual(planned.returncode, 0, planned.stderr)
        approval_digest = re.search(r"Approval SHA-256: ([0-9a-f]{64})", planned.stdout).group(1)
        self.curl_fail_for = "https://zwf.zeaz.dev/health"

        applied = self._run(
            "--apply",
            "--plan-file",
            str(plan_path),
            "--approved-plan-sha256",
            approval_digest,
        )

        self.assertNotEqual(applied.returncode, 0)
        self.assertTrue(self.marker.exists(), "Terraform apply ran before post-apply verification")
        self.assertNotIn("PASS: Z.A.R.V.I.S. is online", applied.stdout)

    def test_apply_requires_approval_digest_and_existing_plan(self):
        without_digest = self._run("--apply")
        self.assertNotEqual(without_digest.returncode, 0)
        self.assertIn("--approved-plan-sha256", without_digest.stderr)
        self.assertFalse(self.log.exists(), "invalid apply requests must stop before Terraform")

    def test_ha_workflow_has_no_production_apply_action(self):
        workflow = (ROOT / ".github" / "workflows" / "ha-infrastructure.yml").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("--apply", workflow)
        self.assertNotRegex(workflow, re.compile(r"^\s+- apply\s*$", re.MULTILINE))
        self.assertIn("create a non-applying plan", workflow)
        self.assertIn("PGSERVICEFILE", workflow)
        self.assertIn("PGSERVICE=zworkforce-preflight", workflow)
        self.assertIn("unset SUPABASE_DATABASE_URL", workflow)
        self.assertNotIn('psql "$SUPABASE_DATABASE_URL"', workflow)
        self.assertNotIn("CLOUDFLARE_API_TOKEN=$CLOUDFLARE_API_TOKEN", workflow)
        self.assertIn("shlex.quote(value)", workflow)


if __name__ == "__main__":
    unittest.main()
