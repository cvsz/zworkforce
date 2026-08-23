import pytest

from app.schemas import InvalidTransition


def test_serum_bundle_uses_merchant_promotion(orders):
    order = orders.create_draft(product_id="LOE_VITC_SERUM", quantity=2, customer_name="Mali")

    assert order.total_thb == 169
    assert order.status == "awaiting_payment"


def test_price_missing_product_cannot_create_an_order(orders):
    with pytest.raises(ValueError, match="PRICE_UNAVAILABLE"):
        orders.create_draft(product_id="MALA_CHILI_OIL", quantity=1, customer_name="Mali")


def test_payment_evidence_requires_review_before_confirmation(orders):
    order = orders.create_draft(product_id="LOE_VITC_SERUM", quantity=1, customer_name="Mali")
    reviewed = orders.submit_payment_evidence(order.id, "slip-reference")

    assert reviewed.status == "pending_review"
    with pytest.raises(InvalidTransition):
        orders.transition(order.id, "fulfilled", actor="admin")
