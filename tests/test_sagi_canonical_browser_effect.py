import unittest

from tests.common import stack
from zworkforce.sagi_canonical_browser_effect import CanonicalComputerEffect
from zworkforce.sagi_computer_use import ComputerAction, prepare_computer_use_intent
from zworkforce.sagi_zloop_binding import PlanBinding


class CanonicalBrowserEffectTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.settings, self.db, self.provider, self.engine, self.auth = stack()
        self.addCleanup(self.engine.shutdown)
        self.addCleanup(self.temp.cleanup)
        self.adapter = CanonicalComputerEffect(self.db)
        self.intent = prepare_computer_use_intent(
            binding=PlanBinding("loop", "default", "requester", "a" * 64, True),
            session_id="session", step_id="step", action=ComputerAction.CLICK,
            target="button:save", screen_evidence_digest="b" * 64,
        )

    def task(self, approved=True):
        task, _ = self.engine.submit(
            "default", "software-engineer", "approved browser effect",
            actor="requester", mutating=True, max_attempts=1,
        )
        if approved:
            self.db.approval_decision("default", task["id"], "independent-reviewer", "approve")
        return task["id"]

    def test_canonical_claim_and_replay_denial(self):
        task_id = self.task()
        effect = self.adapter.claim(intent=self.intent, approval_task_id=task_id)
        self.assertEqual(effect["status"], "executing")
        with self.assertRaises(PermissionError):
            self.adapter.claim(intent=self.intent, approval_task_id=task_id)
        result = self.adapter.finish(
            intent=self.intent, effect_id=effect["id"], status="succeeded",
            result_sha256="c" * 64,
        )
        self.assertEqual(result["status"], "succeeded")

    def test_unapproved_task_denied(self):
        with self.assertRaises(ValueError):
            self.adapter.claim(intent=self.intent, approval_task_id=self.task(False))

    def test_wrong_tenant_denied(self):
        self.db.ensure_tenant("other", "Other")
        other = prepare_computer_use_intent(
            binding=PlanBinding("loop", "other", "requester", "a" * 64, True),
            session_id="session", step_id="step", action=ComputerAction.CLICK,
            target="button:save", screen_evidence_digest="b" * 64,
        )
        with self.assertRaises(ValueError):
            self.adapter.claim(intent=other, approval_task_id=self.task())

    def test_observation_cannot_consume_mutation_approval(self):
        obs = prepare_computer_use_intent(
            binding=PlanBinding("loop", "default", "requester", "a" * 64, False),
            session_id="session", step_id="step", action=ComputerAction.OBSERVE,
            target="https://example.com", screen_evidence_digest="b" * 64,
        )
        with self.assertRaises(PermissionError):
            self.adapter.claim(intent=obs, approval_task_id=self.task())


if __name__ == "__main__":
    unittest.main()
