from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RULESET = ROOT / ".github" / "rulesets" / "main.json"
CI = ROOT / ".github" / "workflows" / "ci.yml"
GITMODULES = ROOT / ".gitmodules"
DEPENDENCY_REVIEW = ROOT / ".github" / "workflows" / "dependency-review.yml"
WINDOWS = ROOT / ".github" / "workflows" / "windows-client.yml"
ZARVIS = ROOT / ".github" / "workflows" / "zarvis.yml"


class RepositoryPolicyTests(unittest.TestCase):
    def ruleset(self) -> dict:
        return json.loads(RULESET.read_text(encoding="utf-8"))

    def required_contexts(self) -> set[str]:
        rules = self.ruleset()["rules"]
        status_rule = next(rule for rule in rules if rule["type"] == "required_status_checks")
        return {
            item["context"]
            for item in status_rule["parameters"]["required_status_checks"]
        }

    def test_default_branch_ruleset_requires_prs_and_linear_safety(self):
        ruleset = self.ruleset()
        self.assertEqual("active", ruleset["enforcement"])
        self.assertIn("~DEFAULT_BRANCH", ruleset["conditions"]["ref_name"]["include"])
        rule_types = {rule["type"] for rule in ruleset["rules"]}
        self.assertLessEqual(
            {"deletion", "non_fast_forward", "pull_request", "required_status_checks"},
            rule_types,
        )

    def test_required_contexts_match_unconditional_workflow_contracts(self):
        required = self.required_contexts()
        expected = {
            "test (3.12)",
            "test (3.13)",
            "test (3.14)",
            "postgres-integration",
            "release-integrity",
            "container",
            "security-invariants",
            "documentation-contract",
            "dependency-review",
            "build-test-package",
            "Analyze (python)",
            "Analyze (actions)",
            "CodeQL",
        }
        self.assertEqual(expected, required)

        ci = CI.read_text(encoding="utf-8")
        for job in [
            "postgres-integration:",
            "release-integrity:",
            "container:",
            "security-invariants:",
            "documentation-contract:",
        ]:
            with self.subTest(job=job):
                self.assertIn(job, ci)
        for version in ['"3.12"', '"3.13"', '"3.14"']:
            self.assertIn(version, ci)

        self.assertIn("dependency-review:", DEPENDENCY_REVIEW.read_text(encoding="utf-8"))
        self.assertIn("build-test-package:", WINDOWS.read_text(encoding="utf-8"))

    def test_path_filtered_zarvis_checks_are_not_globally_required(self):
        zarvis = ZARVIS.read_text(encoding="utf-8")
        self.assertIn("pull_request:", zarvis)
        self.assertIn("paths:", zarvis)
        required = self.required_contexts()
        for context in [
            "migration-contract",
            "node-workspace",
            "zarvis-api",
            "zarvis-windows-linux-restore",
        ]:
            with self.subTest(context=context):
                self.assertNotIn(context, required)

    def test_submodules_are_ssh_accessible_and_security_validated(self):
        gitmodules = GITMODULES.read_text(encoding="utf-8")
        self.assertIn("url = git@github.com:cvsz/zksato.git", gitmodules)
        self.assertIn("url = git@github.com:cvsz/zttshop-php.git", gitmodules)
        self.assertNotIn("url = https://github.com/cvsz/", gitmodules)

        ci = CI.read_text(encoding="utf-8")
        self.assertIn("submodule-validation:", ci)
        self.assertIn("needs: submodule-validation", ci)
        self.assertIn("submodules: recursive", ci)
        self.assertIn("ssh-key: ${{ secrets.SUBMODULE_SSH_KEY }}", ci)
        self.assertIn("ssh-known-hosts:", ci)
        self.assertIn("persist-credentials: false", ci)
        self.assertIn("if: always()", ci)
        self.assertIn('run: test "${{ needs.submodule-validation.result }}" = success', ci)
        self.assertIn("Reject untrusted submodule changes", ci)
        self.assertIn('pytest -m "not uat and not performance"', ci)
        self.assertIn("composer audit --locked --no-interaction", ci)
        self.assertIn("composer test", ci)



if __name__ == "__main__":
    unittest.main()
