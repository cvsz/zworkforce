from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RULESET = ROOT / ".github" / "rulesets" / "main.json"
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"
CI = ROOT / ".github" / "workflows" / "ci.yml"
GITMODULES = ROOT / ".gitmodules"
CONTROL = ROOT / "control.sh"
DEPENDENCY_REVIEW = ROOT / ".github" / "workflows" / "dependency-review.yml"
WINDOWS = ROOT / ".github" / "workflows" / "windows-client.yml"
ZARVIS = ROOT / ".github" / "workflows" / "zarvis.yml"
INDEPENDENT_REVIEW = ROOT / ".github" / "workflows" / "request-independent-review.yml"


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

        pull_request_rule = next(
            rule for rule in ruleset["rules"] if rule["type"] == "pull_request"
        )
        parameters = pull_request_rule["parameters"]
        self.assertGreaterEqual(parameters["required_approving_review_count"], 1)
        self.assertTrue(parameters["dismiss_stale_reviews_on_push"])
        self.assertTrue(parameters["require_code_owner_review"])
        self.assertTrue(parameters["require_last_push_approval"])
        self.assertEqual([], ruleset["bypass_actors"])

    def test_security_sensitive_paths_require_independent_codeowner(self):
        owners = {}
        for raw_line in CODEOWNERS.read_text(encoding="utf-8").splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            path, *reviewers = line.split()
            owners[path] = reviewers

        self.assertEqual(["@cvsz"], owners.get("*"))
        for path in (
            "/.github/",
            "/zworkforce/security.py",
            "/zworkforce/policy.py",
            "/zworkforce/secret_store.py",
            "/zworkforce/skill_registry.py",
            "/deploy/",
            "/SECURITY.md",
            "/apps/zwallet/",
        ):
            with self.subTest(path=path):
                self.assertEqual(["@policedbc"], owners.get(path))

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
            "zchat-contract",
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
            "zchat-contract:",
        ]:
            with self.subTest(job=job):
                self.assertIn(job, ci)
        for version in ['"3.12"', '"3.13"', '"3.14"']:
            self.assertIn(version, ci)

        self.assertIn("dependency-review:", DEPENDENCY_REVIEW.read_text(encoding="utf-8"))
        self.assertIn("build-test-package:", WINDOWS.read_text(encoding="utf-8"))

    def test_independent_review_workflow_is_request_only(self):
        workflow = INDEPENDENT_REVIEW.read_text(encoding="utf-8")
        runbook = (ROOT / "docs" / "GITHUB-OPERATIONS.md").read_text(encoding="utf-8")
        self.assertIn("Request independent PR review", runbook)
        self.assertIn("pull_request_target:", workflow)
        self.assertIn(
            "types: [opened, reopened, ready_for_review, synchronize]", workflow
        )
        self.assertIn("contents: read", workflow)
        self.assertIn("pull-requests: write", workflow)
        self.assertIn("github.event.pull_request.draft == false", workflow)
        self.assertIn("github.event.pull_request.user.login != 'policedbc'", workflow)
        self.assertIn("-f 'reviewers[]=policedbc'", workflow)
        self.assertNotIn("actions/checkout", workflow)
        self.assertNotIn("gh pr merge", workflow)
        self.assertNotIn("gh pr review", workflow)

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

    def test_submodules_are_pinned_accessible_and_security_validated(self):
        gitmodules = GITMODULES.read_text(encoding="utf-8")
        self.assertIn("url = git@github.com:cvsz/zksato.git", gitmodules)
        self.assertIn("url = git@github.com:cvsz/zttshop-php.git", gitmodules)
        self.assertIn("url = ../zmovie.git", gitmodules)
        self.assertIn("url = ../zok.git", gitmodules)
        self.assertNotIn("url = https://github.com/cvsz/", gitmodules)

        ci = CI.read_text(encoding="utf-8")
        self.assertIn("submodule-validation:", ci)
        self.assertIn("needs: submodule-validation", ci)
        self.assertIn("git submodule update --init --recursive --depth=1", ci)
        self.assertIn("python -m pip install --upgrade pip 'setuptools>=83.0.0'", ci)
        self.assertIn("ZKSATO_SUBMODULE_SSH_KEY: ${{ secrets.ZKSATO_SUBMODULE_SSH_KEY }}", ci)
        self.assertIn("ZTTSHOP_PHP_SUBMODULE_SSH_KEY: ${{ secrets.ZTTSHOP_PHP_SUBMODULE_SSH_KEY }}", ci)
        self.assertIn("git@github.com-zksato:cvsz/zksato.git", ci)
        self.assertIn("git@github.com-zttshop-php:cvsz/zttshop-php.git", ci)
        sync_index = ci.index("git submodule sync --recursive")
        for alias in [
            "git config --local submodule.packages/zksato.url git@github.com-zksato:cvsz/zksato.git",
            "git config --local submodule.packages/zttshop-php.url git@github.com-zttshop-php:cvsz/zttshop-php.git",
        ]:
            with self.subTest(alias=alias):
                self.assertGreater(ci.index(alias), sync_index)
        self.assertIn("~/.ssh/known_hosts", ci)
        self.assertIn("persist-credentials: false", ci)
        self.assertIn("if: always()", ci)
        self.assertIn('run: test "${{ needs.submodule-validation.result }}" = success', ci)
        self.assertIn("Reject untrusted submodule changes", ci)
        self.assertIn(".gitmodules packages/zksato packages/zttshop-php packages/zmovie packages/zok", ci)
        self.assertIn(
            'test "$(git -C packages/zmovie rev-parse HEAD)" = "$(git rev-parse HEAD:packages/zmovie)"',
            ci,
        )
        self.assertIn(
            'test "$(git -C packages/zok rev-parse HEAD)" = "$(git rev-parse HEAD:packages/zok)"',
            ci,
        )
        self.assertIn("- name: Validate zmovie", ci)
        self.assertIn("python scripts/verify_docs.py", ci)
        self.assertIn("ruff check app.py main.py zmovie_platform tests", ci)
        self.assertIn("python -m unittest discover -s tests -v", ci)
        self.assertIn("pip-audit -r requirements.txt", ci)
        self.assertIn("docker compose config --quiet", ci)
        self.assertIn("docker build -t zmovie:submodule-ci .", ci)
        self.assertIn('pytest -m "not uat and not performance"', ci)
        self.assertIn("bandit -q -r src --severity-level medium", ci)
        self.assertIn(
            "python -m pip install -e '.[dev,security]' 'boto3>=1.35,<2.0'",
            ci,
        )
        self.assertIn("composer audit --locked --no-interaction", ci)
        self.assertIn("composer test", ci)

        control = CONTROL.read_text(encoding="utf-8")
        self.assertIn(
            "git submodule update --init --recursive --depth=1 -- packages/zok",
            control,
        )
        self.assertIn('if [ -f "packages/zok/package.json" ]; then', control)
        self.assertIn(
            'log_error "packages/zok is not initialized; expected packages/zok/package.json"',
            control,
        )
        self.assertNotIn("(cd packages/zok && npm install || true)", control)


if __name__ == "__main__":
    unittest.main()
