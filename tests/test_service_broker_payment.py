from decimal import Decimal
import unittest

from zworkforce.service_broker_payment import build_payment_event


class ServiceBrokerPaymentTests(unittest.TestCase):
    def test_builds_pending_deposit_without_executing_provider(self):
        event = build_payment_event(
            event_id="payment-001",
            tenant_id="zeazdev",
            job_id="job-001",
            quote_id="quote-001",
            customer_id="customer-001",
            kind="deposit",
            amount="7500",
        )

        self.assertEqual(event.amount, Decimal("7500"))
        self.assertEqual(event.currency, "THB")
        self.assertEqual(event.status, "pending")
        contract = event.to_contract()
        self.assertEqual(contract["schema_version"], "service-broker.payment.v1")
        self.assertEqual(contract["amount"], "7500")
        self.assertEqual(
            contract["idempotency_key"],
            "zeazdev:job-001:deposit:payment-001",
        )

    def test_paid_event_can_preserve_external_reference(self):
        event = build_payment_event(
            event_id="payment-002",
            tenant_id="zeazdev",
            job_id="job-001",
            quote_id="quote-001",
            customer_id="customer-001",
            kind="balance",
            amount=7500,
            status="paid",
            provider_reference="provider-event-123",
        )
        self.assertEqual(event.provider_reference, "provider-event-123")

    def test_rejects_invalid_money_and_identity(self):
        with self.assertRaises(ValueError):
            build_payment_event(
                event_id="payment-003",
                tenant_id="",
                job_id="job-001",
                quote_id="quote-001",
                customer_id="customer-001",
                kind="full",
                amount=15000,
            )
        with self.assertRaises(ValueError):
            build_payment_event(
                event_id="payment-004",
                tenant_id="zeazdev",
                job_id="job-001",
                quote_id="quote-001",
                customer_id="customer-001",
                kind="full",
                amount=-1,
            )

    def test_paid_zero_amount_is_rejected(self):
        with self.assertRaises(ValueError):
            build_payment_event(
                event_id="payment-005",
                tenant_id="zeazdev",
                job_id="job-001",
                quote_id="quote-001",
                customer_id="customer-001",
                kind="full",
                amount=0,
                status="paid",
            )


if __name__ == "__main__":
    unittest.main()
