from decimal import Decimal
import unittest

from zworkforce.service_broker import (
    evaluate_job,
    jobs_required,
    max_acquisition_cost,
    max_supplier_cost,
)


class ServiceBrokerEconomicsTests(unittest.TestCase):
    def test_example_job_contributes_three_thousand_baht(self):
        result = evaluate_job(
            revenue=15000,
            supplier_cost=9000,
            operations_cost=1000,
            acquisition_cost=1500,
            risk_reserve=500,
        )
        self.assertEqual(result.contribution, Decimal("3000"))
        self.assertEqual(result.contribution_margin, Decimal("0.2"))
        self.assertTrue(result.profitable)

    def test_ten_three_thousand_jobs_meet_monthly_target(self):
        self.assertEqual(jobs_required(monthly_target=30000, contribution_per_job=3000), 10)

    def test_six_five_thousand_jobs_meet_monthly_target(self):
        self.assertEqual(jobs_required(monthly_target=30000, contribution_per_job=5000), 6)

    def test_max_supplier_cost_enforces_target_contribution(self):
        self.assertEqual(
            max_supplier_cost(
                revenue=15000,
                target_contribution=3000,
                acquisition_cost=1500,
                operations_cost=1000,
                risk_reserve=500,
            ),
            Decimal("9000"),
        )

    def test_max_acquisition_cost_enforces_target_contribution(self):
        self.assertEqual(
            max_acquisition_cost(
                revenue=15000,
                supplier_cost=9000,
                target_contribution=3000,
                operations_cost=1000,
                risk_reserve=500,
            ),
            Decimal("1500"),
        )

    def test_negative_input_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_job(revenue=1000, supplier_cost=-1)

    def test_positive_target_requires_positive_contribution(self):
        with self.assertRaises(ValueError):
            jobs_required(monthly_target=30000, contribution_per_job=0)


if __name__ == "__main__":
    unittest.main()
