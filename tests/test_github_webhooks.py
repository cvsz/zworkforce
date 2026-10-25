from __future__ import annotations

import hashlib
import hmac
import json
import unittest

from zworkforce.github_webhooks import (
    GitHubWebhookError,
    parse_delivery,
    verify_signature,
)


SECRET = "test-webhook-secret"
DELIVERY_ID = "12345678-1234-1234-1234-123456789abc"
SHA = "a" * 40


def signed(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def pr_payload(**overrides):
    payload = {
        "action": "opened",
        "number": 12,
        "repository": {"full_name": "cvsz/zworkforce"},
        "pull_request": {
            "head": {"sha": SHA},
            "base": {"sha": "b" * 40},
        },
    }
    payload.update(overrides)
    return json.dumps(payload, separators=(",", ":")).encode()


class GitHubWebhookTests(unittest.TestCase):
    def test_signature_is_bound_to_exact_raw_bytes(self):
        body = b'{"action":"opened"}'
        self.assertTrue(verify_signature(SECRET, body, signed(body)))
        self.assertFalse(verify_signature(SECRET, body + b" ", signed(body)))
        self.assertFalse(verify_signature("", body, signed(body)))
        self.assertFalse(verify_signature(SECRET, body, "sha1=" + "0" * 40))

    def test_verify_signature_rejects_non_string_secret(self):
        body = pr_payload()
        self.assertFalse(verify_signature(123, body, signed(body)))

    def test_rejects_non_string_event(self):
        body = pr_payload()
        with self.assertRaisesRegex(GitHubWebhookError, "unsupported webhook event"):
            parse_delivery(
                delivery_id=DELIVERY_ID,
                event=[],
                raw_body=body,
                signature_header=signed(body),
                secret=SECRET,
            )

    def test_rejects_boolean_body_limit(self):
        body = pr_payload()
        with self.assertRaisesRegex(GitHubWebhookError, "body limit"):
            parse_delivery(
                delivery_id=DELIVERY_ID,
                event="pull_request",
                raw_body=body,
                signature_header=signed(body),
                secret=SECRET,
                max_body_bytes=True,
            )

    def test_parse_valid_pull_request_delivery(self):
        body = pr_payload()
        delivery = parse_delivery(
            delivery_id=DELIVERY_ID,
            event="pull_request",
            raw_body=body,
            signature_header=signed(body),
            secret=SECRET,
        )
        self.assertEqual("opened", delivery.action)
        self.assertEqual("cvsz/zworkforce", delivery.payload["repository"]["full_name"])
        self.assertEqual(hashlib.sha256(body).hexdigest(), delivery.payload_sha256)

    def test_rejects_invalid_signature_before_accepting_payload(self):
        body = pr_payload()
        with self.assertRaisesRegex(GitHubWebhookError, "signature"):
            parse_delivery(
                delivery_id=DELIVERY_ID,
                event="pull_request",
                raw_body=body,
                signature_header="sha256=" + "0" * 64,
                secret=SECRET,
            )

    def test_rejects_oversized_body(self):
        body = pr_payload()
        with self.assertRaisesRegex(GitHubWebhookError, "too large"):
            parse_delivery(
                delivery_id=DELIVERY_ID,
                event="pull_request",
                raw_body=body,
                signature_header=signed(body),
                secret=SECRET,
                max_body_bytes=10,
            )

    def test_rejects_malformed_json(self):
        body = b"{"
        with self.assertRaisesRegex(GitHubWebhookError, "JSON"):
            parse_delivery(
                delivery_id=DELIVERY_ID,
                event="pull_request",
                raw_body=body,
                signature_header=signed(body),
                secret=SECRET,
            )

    def test_rejects_unsupported_event_action(self):
        body = pr_payload(action="closed")
        with self.assertRaisesRegex(GitHubWebhookError, "action"):
            parse_delivery(
                delivery_id=DELIVERY_ID,
                event="pull_request",
                raw_body=body,
                signature_header=signed(body),
                secret=SECRET,
            )

    def test_rejects_invalid_pull_request_sha(self):
        body = pr_payload(pull_request={"head": {"sha": "short"}, "base": {"sha": "b" * 40}})
        with self.assertRaisesRegex(GitHubWebhookError, "SHA"):
            parse_delivery(
                delivery_id=DELIVERY_ID,
                event="pull_request",
                raw_body=body,
                signature_header=signed(body),
                secret=SECRET,
            )

    def test_accepts_supported_check_suite_event(self):
        body = json.dumps({
            "action": "requested",
            "repository": {"full_name": "cvsz/zworkforce"},
        }).encode()
        delivery = parse_delivery(
            delivery_id=DELIVERY_ID,
            event="check_suite",
            raw_body=body,
            signature_header=signed(body),
            secret=SECRET,
        )
        self.assertEqual("check_suite", delivery.event)

    def test_rejects_invalid_delivery_id(self):
        body = pr_payload()
        with self.assertRaisesRegex(GitHubWebhookError, "delivery ID"):
            parse_delivery(
                delivery_id="invalid",
                event="pull_request",
                raw_body=body,
                signature_header=signed(body),
                secret=SECRET,
            )


if __name__ == "__main__":
    unittest.main()
