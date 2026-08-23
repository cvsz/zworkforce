import base64
import hashlib
import hmac
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.webhook_auth import WebhookVerifier


SECRETS = {
    "facebook": "facebook-secret",
    "line": "line-secret",
    "tiktok": "tiktok-secret",
    "shopee": "shopee-secret",
}


def payload(event_id: str) -> dict[str, str]:
    return {"event_id": event_id, "customer_id": f"buyer-{event_id}", "text": "สนใจวิตซีโลเอ้"}


def raw_json(value: dict[str, str]) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def signature(provider: str, body: bytes) -> str:
    digest = hmac.new(SECRETS[provider].encode("utf-8"), body, hashlib.sha256)
    if provider == "line":
        return base64.b64encode(digest.digest()).decode("ascii")
    return f"sha256={digest.hexdigest()}"


def test_verifier_accepts_native_and_normalized_provider_signatures():
    settings = Settings(
        database_path=":memory:",
        line_channel_access_token=None,
        line_channel_secret=SECRETS["line"],
        facebook_app_secret=SECRETS["facebook"],
        tiktok_webhook_secret=SECRETS["tiktok"],
        shopee_webhook_secret=SECRETS["shopee"],
    )
    verifier = WebhookVerifier(settings)

    for provider, header in (
        ("facebook", "X-Hub-Signature-256"),
        ("line", "X-Line-Signature"),
        ("tiktok", "X-UPerfect-Webhook-Signature"),
        ("shopee", "X-UPerfect-Webhook-Signature"),
    ):
        body = raw_json(payload(provider))
        assert verifier.verify(provider, body, {header: signature(provider, body)}) is True


def test_api_requires_signature_over_exact_raw_body(tmp_path: Path):
    settings = Settings(
        database_path=str(tmp_path / "signed.db"),
        line_channel_access_token=None,
        line_channel_secret=SECRETS["line"],
        facebook_app_secret=SECRETS["facebook"],
        tiktok_webhook_secret=SECRETS["tiktok"],
        shopee_webhook_secret=SECRETS["shopee"],
    )
    with TestClient(create_app(settings)) as client:
        for provider in SECRETS:
            event = payload(f"valid-{provider}")
            body = raw_json(event)
            response = client.post(
                f"/api/webhooks/{provider}",
                content=body,
                headers={"Content-Type": "application/json", "X-Line-Signature" if provider == "line" else ("X-Hub-Signature-256" if provider == "facebook" else "X-UPerfect-Webhook-Signature"): signature(provider, body)},
            )
            assert response.status_code == 200

        body = raw_json(payload("tampered"))
        valid_signature = signature("facebook", body)
        tampered = body.replace("สนใจ".encode("utf-8"), "ถามราคา".encode("utf-8"))
        response = client.post(
            "/api/webhooks/facebook",
            content=tampered,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": valid_signature},
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "WEBHOOK_SIGNATURE_INVALID"


def test_boolean_header_cannot_bypass_signature_check(client):
    response = client.post(
        "/api/webhooks/facebook",
        json=payload("boolean-bypass"),
        headers={"X-UPerfect-Webhook-Verified": "true"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "WEBHOOK_SIGNATURE_INVALID"


def test_valid_signed_webhook_remains_idempotent(tmp_path: Path):
    settings = Settings(
        database_path=str(tmp_path / "duplicate.db"),
        line_channel_access_token=None,
        facebook_app_secret=SECRETS["facebook"],
    )
    event = payload("duplicate")
    body = raw_json(event)
    headers = {"Content-Type": "application/json", "X-Hub-Signature-256": signature("facebook", body)}
    with TestClient(create_app(settings)) as client:
        first = client.post("/api/webhooks/facebook", content=body, headers=headers)
        second = client.post("/api/webhooks/facebook", content=body, headers=headers)

    assert first.status_code == 200
    assert first.json()["duplicate"] is False
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
