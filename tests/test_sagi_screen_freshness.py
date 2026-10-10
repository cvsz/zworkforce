import unittest
from datetime import datetime, timedelta, timezone

from zworkforce.sagi_screen_freshness import TrustedScreenSnapshot, require_fresh_screen
from zworkforce.sagi_computer_use import ComputerAction, prepare_computer_use_intent
from zworkforce.sagi_zloop_binding import PlanBinding


class ScreenFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 10, tzinfo=timezone.utc)
        self.intent = prepare_computer_use_intent(
            binding=PlanBinding("loop", "tenant", "actor", "a" * 64, True),
            session_id="session", step_id="step", action=ComputerAction.CLICK,
            target="button:save", screen_evidence_digest="b" * 64,
        )
        self.snapshot = TrustedScreenSnapshot(
            "tenant", "actor", "session", "b" * 64, self.now, 2
        )

    def verify(self, snapshot=None, generation=2):
        require_fresh_screen(self.intent, snapshot or self.snapshot,
                             now=self.now, expected_generation=generation)

    def test_matching_fresh_snapshot(self):
        self.verify()

    def test_mismatched_session_denied(self):
        with self.assertRaises(PermissionError):
            self.verify(TrustedScreenSnapshot("tenant", "actor", "other", "b" * 64, self.now, 2))

    def test_stale_digest_or_generation_denied(self):
        with self.assertRaises(PermissionError):
            self.verify(TrustedScreenSnapshot("tenant", "actor", "session", "c" * 64, self.now, 2))
        with self.assertRaises(PermissionError):
            self.verify(generation=3)

    def test_old_and_future_evidence_denied(self):
        for delta in (-10, 1):
            snapshot = TrustedScreenSnapshot("tenant", "actor", "session", "b" * 64,
                                             self.now + timedelta(seconds=delta), 2)
            with self.subTest(delta=delta), self.assertRaises(PermissionError):
                self.verify(snapshot)


if __name__ == "__main__":
    unittest.main()
