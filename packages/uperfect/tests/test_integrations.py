from app.schemas import WebhookEvent


def test_seeded_platforms_are_not_presented_as_verified(integrations):
    statuses = integrations.statuses()
    assert {item.status for item in statuses} == {"unconfigured"}


def test_same_verified_event_is_processed_once(integrations):
    event = WebhookEvent(
        provider="facebook",
        event_id="event-1",
        customer_id="customer-1",
        text="สนใจวิตซีโลเอ้",
        verified=True,
    )

    first = integrations.accept(event)
    second = integrations.accept(event)

    assert first.accepted is True
    assert second.duplicate is True


def test_line_failure_stays_retryable(notifications):
    notifications.enqueue("admin-line", "order-created")

    def failing_sender(destination: str, body: str) -> None:
        raise RuntimeError("transport unavailable")

    summary = notifications.deliver_pending(failing_sender)
    assert summary.failed == 1
    assert notifications.pending_count() == 1
