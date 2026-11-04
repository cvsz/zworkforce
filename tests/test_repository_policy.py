from __future__ import annotations

import json
import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RULESET = ROOT / ".github" / "rulesets" / "main.json"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"
CI = ROOT / ".github" / "workflows" / "ci.yml"
GITMODULES = ROOT / ".gitmodules"
CONTROL = ROOT / "control.sh"
DEPENDENCY_REVIEW = ROOT / ".github" / "workflows" / "dependency-review.yml"
WINDOWS = ROOT / ".github" / "workflows" / "windows-client.yml"
OPEN_WEBUI_COMPOSE = ROOT / "compose.open-webui.yml"
CADDYFILE = ROOT / "deploy" / "caddy" / "Caddyfile"
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

    def test_contributing_documents_desired_and_effective_review_policy(self):
        contributing = CONTRIBUTING.read_text(encoding="utf-8")
        for phrase in (
            "one independent approving review",
            "CODEOWNERS review",
            "approval after the latest push",
            "server-side ruleset",
            "NOT ENFORCED",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, contributing)

        self.assertNotIn(
            "approval count is `0` to avoid making self-authored",
            contributing,
        )

    def test_security_sensitive_paths_require_independent_codeowner(self):
        owners = {}
        for raw_line in CODEOWNERS.read_text(encoding="utf-8").splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            path, *reviewers = line.split()
            owners[path] = reviewers

        self.assertEqual(["@cvsz", "@policedbc"], owners.get("*"))
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
        expected_urls = {
            "https://github.com/cvsz/zksato.git",
            "https://github.com/cvsz/zttshop-php.git",
            "https://github.com/cvsz/zmovie.git",
            "https://github.com/cvsz/zok.git",
        }
        urls = set(re.findall(r"^\s*url\s*=\s*(\S+)\s*$", gitmodules, re.MULTILINE))
        self.assertEqual(expected_urls, urls)

        ci = CI.read_text(encoding="utf-8")
        self.assertIn("submodule-validation:", ci)
        self.assertIn("needs: submodule-validation", ci)
        self.assertIn("git submodule update --init --recursive --depth=1", ci)
        self.assertIn("python -m pip install --upgrade pip 'setuptools>=83.0.0'", ci)
        self.assertIn("Checkout pinned public submodules", ci)
        self.assertIn("Verify pinned submodule revisions", ci)
        for marker in (
            "ZKSATO_SUBMODULE_SSH_KEY",
            "ZTTSHOP_PHP_SUBMODULE_SSH_KEY",
            "git@github.com",
            "IdentityFile",
            "ssh.github.com",
            "~/.ssh/known_hosts",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, ci)
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


    def test_open_webui_customer_boundary_is_fail_closed(self):
        compose = OPEN_WEBUI_COMPOSE.read_text(encoding="utf-8")
        required_settings = (
            '"127.0.0.1:${OPEN_WEBUI_PORT:-3080}:8080"',
            'WEBUI_AUTH: "true"',
            'ENABLE_SIGNUP: "false"',
            'DEFAULT_USER_ROLE: "pending"',
            'ENABLE_CODE_EXECUTION: "false"',
            'ENABLE_HTML_PREVIEW: "false"',
            'ENABLE_ARTIFACTS: "false"',
            'ENABLE_FUNCTIONS: "false"',
            'ENABLE_OPENAPI: "false"',
        )
        for setting in required_settings:
            with self.subTest(setting=setting):
                self.assertIn(setting, compose)

        self.assertIn(
            'WEBUI_SECRET_KEY: "${WEBUI_SECRET_KEY:?WEBUI_SECRET_KEY must be set}"',
            compose,
        )
        self.assertIn(
            'OPENAI_API_KEY: "${OPEN_WEBUI_PROVIDER_API_KEY:?OPEN_WEBUI_PROVIDER_API_KEY must be set}"',
            compose,
        )
        self.assertNotIn('ENABLE_SIGNUP: "true"', compose)
        self.assertNotIn('DEFAULT_USER_ROLE: "admin"', compose)
        self.assertNotIn("zwf-openwebui-secret-key", compose)

        caddy = CADDYFILE.read_text(encoding="utf-8")
        chat_route = caddy.split("http://chat.zeaz.dev:8080", 1)[1].split(chr(10) + "}", 1)[0]
        self.assertIn("bind 127.0.0.1", chat_route)
        self.assertIn("reverse_proxy 127.0.0.1:3080", chat_route)

    def test_kubernetes_manifests_have_unique_resource_identities(self):
        k8s_base = ROOT / "infrastructure" / "kubernetes" / "base"
        for manifest_name in ("deployments.yaml", "services.yaml", "poddisruptionbudgets.yaml"):
            manifest_path = k8s_base / manifest_name
            raw = manifest_path.read_text(encoding="utf-8")
            docs = [doc.strip() for doc in raw.split("\n---") if doc.strip()]
            seen: set[tuple[str, str, str]] = set()
            for doc in docs:
                kind_match = re.search(r"^kind:\s*(\S+)", doc, re.MULTILINE)
                name_match = re.search(r"^\s*name:\s*(\S+)", doc, re.MULTILINE)
                ns_match = re.search(r"^\s*namespace:\s*(\S+)", doc, re.MULTILINE)
                if not kind_match or not name_match:
                    continue
                identity = (
                    kind_match.group(1),
                    ns_match.group(1) if ns_match else "default",
                    name_match.group(1),
                )
                self.assertNotIn(
                    identity,
                    seen,
                    f"Duplicate Kubernetes resource identity {identity} in {manifest_name}",
                )
                seen.add(identity)


if __name__ == "__main__":
    unittest.main()
