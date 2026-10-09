"""Fail-closed, read-only verification of independent release evidence signatures.

This module verifies signatures and digest binding only. It cannot independently
establish that CI, production deployments, or recovery tests actually succeeded.
Do not store private keys or use this as a standalone production GO decision.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

VERIFIER_DOMAIN = b"ZEAZ-PORTFOLIO-VERIFIER-v1\\x00"
OPERATOR_DOMAIN = b"ZEAZ-PORTFOLIO-OPERATOR-v1\\x00"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _decoded(value, length):
    if not isinstance(value, str):
        raise ValueError("not base64")
    result = base64.b64decode(value, validate=True)
    if len(result) != length:
        raise ValueError("incorrect length")
    return result


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def verify_attestation(snapshot, evidence, attestation, trust_store, *, now=None):
    """Return a failure code or None. Trust store MUST come from a pinned source."""
    now = now or datetime.now(timezone.utc)
    try:
        if not isinstance(attestation, dict) or attestation.get("schema_version") != 1:
            return "ATTESTATION_SCHEMA"
        if not isinstance(trust_store, dict) or trust_store.get("schema_version") != 1:
            return "TRUST_STORE_INVALID"
        verifier = attestation["verifier"]
        operator = attestation["operator"]
        receipt = verifier["receipt"]
        target = receipt["release_target"]
        if (receipt.get("schema_version") != 1 or receipt.get("verdict") != "verified"
                or not isinstance(target, dict) or set(target) != {"repo", "sha"}):
            return "ATTESTATION_RECEIPT_INVALID"
        repo = snapshot["repositories"][target["repo"]]
        if repo["main_sha"] != target["sha"]:
            return "ATTESTATION_TARGET_DRIFT"
        if (receipt.get("snapshot_sha256") != digest(snapshot)
                or receipt.get("evidence_sha256") != digest(evidence)):
            return "ATTESTATION_INPUT_MISMATCH"
        issued = _timestamp(receipt["issued_at"])
        expires = _timestamp(receipt["expires_at"])
        if (issued > now + timedelta(minutes=5)
                or issued < now - timedelta(hours=24)
                or expires <= now or expires <= issued
                or expires - issued > timedelta(hours=24)):
            return "ATTESTATION_EXPIRED"
        verifier_id, operator_id = verifier["key_id"], operator["key_id"]
        if verifier_id == operator_id:
            return "ATTESTATION_KEY_SEPARATION"
        verifier_key = _decoded(trust_store["verifiers"][verifier_id], 32)
        operator_key = _decoded(trust_store["operators"][operator_id], 32)
        if verifier_key == operator_key:
            return "ATTESTATION_KEY_SEPARATION"
        Ed25519PublicKey.from_public_bytes(verifier_key).verify(
            _decoded(verifier["signature"], 64),
            VERIFIER_DOMAIN + canonical(receipt))
        approval = operator["approval"]
        if (approval.get("decision") != "approve"
                or approval.get("release_target") != target
                or approval.get("verifier_receipt_sha256") != digest(verifier)):
            return "ATTESTATION_OPERATOR_BINDING"
        approved_at = _timestamp(approval["approved_at"])
        if (approved_at < issued - timedelta(minutes=5)
                or approved_at > now + timedelta(minutes=5)
                or now - approved_at > timedelta(hours=24)):
            return "ATTESTATION_OPERATOR_EXPIRED"
        Ed25519PublicKey.from_public_bytes(operator_key).verify(
            _decoded(operator["signature"], 64),
            OPERATOR_DOMAIN + canonical(approval))
        return None
    except (KeyError, TypeError, ValueError, OverflowError, InvalidSignature,
            base64.binascii.Error, AttributeError):
        return "ATTESTATION_UNTRUSTED_OR_MALFORMED"
