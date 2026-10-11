import unittest

from zworkforce.sagi_worker_fencing import ExecutionLease, require_live_fence


class Store:
    def __init__(self, lease): self.lease = lease
    def load_execution_lease(self, tenant_id, effect_id): return self.lease


class WorkerFenceTests(unittest.TestCase):
    def setUp(self):
        self.lease = ExecutionLease("tenant", "effect", "worker-a", 7, True)

    def verify(self, *, lease=None, **changes):
        fields = dict(tenant_id="tenant", effect_id="effect",
                      worker_id="worker-a", generation=7,
                      authority=Store(self.lease if lease is None else lease))
        fields.update(changes)
        return require_live_fence(**fields)

    def test_active_exact_generation(self):
        self.assertIsNone(self.verify())

    def test_stale_or_future_generations_rejected(self):
        for generation in (6, 8, 0, True):
            with self.subTest(generation=generation), self.assertRaises(PermissionError):
                self.verify(generation=generation)

    def test_replaced_revoked_or_cross_tenant_lease_rejected(self):
        for lease in (
            ExecutionLease("tenant", "effect", "worker-b", 8, True),
            ExecutionLease("tenant", "effect", "worker-a", 7, False),
            ExecutionLease("other", "effect", "worker-a", 7, True),
        ):
            with self.subTest(lease=lease), self.assertRaises(PermissionError):
                self.verify(lease=lease)

    def test_missing_lease_rejected(self):
        with self.assertRaises(PermissionError):
            self.verify(authority=Store(None))

    def test_worker_impersonation_rejected(self):
        with self.assertRaises(PermissionError):
            self.verify(worker_id="worker-b")


if __name__ == "__main__":
    unittest.main()
