import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zworkforce.sagi_atomic_approval import AtomicApprovalStore
from zworkforce.sagi_computer_use import ComputerAction, prepare_computer_use_intent
from zworkforce.sagi_zloop_binding import PlanBinding


class AtomicApprovalTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = AtomicApprovalStore(Path(self.folder.name) / "claims.sqlite")
        self.now = datetime(2026, 10, 10, tzinfo=timezone.utc)
        self.intent = prepare_computer_use_intent(
            binding=PlanBinding("loop", "tenant", "actor", "a" * 64, True),
            session_id="session", step_id="step", action=ComputerAction.CLICK,
            target="button:save", screen_evidence_digest="b" * 64,
        )

    def approve(self, expiry=None):
        self.store.register_approved(
            self.intent, expires_at=expiry or self.now + timedelta(minutes=2)
        )

    def test_claim_once_and_no_replay_after_finish(self):
        self.approve()
        self.assertTrue(self.store.claim_once(self.intent, now=self.now))
        self.assertFalse(self.store.claim_once(self.intent, now=self.now))
        self.assertTrue(self.store.finish(self.intent, result_digest="c" * 64, success=True))
        self.assertFalse(self.store.claim_once(self.intent, now=self.now))
        self.assertEqual(self.store.get_state(self.intent.request_digest), "completed")

    def test_concurrent_claim_has_single_winner(self):
        self.approve()
        results = []
        lock = threading.Lock()
        def attempt():
            won = self.store.claim_once(self.intent, now=self.now)
            with lock:
                results.append(won)
        threads = [threading.Thread(target=attempt) for _ in range(8)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(sum(results), 1)

    def test_expired_approval_rejected(self):
        self.approve(self.now)
        self.assertFalse(self.store.claim_once(self.intent, now=self.now))

    def test_duplicate_approval_cannot_reset_consumed_state(self):
        self.approve()
        self.assertTrue(self.store.claim_once(self.intent, now=self.now))
        with self.assertRaises(Exception):
            self.approve()
        self.assertFalse(self.store.claim_once(self.intent, now=self.now))

    def test_unknown_or_failed_action_never_replays(self):
        self.assertFalse(self.store.claim_once(self.intent, now=self.now))
        self.approve()
        self.assertTrue(self.store.claim_once(self.intent, now=self.now))
        self.assertTrue(self.store.finish(self.intent, result_digest="c" * 64, success=False))
        self.assertFalse(self.store.claim_once(self.intent, now=self.now))


if __name__ == "__main__":
    unittest.main()
