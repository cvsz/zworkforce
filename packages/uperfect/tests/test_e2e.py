def test_customer_dialogue_to_confirmed_order_persists_outbox_event(client):
    first = client.post(
        "/api/messages",
        json={"platform": "facebook", "customer_id": "e2e-buyer", "text": "สนใจวิตซีโลเอ้"},
    )
    conversation_id = first.json()["conversation"]["id"]
    follow_up = client.post(
        "/api/messages",
        json={"platform": "facebook", "customer_id": "e2e-buyer", "text": "ขอโปร 2 ชิ้นค่ะ"},
    )
    created = client.post(
        "/api/orders",
        json={
            "product_id": "LOE_VITC_SERUM",
            "quantity": 2,
            "customer_name": "E2E Buyer",
            "conversation_id": conversation_id,
        },
    )
    order_id = created.json()["id"]
    evidence = client.post(f"/api/orders/{order_id}/payment-evidence", json={"reference": "e2e-slip-1"})
    confirmed = client.post(
        f"/api/orders/{order_id}/transition",
        json={"target": "confirmed", "actor": "e2e-admin"},
    )
    notifications = client.get("/api/notifications")
    conversation = client.get(f"/api/conversations/{conversation_id}")

    assert first.status_code == 200
    assert first.json()["active_product_id"] == "LOE_VITC_SERUM"
    assert follow_up.status_code == 200
    assert follow_up.json()["reply"]
    assert created.status_code == 201
    assert created.json()["total_thb"] == 169
    assert evidence.json()["status"] == "pending_review"
    assert confirmed.json()["status"] == "confirmed"
    assert notifications.status_code == 200
    assert notifications.json()["pending"] == 1
    assert notifications.json()["items"][0]["event_type"] == "order_confirmed"
    assert len(conversation.json()["messages"]) >= 4


def test_e2e_dashboard_reports_pending_review_and_notification_counts(client):
    created = client.post(
        "/api/orders",
        json={"product_id": "LOE_VITC_SERUM", "quantity": 1, "customer_name": "Review Buyer"},
    )
    order_id = created.json()["id"]
    client.post(f"/api/orders/{order_id}/payment-evidence", json={"reference": "review-slip"})

    dashboard = client.get("/api/dashboard")

    assert dashboard.status_code == 200
    assert dashboard.json()["pending_review"] == 1
    assert dashboard.json()["pending_notifications"] == 0
