import pytest

from app.config import Settings


def test_settings_update_persists_allowed_values_and_keeps_reference_url(services):
    before = services.workspace_settings.get()

    result = services.workspace_settings.update({"store_name": "Test Store", "assistant_tone": "warm"})

    assert result["store_name"] == "Test Store"
    assert result["assistant_tone"] == "warm"
    assert result["facebook_page_url"] == before["facebook_page_url"]
    assert services.workspace_settings.get()["store_name"] == "Test Store"


def test_settings_reject_unknown_keys_without_persisting_them(services):
    with pytest.raises(ValueError, match="Unsupported workspace setting"):
        services.workspace_settings.update({"FACEBOOK_PAGE_ACCESS_TOKEN": "secret"})


def test_runtime_settings_repr_masks_provider_secrets():
    settings = Settings(
        database_path="uperfect.db",
        line_channel_access_token="line-token-for-test",
        line_channel_secret="line-signing-secret-for-test",
        facebook_app_secret="facebook-secret-for-test",
        tiktok_app_secret="tiktok-secret-for-test",
        tiktok_refresh_token="tiktok-refresh-for-test",
        shopee_partner_key="shopee-key-for-test",
        gemini_api_key="gemini-key-for-test",
    )

    rendered = repr(settings)

    assert "line-token-for-test" not in rendered
    assert "line-signing-secret-for-test" not in rendered
    assert "facebook-secret-for-test" not in rendered
    assert "tiktok-secret-for-test" not in rendered
    assert "tiktok-refresh-for-test" not in rendered
    assert "shopee-key-for-test" not in rendered
    assert "gemini-key-for-test" not in rendered
    assert "line_channel_access_token='***'" in rendered


def test_provider_status_is_degraded_when_webhook_secret_is_missing():
    settings = Settings(
        database_path="uperfect.db",
        line_channel_access_token="line-token",
        facebook_page_access_token="facebook-token",
        facebook_verify_token="facebook-verify",
        tiktok_app_key="tiktok-app",
        tiktok_app_secret="tiktok-app-secret",
        tiktok_refresh_token="tiktok-refresh",
        shopee_partner_id="shopee-partner",
        shopee_partner_key="shopee-key",
        shopee_shop_id="shopee-shop",
    )

    assert settings.integration_status("facebook") == "degraded"
    assert settings.integration_status("tiktok") == "degraded"
    assert settings.integration_status("shopee") == "degraded"
