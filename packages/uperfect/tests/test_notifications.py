def test_successful_delivery_marks_event_sent_and_clears_pending(notifications):
    delivered = []
    notifications.enqueue("admin-line", "hello", event_type="order_confirmed")

    summary = notifications.deliver_pending(lambda destination, body: delivered.append((destination, body)))

    assert delivered == [("admin-line", "hello")]
    assert summary.sent == 1
    assert summary.failed == 0
    assert summary.remaining == 0
    assert notifications.list_pending() == []


def test_failed_delivery_remains_pending_and_is_retryable(notifications):
    notifications.enqueue("admin-line", "hello")

    def failing_sender(destination: str, body: str) -> None:
        raise RuntimeError("offline")

    summary = notifications.deliver_pending(failing_sender)

    assert summary.sent == 0
    assert summary.failed == 1
    assert summary.remaining == 1
    assert notifications.list_pending()[0]["status"] == "failed"


def test_delivery_claims_each_event_once_per_worker_run(notifications):
    delivered = []
    notifications.enqueue("admin-line", "first")
    notifications.enqueue("admin-line", "second")

    summary = notifications.deliver_pending(
        lambda destination, body: delivered.append((destination, body)),
        worker_id="worker-a",
    )

    assert summary.sent == 2
    assert delivered == [("admin-line", "first"), ("admin-line", "second")]
    assert notifications.pending_count() == 0
