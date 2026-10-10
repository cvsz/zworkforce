import unittest

from zworkforce.sagi_computer_use import (
    ComputerAction, prepare_computer_use_intent,
)
from zworkforce.sagi_zloop_binding import PlanBinding


class ComputerUseContractTests(unittest.TestCase):
    def setUp(self):
        self.binding = PlanBinding("loop-1", "tenant-a", "actor-a", "a" * 64, True)

    def prepare(self, **changes):
        values = dict(binding=self.binding, session_id="session-1", step_id="step-1",
                      action=ComputerAction.CLICK, target="button:save",
                      screen_evidence_digest="b" * 64)
        values.update(changes)
        return prepare_computer_use_intent(**values)

    def test_mutation_proposal_is_not_execution(self):
        proposal = self.prepare()
        self.assertTrue(proposal.requires_approval)
        self.assertEqual(proposal.action, ComputerAction.CLICK)
        self.assertEqual(self.prepare().request_digest, proposal.request_digest)

    def test_screen_evidence_and_session_change_digest(self):
        original = self.prepare().request_digest
        self.assertNotEqual(original, self.prepare(session_id="session-2").request_digest)
        self.assertNotEqual(original, self.prepare(screen_evidence_digest="c" * 64).request_digest)

    def test_readonly_plan_must_not_propose_mutation(self):
        readonly = PlanBinding("loop-1", "tenant-a", "actor-a", "a" * 64, False)
        with self.assertRaises(ValueError):
            self.prepare(binding=readonly)
        self.assertFalse(self.prepare(binding=readonly, action=ComputerAction.OBSERVE).requires_approval)

    def test_reject_invalid_scope_digest_and_action(self):
        for change in ({"target": ""}, {"step_id": ""}, {"session_id": "x" * 129},
                       {"screen_evidence_digest": "not-sha"}, {"action": "shell"},
                       {"action": ComputerAction.CLICK, "target": "x" * 1025}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.prepare(**change)

    def test_tenant_isolation_in_request_digest(self):
        other = PlanBinding("loop-1", "tenant-b", "actor-a", "a" * 64, True)
        self.assertNotEqual(self.prepare().request_digest,
                            self.prepare(binding=other).request_digest)


if __name__ == "__main__":
    unittest.main()
