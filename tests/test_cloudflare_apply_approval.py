import hashlib
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
        self.lib_dir = self.script_dir / "lib"
        self.stack = self.root / "infrastructure" / "terraform" / "cloudflare"
        self.bin_dir = Path(self.temp_dir.name) / "bin"
        self.marker = Path(self.temp_dir.name) / "applied"
        self.log = Path(self.temp_dir.name) / "terraform.log"
        self.script_dir.mkdir(parents=True)
        (self.lib_dir / "cloudflare").mkdir(parents=True)
        self.stack.mkdir(parents=True)
        self.bin_dir.mkdir()
        shutil.copy2(ROOT / "scripts" / "cloudflare-apply.sh", self.script_dir)
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
        for command in ("curl", "jq"):
            stub = self.bin_dir / command
            stub.write_text("#!/usr/bin/env bash\nexit 22\n", encoding="utf-8")
            stub.chmod(0o755)

    def _run(self, *args):
        env = os.environ.copy()
        env.update(
            {
                "CLOUDFLARE_ROOT": str(self.root),
                "CLOUDFLARE_STACK": str(self.stack),
                "CLOUDFLARE_ENV_FILE": str(self.root / ".env.cloudflare"),
                "TERRAFORM_BIN": str(self.terraform),
                "TF_LOG": str(self.log),
                "APPLIED_MARKER": str(self.marker),
                "PATH": f"{self.bin_dir}:/usr/bin:/bin",
            }
        )
        return subprocess.run(
            ["bash", str(self.script_dir / "cloudflare-apply.sh"), *args],
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
        self.assertRegex(
            planned.stdout,
            re.compile(r"--approved-plan-sha256 " + re.escape(digest)),
        )

        before_apply = self.log.read_text(encoding="utf-8").splitlines()
        applied = self._run(
            "--apply",
            "--plan-file",
            str(plan_path),
            "--approved-plan-sha256",
            digest,
        )
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertTrue(self.marker.exists())
        apply_calls = self.log.read_text(encoding="utf-8").splitlines()[len(before_apply) :]
        self.assertTrue(any(" apply " in f" {call} " for call in apply_calls))
        self.assertFalse(any(" plan " in f" {call} " for call in apply_calls))
        self.assertFalse(any("state pull" in call for call in apply_calls))
        self.assertIn("Applying the exact saved Terraform plan", applied.stdout)

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
