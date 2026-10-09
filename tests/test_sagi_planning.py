import unittest

from zworkforce.sagi_planning import MissionLimits, ProposedStep, validate_plan


class SagiPlanningTests(unittest.TestCase):
    def plan(self, steps, **kw):
        return validate_plan(
            tenant_id=kw.pop("tenant_id", "tenant-a"), actor_id="actor-a",
            goal="Safely inspect a repository", proposed_steps=steps,
            limits=kw.pop("limits", MissionLimits()), **kw,
        )

    def test_valid_dag_is_deterministic_and_mutation_is_not_authority(self):
        steps = [ProposedStep("inspect", "Inspect files"), ProposedStep("fix", "Propose patch", ("inspect",), mutation=True)]
        result = self.plan(steps)
        self.assertEqual(result.digest, self.plan(steps).digest)
        self.assertTrue(result.requires_approval)
        self.assertEqual(len(result.digest), 64)

    def test_digest_binds_tenant(self):
        steps = [ProposedStep("read", "Read only")]
        self.assertNotEqual(self.plan(steps).digest, self.plan(steps, tenant_id="tenant-b").digest)

    def test_rejects_forward_edges_and_duplicates(self):
        with self.assertRaises(ValueError):
            self.plan([ProposedStep("a", "A", ("b",)), ProposedStep("b", "B")])
        with self.assertRaises(ValueError):
            self.plan([ProposedStep("a", "A"), ProposedStep("a", "A again")])

    def test_rejects_budget_and_nonfinite_cost(self):
        with self.assertRaises(ValueError):
            self.plan([ProposedStep("a", "A", estimated_cost=5.1)])
        with self.assertRaises(ValueError):
            self.plan([ProposedStep("a", "A", estimated_cost=float("nan"))])

    def test_rejects_excess_fanout(self):
        steps = [ProposedStep("a", "A")] + [ProposedStep(str(i), "child", ("a",)) for i in range(3)]
        with self.assertRaises(ValueError):
            self.plan(steps, limits=MissionLimits(max_fanout=2))

    def test_rejects_depth_and_untrusted_types(self):
        with self.assertRaises(ValueError):
            self.plan([ProposedStep("a", "A", depth=3)])
        with self.assertRaises(ValueError):
            self.plan([ProposedStep("a", "A", mutation="yes")])
        with self.assertRaises(ValueError):
            self.plan([ProposedStep("a", "A", estimated_cost=True)])

    def test_requires_identity_and_bounded_steps(self):
        with self.assertRaises(ValueError):
            self.plan([], limits=MissionLimits())
        with self.assertRaises(ValueError):
            self.plan([ProposedStep("a", "A")], tenant_id="")
        with self.assertRaises(ValueError):
            MissionLimits(max_cost=float("inf"))


if __name__ == "__main__":
    unittest.main()
