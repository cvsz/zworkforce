from decimal import Decimal
from datetime import timedelta

import pytest

from app.database import Database
from app.repositories import Repository, timestamp, utcnow


@pytest.fixture()
def repository(tmp_path):
    database = Database(str(tmp_path / "repository.db"))
    database.initialize()
    return Repository(database)


def test_product_keyword_lookup_returns_seeded_product(repository):
    matches = repository.find_keyword_matches("วิตซีโลเอ้")

    assert matches[0].id == "LOE_VITC_SERUM"
    assert matches[0].matched_alias == "วิตซีโลเอ้"


def test_conversation_creation_is_unique_for_platform_and_customer(repository):
    first = repository.get_or_create_conversation("facebook", "customer-1")
    second = repository.get_or_create_conversation("facebook", "customer-1")

    assert first.id == second.id


def test_webhook_claim_is_idempotent(repository):
    assert repository.claim_webhook("facebook", "event-1") is True
    assert repository.claim_webhook("facebook", "event-1") is False


def test_notification_failure_can_be_marked_sent(repository):
    notification_id = repository.add_notification("test", "admin-line", "body")

    repository.record_notification_failure(notification_id, "offline")
    assert repository.pending_notification_count() == 1

    repository.mark_notification_sent(notification_id)
    assert repository.pending_notification_count() == 0


def test_notification_claim_is_exclusive_until_lease_expires(repository):
    notification_id = repository.add_notification("test", "admin-line", "body")

    first = repository.claim_next_notification("worker-a", lease_seconds=60)
    second = repository.claim_next_notification("worker-b", lease_seconds=60)

    assert first["id"] == notification_id
    assert first["locked_by"] == "worker-a"
    assert second is None

    with repository.database.transaction() as connection:
        connection.execute(
            "UPDATE notification_outbox SET locked_until = ? WHERE id = ?",
            (timestamp(utcnow() - timedelta(seconds=1)), notification_id),
        )

    recovered = repository.claim_next_notification("worker-b", lease_seconds=60)
    assert recovered["id"] == notification_id
    assert recovered["locked_by"] == "worker-b"


def test_notification_failure_schedules_a_retry(repository):
    notification_id = repository.add_notification("test", "admin-line", "body")

    repository.record_notification_failure(notification_id, "offline")

    with repository.database.transaction() as connection:
        row = connection.execute(
            "SELECT status, attempts, next_attempt_at, locked_until, locked_by FROM notification_outbox WHERE id = ?",
            (notification_id,),
        ).fetchone()
    assert row["status"] == "failed"
    assert row["attempts"] == 1
    assert row["next_attempt_at"]
    assert row["locked_until"] is None
    assert row["locked_by"] is None


def test_inventory_reservation_rejects_quantity_above_available_stock(repository):
    with pytest.raises(ValueError, match="OUT_OF_STOCK"):
        repository.reserve_inventory("LOE_VITC_SERUM", 501)


def test_order_round_trip_preserves_currency_and_item(repository):
    order = repository.create_order(
        customer_name="Mali",
        status="awaiting_payment",
        total_thb=Decimal("169.00"),
        product_id="LOE_VITC_SERUM",
        quantity=2,
        unit_price_thb=Decimal("98.00"),
        conversation_id=None,
    )

    loaded = repository.get_order(order.id)

    assert loaded.id == order.id
    assert loaded.product_id == "LOE_VITC_SERUM"
    assert loaded.quantity == 2
    assert loaded.total_thb == Decimal("169.00")


def test_workspace_settings_round_trip_returns_timestamp(repository):
    repository.save_workspace_settings({"store_name": "Test Store"})

    values, updated_at = repository.load_workspace_settings()

    assert values["store_name"] == "Test Store"
    assert updated_at
