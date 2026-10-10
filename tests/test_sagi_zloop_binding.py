import unittest

from zworkforce.sagi_planning import MissionLimits, ProposedStep, validate_plan
from zworkforce.sagi_zloop_binding import bind_plan_to_loop
from zworkforce.zloop_bridge import LoopBudget, LoopPhase, ZLoopState


class SagiZLoopBindingTests(unittest.TestCase):
    def setUp(self):
        self.state = ZLoopState(
            "loop-1", "tenant-a", "actor-a", "inspect repository",
            ["test results verified"], phase=LoopPhase.PLAN,
        )
        self.plan = validate_plan(
            tenant_id="tenant-a", actor_id="actor-a",
            goal="inspect repository",
            proposed_steps=[ProposedStep("inspect", "Review files", estimated_cost=1.0),
                            ProposedStep("update", "Propose patch", ("inspect",),
                                         mutation=True, estimated_cost=0.5)],
            limits=MissionLimits(),
        )

    def bind(self):
        return bind_plan_to_loop(
            plan=self.plan, state=self.state, loop_budget=LoopBudget()
        )

    def test_matching_plan_is_bound_without_mutating_state(self):
        old_phase = self.state.phase
        binding = self.bind()
        self.assertEqual(binding.plan_digest, self.plan.digest)
        self.assertTrue(binding.requires_approval)
        self.assertEqual(self.state.phase, old_phase)

    def test_tenant_mismatch_fails_closed(self):
        self.state.tenant_id = "tenant-b"
        with self.assertRaises(ValueError):
            self.bind()

    def test_actor_or_goal_mismatch_fails_closed(self):
        self.state.actor_id = "another-actor"
        with self.assertRaises(ValueError):
            self.bind()
        self.state.actor_id = "actor-a"
        self.state.goal = "unrelated action"
        with self.assertRaises(ValueError):
            self.bind()

    def test_cannot_bind_during_execute_or_terminal(self):
        for phase in (LoopPhase.EXECUTE, LoopPhase.HANDOFF, LoopPhase.SHIPPED):
            self.state.phase = phase
            with self.assertRaises(ValueError):
                self.bind()

    def test_remaining_budget_must_cover_estimate(self):
        self.state.cost_used = 4.0
        with self.assertRaises(ValueError):
            self.bind()
        self.state.cost_used = 3.5
        self.assertEqual(self.bind().plan_digest, self.plan.digest)

    def test_exhausted_iteration_and_invalid_cost_fail_closed(self):
        self.state.iteration = 12
        with self.assertRaises(ValueError):
            self.bind()
        self.state.iteration = 0
        self.state.cost_used = float("nan")
        with self.assertRaises(ValueError):
            self.bind()


if __name__ == "__main__":
    unittest.main()
