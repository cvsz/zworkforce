from dataclasses import replace

from app.worker import NotificationWorker


def test_configured_worker_delivers_pending_notification(notifications, settings):
    delivered = []
    notifications.enqueue("admin-line", "order confirmed")
    configured = replace(
        settings,
        line_channel_access_token="configured-token",
        line_admin_destination="admin-line",
    )

    worker = NotificationWorker(
        settings=configured,
        notifications=notifications,
        sender=lambda destination, body: delivered.append((destination, body)),
        worker_id="worker-a",
    )

    summary = worker.run_once()

    assert delivered == [("admin-line", "order confirmed")]
    assert summary.sent == 1
    assert summary.failed == 0
    assert summary.remaining == 0


def test_unconfigured_worker_is_dormant_and_does_not_call_sender(notifications, settings):
    delivered = []
    notifications.enqueue("admin-line", "order confirmed")

    worker = NotificationWorker(
        settings=settings,
        notifications=notifications,
        sender=lambda destination, body: delivered.append((destination, body)),
        worker_id="worker-a",
    )

    summary = worker.run_once()

    assert delivered == []
    assert summary.sent == 0
    assert summary.failed == 0
    assert summary.remaining == 1
