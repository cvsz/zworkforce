"""Security primitives for GitHub webhook ingress.

This module deliberately does not create an HTTP endpoint or grant repository
mutation authority. The API layer must call these helpers on the raw request
body before parsing or enqueueing a delivery.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any

_SIGNATURE_RE = re.compile(r"^sha256=[0-9a-f]{64}$")
_DELIVERY_RE = re.compile(r"^[A-Fa-f0-9-]{16,128}$")
_ALLOWED_EVENTS = {"pull_request", "check_suite", "check_run"}
_PR_ACTIONS = {"opened", "reopened", "ready_for_review", "synchronize"}
_CHECK_ACTIONS = {"requested", "rerequested", "completed"}


class GitHubWebhookError(ValueError):
    """Raised when a webhook delivery fails validation."""


@dataclass(frozen=True)
class GitHubWebhookDelivery:
    delivery_id: str
    event: str
    action: str
    payload: dict[str, Any]
    payload_sha256: str


def verify_signature(secret: str, raw_body: bytes, signature_header: str) -> bool:
    """Verify X-Hub-Signature-256 against exact raw request bytes."""
    if not secret or not isinstance(raw_body, bytes):
        return False
    if not isinstance(signature_header, str) or not _SIGNATURE_RE.fullmatch(signature_header):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def parse_delivery(
    *,
    delivery_id: str,
    event: str,
    raw_body: bytes,
    signature_header: str,
    secret: str,
    max_body_bytes: int = 1_048_576,
) -> GitHubWebhookDelivery:
    """Authenticate and validate a supported webhook without side effects."""
    if not isinstance(max_body_bytes, int) or max_body_bytes < 1:
        raise GitHubWebhookError("invalid webhook body limit")
    if not isinstance(raw_body, bytes) or len(raw_body) > max_body_bytes:
        raise GitHubWebhookError("webhook body is invalid or too large")
    if not isinstance(delivery_id, str) or not _DELIVERY_RE.fullmatch(delivery_id):
        raise GitHubWebhookError("invalid webhook delivery ID")
    if event not in _ALLOWED_EVENTS:
        raise GitHubWebhookError("unsupported webhook event")
    if not verify_signature(secret, raw_body, signature_header):
        raise GitHubWebhookError("invalid webhook signature")

    try:
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GitHubWebhookError("invalid webhook JSON") from exc
    if not isinstance(payload, dict):
        raise GitHubWebhookError("webhook JSON must be an object")

    action = payload.get("action", "")
    if not isinstance(action, str):
        raise GitHubWebhookError("invalid webhook action")
    allowed_actions = _PR_ACTIONS if event == "pull_request" else _CHECK_ACTIONS
    if action not in allowed_actions:
        raise GitHubWebhookError("unsupported webhook action")

    repository = payload.get("repository")
    if not isinstance(repository, dict):
        raise GitHubWebhookError("missing repository identity")
    full_name = repository.get("full_name")
    if not isinstance(full_name, str) or not re.fullmatch(
        r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}", full_name
    ):
        raise GitHubWebhookError("invalid repository identity")

    if event == "pull_request":
        pr = payload.get("pull_request")
        if not isinstance(pr, dict):
            raise GitHubWebhookError("missing pull request")
        number = payload.get("number")
        head = pr.get("head")
        base = pr.get("base")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise GitHubWebhookError("invalid pull request number")
        if not isinstance(head, dict) or not isinstance(base, dict):
            raise GitHubWebhookError("missing pull request refs")
        for ref in (head.get("sha"), base.get("sha")):
            if not isinstance(ref, str) or not re.fullmatch(r"[0-9a-f]{40}", ref):
                raise GitHubWebhookError("invalid pull request commit SHA")

    return GitHubWebhookDelivery(
        delivery_id=delivery_id,
        event=event,
        action=action,
        payload=payload,
        payload_sha256=hashlib.sha256(raw_body).hexdigest(),
    )
