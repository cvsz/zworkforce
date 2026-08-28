import base64
import hashlib
import hmac
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import SecretStr
from zeaz_enterprise.webhooks import (
    AnthropicWebhookVerifier,
    SQLiteWebhookReplayStore,
    WebhookVerificationError,
)

NOW = 1_785_024_000
KEY_BYTES = bytes(range(32))
SECRET = SecretStr("whsec_" + base64.b64encode(KEY_BYTES).decode())


def body(event_id: str = "event_1", **data_changes) -> bytes:
    data = {
        "type": "session.status_idled",
        "id": "session_1",
        "organization_id": "org_1",
        "workspace_id": "workspace_1",
    }
    data.update(data_changes)
    return json.dumps(
        {
            "type": "event",
            "id": event_id,
            "created_at": "2026-07-26T00:00:00Z",
            "data": data,
        },
        separators=(",", ":"),
    ).encode()


def headers(payload: bytes, *, event_id: str = "event_1", timestamp: int = NOW) -> dict:
    signed = f"{event_id}.{timestamp}.".encode() + payload
    signature = base64.b64encode(
        hmac.new(KEY_BYTES, signed, hashlib.sha256).digest()
    ).decode()
    return {
        "Webhook-Id": event_id,
        "Webhook-Timestamp": str(timestamp),
        "Webhook-Signature": f"v1,{signature}",
    }


def verifier(path: Path, **changes) -> AnthropicWebhookVerifier:
    values = {
        "signing_secret": SECRET,
        "replay_store": SQLiteWebhookReplayStore(path),
        "clock": lambda: NOW,
    }
    values.update(changes)
    return AnthropicWebhookVerifier(**values)


def test_valid_raw_body_signature_is_verified_and_normalized(tmp_path: Path) -> None:
    payload = body(vault_id="vault_1")
    checker = verifier(tmp_path / "replay.sqlite")
    result = checker.verify(payload, headers(payload))
    assert result.duplicate is False
    assert result.event.data.type == "session.status_idled"
    assert result.event.data.details == {"vault_id": "vault_1"}
    assert SECRET.get_secret_value() not in repr(result)
    assert repr(KEY_BYTES) not in repr(vars(checker))


def test_same_event_id_is_durable_duplicate_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "replay.sqlite"
    payload = body()
    assert verifier(path).verify(payload, headers(payload)).duplicate is False
    assert verifier(path).verify(payload, headers(payload)).duplicate is True

    connection = sqlite3.connect(path)
    columns = [row[1] for row in connection.execute("PRAGMA table_info(webhook_events)")]
    assert columns == ["event_id", "received_at"]
    assert payload not in path.read_bytes()
    connection.close()


def test_concurrent_delivery_claim_is_atomic(tmp_path: Path) -> None:
    payload = body()
    signed_headers = headers(payload)
    checker = verifier(tmp_path / "concurrent.sqlite")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _: checker.verify(payload, signed_headers), range(20))
        )
    assert sum(not result.duplicate for result in results) == 1


def test_database_is_private_and_symlink_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "replay.sqlite"
    SQLiteWebhookReplayStore(path)
    assert os.stat(path).st_mode & 0o777 == 0o600
    target = tmp_path / "target"
    target.write_text("")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="regular"):
        SQLiteWebhookReplayStore(link)


@pytest.mark.parametrize("delta", (-301, 301))
def test_stale_or_future_delivery_is_rejected(tmp_path: Path, delta: int) -> None:
    payload = body()
    with pytest.raises(WebhookVerificationError, match="stale"):
        verifier(tmp_path / f"{delta}.sqlite").verify(
            payload, headers(payload, timestamp=NOW + delta)
        )


@pytest.mark.parametrize("mutation", ("body", "signature", "id", "missing"))
def test_forged_or_incomplete_deliveries_are_rejected(
    tmp_path: Path, mutation: str
) -> None:
    payload = body()
    signed_headers = headers(payload)
    if mutation == "body":
        payload += b" "
    elif mutation == "signature":
        signed_headers["Webhook-Signature"] = "v1," + base64.b64encode(b"x" * 32).decode()
    elif mutation == "id":
        signed_headers["Webhook-Id"] = "event_other"
    else:
        del signed_headers["Webhook-Signature"]
    with pytest.raises(WebhookVerificationError, match="signature|header|ID"):
        verifier(tmp_path / f"{mutation}.sqlite").verify(payload, signed_headers)


def test_key_rotation_accepts_any_valid_v1_signature(tmp_path: Path) -> None:
    payload = body()
    signed_headers = headers(payload)
    good = signed_headers["Webhook-Signature"]
    bad = "v1," + base64.b64encode(b"x" * 32).decode()
    signed_headers["Webhook-Signature"] = f"{bad} {good}"
    assert verifier(tmp_path / "rotation.sqlite").verify(
        payload, signed_headers
    ).duplicate is False


@pytest.mark.parametrize(
    "payload",
    (
        b"[]",
        b'{"type":"event"}',
        body(**{f"x{i}": i for i in range(17)}),
        body(type="Bad Type"),
        body() + b"x",
    ),
)
def test_malformed_payloads_fail_closed(tmp_path: Path, payload: bytes) -> None:
    with pytest.raises(WebhookVerificationError, match="payload"):
        verifier(tmp_path / f"bad-{hash(payload)}.sqlite").verify(
            payload, headers(payload)
        )


def test_oversized_body_and_invalid_secret_are_rejected(tmp_path: Path) -> None:
    payload = b"x" * 1025
    with pytest.raises(WebhookVerificationError, match="large"):
        verifier(
            tmp_path / "large.sqlite", max_body_bytes=1024
        ).verify(payload, headers(payload))
    with pytest.raises(ValueError, match="32 bytes"):
        AnthropicWebhookVerifier(
            SecretStr("whsec_" + base64.b64encode(b"short").decode()),
            SQLiteWebhookReplayStore(tmp_path / "bad-key.sqlite"),
        )
