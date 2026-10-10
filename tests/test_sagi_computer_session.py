import unittest
from datetime import datetime, timedelta, timezone

from zworkforce.sagi_computer_session import (
    ApprovalSnapshot, SessionSnapshot, verify_computer_use,
)
from zworkforce.sagi_computer_use import (
    ComputerAction, prepare_computer_use_intent,
)
from zworkforce.sagi_zloop_binding import PlanBinding


class Store:
    def __init__(self, value): self.value = value
    def load_session(self, _): return self.value
    def load_approval(self, _): return self.value


class ComputerSessionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 10, tzinfo=timezone.utc)
        binding = PlanBinding("loop", "tenant", "actor", "a" * 64, True)
        self.intent = prepare_computer_use_intent(
            binding=binding, session_id="session", step_id="step",
            action=ComputerAction.CLICK, target="button",
            screen_evidence_digest="b" * 64,
        )
        self.session = SessionSnapshot(
            "session", "tenant", "actor", self.now + timedelta(minutes=5),
            revoked=False, stopped=False, permitted=True,
        )
        self.approval = ApprovalSnapshot(
            "tenant", "actor", "session", self.intent.request_digest,
            self.intent.plan_digest, self.now + timedelta(minutes=1),
            approved=True, consumed=False,
        )

    def check(self, *, session=None, approval=None, stop=False, intent=None):
        return verify_computer_use(
            intent=intent or self.intent,
            sessions=Store(self.session if session is None else session),
            approvals=Store(self.approval if approval is None else approval),
            now=self.now, emergency_stop=lambda: stop,
        )

    def test_valid_preflight_is_not_execution(self):
        self.assertTrue(self.check())

    def test_emergency_stop_fails_closed(self):
        with self.assertRaises(PermissionError): self.check(stop=True)

    def test_revoked_expired_and_other_tenant_fail(self):
        for session in (
            SessionSnapshot("session", "tenant", "actor", self.now, False, False, True),
            SessionSnapshot("session", "tenant", "actor", self.now + timedelta(minutes=5), True, False, True),
            SessionSnapshot("session", "other", "actor", self.now + timedelta(minutes=5), False, False, True),
        ):
            with self.subTest(session=session), self.assertRaises(PermissionError):
                self.check(session=session)

    def test_replayed_or_mismatched_approval_denied(self):
        for approval in (
            ApprovalSnapshot("tenant", "actor", "session", self.intent.request_digest,
                             self.intent.plan_digest, self.now, True, False),
            ApprovalSnapshot("tenant", "actor", "session", self.intent.request_digest,
                             self.intent.plan_digest, self.now + timedelta(minutes=2), True, True),
            ApprovalSnapshot("tenant", "actor", "session", "c" * 64,
                             self.intent.plan_digest, self.now + timedelta(minutes=2), True, False),
        ):
            with self.subTest(approval=approval), self.assertRaises(PermissionError):
                self.check(approval=approval)

    def test_observation_uses_session_but_no_mutation_approval(self):
        binding = PlanBinding("loop", "tenant", "actor", "a" * 64, False)
        observe = prepare_computer_use_intent(
            binding=binding, session_id="session", step_id="step",
            action=ComputerAction.OBSERVE, target="https://example.com",
            screen_evidence_digest="b" * 64,
        )
        self.assertTrue(self.check(intent=observe, approval=Store(None)))
        with self.assertRaises(PermissionError):
            self.check(intent=observe, stop=True)


if __name__ == "__main__":
    unittest.main()
