import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from zworkforce.sagi_browser_runtime import BrowserPolicy
from zworkforce.sagi_computer_dispatch import observe_approved_page
from zworkforce.sagi_computer_session import SessionSnapshot
from zworkforce.sagi_computer_use import ComputerAction, prepare_computer_use_intent
from zworkforce.sagi_zloop_binding import PlanBinding


class Sessions:
    def __init__(self, session): self.session = session
    def load_session(self, _): return self.session


class Approvals:
    def load_approval(self, _): return None


class ComputerDispatchTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 10, tzinfo=timezone.utc)
        self.binding = PlanBinding("loop", "tenant", "actor", "a" * 64, True)
        self.session = SessionSnapshot("session", "tenant", "actor",
            self.now + timedelta(minutes=5), False, False, True)
        self.url = "https://example.com/page"
        self.policy = BrowserPolicy(frozenset({"https://example.com"}))

    def intent(self, action=ComputerAction.OBSERVE, target=None):
        return prepare_computer_use_intent(
            binding=self.binding, session_id="session", step_id="step",
            action=action, target=target or self.url,
            screen_evidence_digest="b" * 64,
        )

    def call(self, intent=None, stopped=False):
        return observe_approved_page(
            intent=intent or self.intent(), policy=self.policy, url=self.url,
            sessions=Sessions(self.session), approvals=Approvals(), now=self.now,
            emergency_stop=lambda: stopped,
        )

    @patch("zworkforce.sagi_computer_dispatch.run_browser_action", return_value=b"PNG")
    def test_observation_uses_canonical_session_preflight(self, run):
        self.assertEqual(self.call(), b"PNG")
        self.assertTrue(run.call_args.kwargs["authorized"](self.intent()))

    @patch("zworkforce.sagi_computer_dispatch.run_browser_action")
    def test_mutation_is_denied_before_launch(self, run):
        with self.assertRaises(PermissionError):
            self.call(self.intent(ComputerAction.CLICK))
        run.assert_not_called()

    @patch("zworkforce.sagi_computer_dispatch.run_browser_action")
    def test_target_substitution_denied(self, run):
        with self.assertRaises(PermissionError):
            self.call(self.intent(target="https://example.com/other"))
        run.assert_not_called()

    @patch("zworkforce.sagi_computer_dispatch.run_browser_action")
    def test_emergency_stop_denies_before_launch(self, run):
        with self.assertRaises(PermissionError):
            self.call(stopped=True)
        run.assert_not_called()

    @patch("zworkforce.sagi_computer_dispatch.run_browser_action")
    def test_revoked_session_denies_before_launch(self, run):
        self.session = SessionSnapshot("session", "tenant", "actor",
            self.now + timedelta(minutes=5), True, False, True)
        with self.assertRaises(PermissionError):
            self.call()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
