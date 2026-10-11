import unittest

from zworkforce.sagi_computer_use import (
    ComputerAction, prepare_computer_use_intent,
)
from zworkforce.sagi_zloop_binding import PlanBinding
from zworkforce.sagi_planning import MissionLimits, ProposedStep, validate_plan


class ComputerUseContractTests(unittest.TestCase):
    def setUp(self):
        self.plan = validate_plan(
            tenant_id="tenant-a", actor_id="actor-a", goal="test",
            proposed_steps=[ProposedStep("step-1", "save", mutation=True),
                            ProposedStep("read-1", "read", mutation=False)],
            limits=MissionLimits(),
        )
        self.binding = PlanBinding("loop-1", "tenant-a", "actor-a", self.plan.digest, True)

    def prepare(self, **changes):
        values = dict(binding=self.binding, plan=self.plan, session_id="session-1", step_id="step-1",
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
        self.assertFalse(self.prepare(binding=readonly, plan=None, action=ComputerAction.OBSERVE).requires_approval)

    def test_step_scope_rejects_unknown_and_readonly_mutation(self):
        for step_id in ("unknown", "read-1"):
            with self.subTest(step_id=step_id), self.assertRaises(ValueError):
                self.prepare(step_id=step_id)
        with self.assertRaises(ValueError):
            self.prepare(plan=None)

    def test_action_parameters_are_digested_and_bounded(self):
        first = self.prepare(action=ComputerAction.TYPE, text="hello").request_digest
        second = self.prepare(action=ComputerAction.TYPE, text="world").request_digest
        self.assertNotEqual(first, second)
        self.assertNotEqual(
            self.prepare(action=ComputerAction.SCROLL, scroll_delta=10).request_digest,
            self.prepare(action=ComputerAction.SCROLL, scroll_delta=20).request_digest)
        self.assertNotEqual(
            self.prepare(action=ComputerAction.KEY, key="Enter").request_digest,
            self.prepare(action=ComputerAction.KEY, key="Escape").request_digest)
        for changes in (dict(action=ComputerAction.TYPE, text=""),
                        dict(action=ComputerAction.TYPE, text="x" * 4097),
                        dict(action=ComputerAction.SCROLL, scroll_delta=0),
                        dict(action=ComputerAction.KEY, key=""),
                        dict(action=ComputerAction.CLICK, text="surprise")):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.prepare(**changes)

    def test_reject_invalid_scope_digest_and_action(self):
        for change in ({"target": ""}, {"step_id": ""}, {"session_id": "x" * 129},
                       {"screen_evidence_digest": "not-sha"}, {"action": "shell"},
                       {"action": ComputerAction.CLICK, "target": "x" * 1025}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.prepare(**change)

    def test_tenant_isolation_in_request_digest(self):
        other = PlanBinding("loop-1", "tenant-b", "actor-a", "a" * 64, True)
        self.assertNotEqual(self.prepare().request_digest,
                            self.prepare(binding=other, plan=None, action=ComputerAction.OBSERVE).request_digest)


if __name__ == "__main__":
    unittest.main()
