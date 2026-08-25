import unittest

from zworkforce.zloop_bridge import (
    LoopBudget,
    LoopPhase,
    ZLoopCoordinator,
    ZLoopState,
    stable_idempotency_key,
)


class StateStore:
    def __init__(self): self.states = []
    def save_zloop_state(self, state): self.states.append(state.phase)


class Approval:
    def __init__(self, allowed=True): self.allowed = allowed; self.calls = []
    def authorize_zloop_mutation(self, **kwargs): self.calls.append(kwargs); return self.allowed


class Dispatcher:
    def __init__(self, blocking=False): self.calls = []; self.blocking = blocking
    def dispatch_zloop_step(self, **kwargs):
        self.calls.append(kwargs)
        return {"tokens": 2, "cost": 0.01, "evidence": ["step"], "blocking_findings": self.blocking}


class Verifier:
    def __init__(self, verdict="PASS"): self.verdict = verdict
    def verify_zloop_result(self, **kwargs): return {"verdict": self.verdict, "evidence": ["verify"]}


class Audit:
    def __init__(self): self.events = []
    def record_zloop_event(self, event): self.events.append(event)


def coordinator(*, allowed=True, verdict="PASS", blocking=False):
    return ZLoopCoordinator(
        state_authority=StateStore(),
        approval_authority=Approval(allowed),
        dispatcher=Dispatcher(blocking),
        verifier=Verifier(verdict),
        audit=Audit(),
    )


class ZLoopBridgeTests(unittest.TestCase):
    def state(self, phase=LoopPhase.DISCOVER):
        return ZLoopState("loop-1", "tenant-a", "actor-a", "goal", ["tests pass"], phase=phase)

    def test_idempotency_key_is_stable_and_tenant_bound(self):
        state = self.state(LoopPhase.EXECUTE)
        first = stable_idempotency_key(state, state.phase, state.goal)
        second = stable_idempotency_key(state, state.phase, state.goal)
        self.assertEqual(first, second)
        state.tenant_id = "tenant-b"
        self.assertNotEqual(first, stable_idempotency_key(state, state.phase, state.goal))

    def test_execute_requires_existing_approval_authority(self):
        c = coordinator(allowed=False)
        state = c.advance(self.state(LoopPhase.EXECUTE), LoopBudget())
        self.assertEqual(state.phase, LoopPhase.HANDOFF)
        self.assertIn("mutation_not_authorized", state.blockers)
        self.assertEqual(len(c.dispatcher.calls), 0)

    def test_inconclusive_verification_fails_closed(self):
        c = coordinator(verdict="INCONCLUSIVE")
        state = c.advance(self.state(LoopPhase.VERIFY), LoopBudget())
        self.assertEqual(state.phase, LoopPhase.HANDOFF)
        self.assertIn("verification_inconclusive", state.blockers)

    def test_happy_path_ships_after_independent_verification_and_review(self):
        c = coordinator()
        state = self.state()
        for _ in range(5):
            state = c.advance(state, LoopBudget())
        self.assertEqual(state.phase, LoopPhase.SHIPPED)
        self.assertGreater(len(state.evidence), 0)

    def test_budget_exhaustion_handoffs_before_dispatch(self):
        c = coordinator()
        state = self.state(LoopPhase.PLAN)
        state.iteration = 2
        result = c.advance(state, LoopBudget(max_iterations=2))
        self.assertEqual(result.phase, LoopPhase.HANDOFF)
        self.assertEqual(len(c.dispatcher.calls), 0)

    def test_tenant_and_actor_are_required(self):
        c = coordinator()
        state = self.state()
        state.tenant_id = ""
        with self.assertRaises(ValueError):
            c.advance(state, LoopBudget())


if __name__ == "__main__":
    unittest.main()
