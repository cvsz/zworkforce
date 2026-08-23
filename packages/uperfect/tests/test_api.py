import hashlib
import hmac
import json

from app.config import Settings
from app.main import create_app


def signed_json(payload: dict[str, str], secret: str, *, encoding: str = "hex") -> tuple[bytes, str]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256)
    signature = digest.hexdigest() if encoding == "hex" else __import__("base64").b64encode(digest.digest()).decode("ascii")
    return body, signature


def test_settings_do_not_expose_secret_values(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "not-for-output")

    settings = Settings.from_environment()

    assert settings.integration_status("line") == "configured"
    assert "not-for-output" not in repr(settings)


def test_local_ai_configuration_is_explicitly_lan_only(monkeypatch):
    monkeypatch.setenv("UPERFECT_LOCAL_AI_BASE_URL", "http://192.168.74.130:11434")
    monkeypatch.setenv("UPERFECT_LOCAL_AI_MODEL", "zCoder:latest")
    monkeypatch.setenv("UPERFECT_LOCAL_ONLY", "true")

    settings = Settings.from_environment()

    assert settings.local_only_mode is True
    assert settings.local_ai_base_url == "http://192.168.74.130:11434"
    assert settings.local_ai_model == "zCoder:latest"
    assert settings.integration_status("local_ai") == "configured"


def test_health_endpoint_reports_the_official_brand(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "brand": "U.Perfect"}


def test_products_and_integrations_are_listed_without_secrets(client):
    products = client.get("/api/products")
    integrations = client.get("/api/integrations")

    assert products.status_code == 200
    assert len(products.json()["items"]) == 2
    assert integrations.status_code == 200
    assert {item["status"] for item in integrations.json()["items"]} == {"unconfigured"}
    assert "token" not in integrations.text.casefold()
    facebook = next(item for item in integrations.json()["items"] if item["provider"] == "facebook")
    assert facebook["label_th"] == "Facebook"
    assert facebook["setup_note_en"].startswith("Configure the account")


def test_sales_assets_and_integration_guides_are_publicly_described_without_secrets(client):
    assets = client.get("/api/sales-assets")
    guides = client.get("/api/integration-guides")

    assert assets.status_code == 200
    payload = assets.json()
    assert payload["version"] == "1.0.0"
    assert "LOE_VITC_SERUM" in payload["products"]
    assert payload["products"]["LOE_VITC_SERUM"]["close_mode"] == "catalog_review"
    assert "access_token" not in assets.text.casefold()
    assert "partner_key" not in assets.text.casefold()

    assert guides.status_code == 200
    assert {item["provider"] for item in guides.json()["items"]} == {
        "facebook",
        "tiktok",
        "shopee",
        "line",
    }
    assert "API_ONBOARDING_TH.md" in guides.text
    for item in guides.json()["items"]:
        assert item["guide_th"].startswith("/guides/API_ONBOARDING_TH.md#")
        assert item["guide_en"].startswith("/guides/API_ONBOARDING_EN.md#")
        assert item["approval_th"].startswith("/guides/PROVIDER-APPROVAL-FORM_TH.md#")
        assert item["approval_en"].startswith("/guides/PROVIDER-APPROVAL-FORM_EN.md#")
        assert client.get(item["approval_th"].split("#", 1)[0]).status_code == 200
        assert client.get(item["approval_en"].split("#", 1)[0]).status_code == 200


def test_product_asset_manifest_is_served_from_local_assets(client):
    response = client.get("/assets/chatbot/asset-manifest.json")

    assert response.status_code == 200
    assert response.json()["version"] == "1.0.0"


def test_workspace_settings_are_safe_and_persisted(client):
    initial = client.get("/api/settings")

    assert initial.status_code == 200
    assert initial.json()["store_name"] == "U.Perfect"
    assert initial.json()["autobot_enabled"] is True
    assert "token" not in initial.text.casefold()

    updated = client.patch(
        "/api/settings",
        json={
            "store_name": "U.Perfect Thailand",
            "default_language": "en",
            "autobot_enabled": False,
            "human_takeover_timeout_minutes": 45,
            "n8n_auto_post_enabled": True,
        },
    )

    assert updated.status_code == 200
    assert updated.json()["store_name"] == "U.Perfect Thailand"
    assert updated.json()["default_language"] == "en"
    assert updated.json()["autobot_enabled"] is False
    assert updated.json()["human_takeover_timeout_minutes"] == 45
    assert updated.json()["n8n_auto_post_enabled"] is True
    assert client.get("/api/settings").json()["store_name"] == "U.Perfect Thailand"


def test_disabling_autobot_suppresses_automated_reply(client):
    assert client.patch("/api/settings", json={"autobot_enabled": False}).status_code == 200

    response = client.post(
        "/api/messages",
        json={"platform": "facebook", "customer_id": "buyer-settings", "text": "สวัสดี"},
    )

    assert response.status_code == 200
    assert response.json()["automated"] is False
    assert response.json()["reply"] is None


def test_invalid_order_transition_has_stable_error(client):
    response = client.post("/api/orders/missing/transition", json={"target": "fulfilled"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"


def test_message_memory_and_takeover_are_exposed(client):
    first = client.post(
        "/api/messages",
        json={"platform": "facebook", "customer_id": "buyer-1", "text": "สนใจวิตซีโลเอ้"},
    )
    conversation_id = first.json()["conversation"]["id"]
    takeover = client.post(f"/api/conversations/{conversation_id}/takeover", json={"enabled": True})
    second = client.post(
        "/api/messages",
        json={"platform": "facebook", "customer_id": "buyer-1", "text": "ราคาเท่าไร"},
    )

    assert first.status_code == 200
    assert takeover.json()["human_takeover"] is True
    assert second.json()["automated"] is False
    assert second.json()["reply"] is None


def test_unverified_webhook_has_explicit_error(client):
    response = client.post(
        "/api/webhooks/facebook",
        json={"event_id": "e-1", "customer_id": "buyer-2", "text": "สวัสดี"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "WEBHOOK_SIGNATURE_INVALID"


def test_verified_webhook_is_idempotent(client):
    payload = {"event_id": "e-2", "customer_id": "buyer-3", "text": "สนใจวิตซีโลเอ้"}
    body, signature = signed_json(payload, "facebook-secret")
    headers = {"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={signature}"}

    first = client.post("/api/webhooks/facebook", content=body, headers=headers)
    second = client.post("/api/webhooks/facebook", content=body, headers=headers)

    assert first.status_code == 200
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True


def test_dashboard_shell_is_served(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "U.Perfect Social Commerce OS" in response.text
    assert 'rel="manifest"' in response.text
    assert 'data-view="sales-assets"' in response.text
    assert "20260810-local-v7" in response.text


def test_project_manuals_and_provider_guides_are_present(client):
    for path in (
        "/guides/API_ONBOARDING_TH.md",
        "/guides/API_ONBOARDING_EN.md",
        "/guides/PROVIDER-APPROVAL-FORM_TH.md",
        "/guides/PROVIDER-APPROVAL-FORM_EN.md",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert "U.Perfect" in response.text


def test_pwa_manifest_declares_cross_platform_installability(client):
    response = client.get("/manifest.webmanifest")

    assert response.status_code == 200
    manifest = response.json()
    assert manifest["display"] == "standalone"
    assert manifest["name"].startswith("U.Perfect")
