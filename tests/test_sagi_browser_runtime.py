import unittest

from zworkforce.sagi_browser_runtime import (
    BrowserPolicy, run_browser_action, validate_navigation,
)
from zworkforce.sagi_computer_use import (
    ComputerAction, prepare_computer_use_intent,
)
from zworkforce.sagi_zloop_binding import PlanBinding


class BrowserRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.policy = BrowserPolicy(frozenset({"https://example.com"}))
        binding = PlanBinding("loop-1", "tenant-a", "actor-a", "a" * 64, True)
        self.observe = prepare_computer_use_intent(
            binding=binding, session_id="s1", step_id="a",
            action=ComputerAction.OBSERVE, target="https://example.com",
            screen_evidence_digest="b" * 64,
        )
        self.click = prepare_computer_use_intent(
            binding=binding, session_id="s1", step_id="a",
            action=ComputerAction.CLICK, target="button",
            screen_evidence_digest="b" * 64,
        )

    def test_denies_unapproved_observation_before_importing_playwright(self):
        with self.assertRaises(PermissionError):
            run_browser_action(intent=self.observe, policy=self.policy,
                               url="https://example.com", authorized=lambda _: False)

    def test_denies_interactive_actions(self):
        with self.assertRaises(PermissionError):
            run_browser_action(intent=self.click, policy=self.policy,
                               url="https://example.com", authorized=lambda _: True)

    def test_exact_origin_and_https_are_required(self):
        validate_navigation("https://example.com/page", self.policy)
        for url in ("http://example.com", "https://example.com.evil.org",
                    "https://example.com:443", "https://user@example.com",
                    "https://127.0.0.1", "file:///etc/passwd"):
            with self.subTest(url=url), self.assertRaises(PermissionError):
                validate_navigation(url, self.policy)

    def test_cannot_allow_ip_localhost_or_bad_origin(self):
        for origin in ("http://example.com", "https://localhost",
                       "https://127.0.0.1", "https://example.com/path"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                BrowserPolicy(frozenset({origin}))

    def test_invalid_timeout(self):
        with self.assertRaises(ValueError):
            BrowserPolicy(frozenset({"https://example.com"}), timeout_ms=0)


if __name__ == "__main__":
    unittest.main()
