"""Provider-neutral payment boundary for ZeaZ service-broker jobs.

This module only builds deterministic payment instructions/events. It does not
call a payment provider, capture funds, store credentials, or mutate accounting
state. Provider execution belongs behind an explicitly configured payment
adapter and settlement remains owned by the ERP/accounting boundary.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Literal


MoneyLike = Decimal | int | str
PaymentKind = Literal["deposit", "balance", "full"]
PaymentStatus = Literal["pending", "authorized", "paid", "failed", "cancelled", "refunded"]


def _money(value: MoneyLike, *, name: str) -> Decimal:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"{name} must be a finite non-negative amount")
    return amount


@dataclass(frozen=True, slots=True)
class ServiceBrokerPayment:
    event_id: str
    tenant_id: str
    job_id: str
    quote_id: str
    customer_id: str
    kind: PaymentKind
    amount: Decimal
    currency: str
    status: PaymentStatus
    provider_reference: str | None = None

    @property
    def idempotency_key(self) -> str:
        return f"{self.tenant_id}:{self.job_id}:{self.kind}:{self.event_id}"

    def to_contract(self) -> dict[str, object]:
        payload = asdict(self)
        payload["schema_version"] = "service-broker.payment.v1"
        payload["amount"] = str(self.amount)
        payload["idempotency_key"] = self.idempotency_key
        return payload


def build_payment_event(
    *,
    event_id: str,
    tenant_id: str,
    job_id: str,
    quote_id: str,
    customer_id: str,
    kind: PaymentKind,
    amount: MoneyLike,
    status: PaymentStatus = "pending",
    currency: str = "THB",
    provider_reference: str | None = None,
) -> ServiceBrokerPayment:
    """Validate and construct one payment lifecycle event without executing it."""

    required = {
        "event_id": event_id,
        "tenant_id": tenant_id,
        "job_id": job_id,
        "quote_id": quote_id,
        "customer_id": customer_id,
    }
    for name, value in required.items():
        if not value or not value.strip():
            raise ValueError(f"{name} is required")

    normalized_currency = currency.strip().upper()
    if len(normalized_currency) != 3 or not normalized_currency.isalpha():
        raise ValueError("currency must be a 3-letter ISO currency code")

    normalized_amount = _money(amount, name="amount")
    if normalized_amount == 0 and status in {"authorized", "paid"}:
        raise ValueError("authorized or paid payment must have a positive amount")

    return ServiceBrokerPayment(
        event_id=event_id.strip(),
        tenant_id=tenant_id.strip(),
        job_id=job_id.strip(),
        quote_id=quote_id.strip(),
        customer_id=customer_id.strip(),
        kind=kind,
        amount=normalized_amount,
        currency=normalized_currency,
        status=status,
        provider_reference=provider_reference.strip() if provider_reference else None,
    )
