from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
GITMODULES = ROOT / ".gitmodules"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

EXPECTED_PUBLIC_SUBMODULES = {
    "https://github.com/cvsz/zksato.git",
    "https://github.com/cvsz/zttshop-php.git",
    "https://github.com/cvsz/zmovie.git",
    "https://github.com/cvsz/zok.git",
}


class PublicSubmoduleSecurityTests(unittest.TestCase):
    def test_all_submodules_use_explicit_public_https_remotes(self):
        source = GITMODULES.read_text(encoding="utf-8")
        urls = set(re.findall(r"^\\s*url\\s*=\\s*(\\S+)\\s*$", source, re.MULTILINE))

        self.assertEqual(EXPECTED_PUBLIC_SUBMODULES, urls)
        self.assertTrue(all(url.startswith("https://github.com/cvsz/") for url in urls))

    def test_pull_request_workflow_never_receives_submodule_ssh_keys(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        forbidden = (
            "ZKSATO_SUBMODULE_SSH_KEY",
            "ZTTSHOP_PHP_SUBMODULE_SSH_KEY",
            "secrets.ZKSATO_SUBMODULE_SSH_KEY",
            "secrets.ZTTSHOP_PHP_SUBMODULE_SSH_KEY",
            "IdentityFile",
            "known_hosts",
            "ssh.github.com",
            "git@github.com",
        )
        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, workflow)

        self.assertIn("permissions:\\n  contents: read", workflow)
        self.assertIn("persist-credentials: false", workflow)

    def test_public_submodule_checkout_is_anonymous_and_gitlink_pinned(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        checkout = re.search(
            r"^      - name: Checkout pinned public submodules\\n(?P<body>.*?)(?=^      - name: Verify pinned submodule revisions$)",
            workflow,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(checkout)
        self.assertNotRegex(checkout.group("body"), r"^\\s*if:", msg="public submodule checkout must run for every PR")
        self.assertIn("git submodule sync --recursive", checkout.group("body"))
        self.assertIn("git submodule update --init --recursive --depth=1", checkout.group("body"))

        verify = re.search(
            r"^      - name: Verify pinned submodule revisions\\n(?P<body>.*?)(?=^      - uses: actions/setup-python@)",
            workflow,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(verify)
        self.assertNotRegex(verify.group("body"), r"^\\s*if:", msg="gitlink verification must run for every PR")
        for path in ("packages/zksato", "packages/zttshop-php", "packages/zmovie", "packages/zok"):
            with self.subTest(path=path):
                self.assertIn(f"git -C {path} rev-parse HEAD", verify.group("body"))

    def test_untrusted_pull_requests_cannot_change_submodule_sources_or_gitlinks(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        guard = re.search(
            r"^      - name: Reject untrusted submodule changes\\n(?P<body>.*?)(?=^      - name: Checkout pinned public submodules$)",
            workflow,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(guard)
        self.assertIn(".gitmodules", guard.group("body"))
        self.assertIn("packages/zksato", guard.group("body"))
        self.assertIn("packages/zttshop-php", guard.group("body"))
        self.assertIn("packages/zmovie", guard.group("body"))
        self.assertIn("packages/zok", guard.group("body"))


if __name__ == "__main__":
    unittest.main()
