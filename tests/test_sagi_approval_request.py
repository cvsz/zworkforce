import unittest

from zworkforce.sagi_approval_request import create_approval_request
from zworkforce.sagi_zloop_binding import PlanBinding


class SagiApprovalRequestTests(unittest.TestCase):
    def setUp(self):
        self.binding = PlanBinding(
            "loop-1", "tenant-a", "actor-a", "a" * 64, True
        )

    def request(self, **updates):
        arguments = {"binding": self.binding, "action": "execute",
                     "target": "repo:cvsz/zworkforce", "step_id": "step-1"}
        arguments.update(updates)
        return create_approval_request(**arguments)

    def test_deterministic_and_bound_to_identity_and_digest(self):
        self.assertEqual(self.request(), self.request())
        changed = PlanBinding("loop-1", "tenant-b", "actor-a", "a" * 64, True)
        self.assertNotEqual(self.request().idempotency_key,
                            self.request(binding=changed).idempotency_key)

    def test_target_action_and_plan_digest_affect_key(self):
        baseline = self.request().idempotency_key
        self.assertNotEqual(baseline, self.request(target="repo:another").idempotency_key)
        self.assertNotEqual(baseline, self.request(action="repair").idempotency_key)
        changed = PlanBinding("loop-1", "tenant-a", "actor-a", "b" * 64, True)
        self.assertNotEqual(baseline, self.request(binding=changed).idempotency_key)

    def test_no_approval_needed_is_not_granted(self):
        readonly = PlanBinding("loop-1", "tenant-a", "actor-a", "a" * 64, False)
        with self.assertRaises(ValueError):
            self.request(binding=readonly)

    def test_invalid_action_and_target_fail_closed(self):
        for change in ({"action": "delete_all"}, {"target": ""},
                       {"step_id": ""}, {"step_id": "x" * 129}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.request(**change)

    def test_digest_must_be_hex_sha256(self):
        invalid = PlanBinding("loop-1", "tenant-a", "actor-a", "invalid", True)
        with self.assertRaises(ValueError):
            self.request(binding=invalid)


if __name__ == "__main__":
    unittest.main()
