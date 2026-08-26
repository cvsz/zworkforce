from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any

from .capabilities import CapabilityError, is_enterprise_manifest, validate_capability_manifest

SKILL_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")


class SkillError(ValueError):
    pass


def canonical_manifest(manifest: dict[str, Any]) -> bytes:
    validate_manifest(manifest)
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_manifest(manifest: dict[str, Any], key: str) -> str:
    if not key:
        raise SkillError("skill signing key is not configured")
    return hmac.new(key.encode("utf-8"), canonical_manifest(manifest), hashlib.sha256).hexdigest()


def verify_manifest(manifest: dict[str, Any], signature: str, key: str, require_signature: bool) -> bool:
    if not key:
        return not require_signature and not signature
    if not signature:
        return not require_signature
    expected = sign_manifest(manifest, key)
    return hmac.compare_digest(expected, signature.lower())


def validate_manifest(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict):
        raise SkillError("skill manifest must be an object")
    skill_id = str(manifest.get("id", ""))
    if not SKILL_ID.fullmatch(skill_id):
        raise SkillError("skill id must be a DNS-like slug")
    version = str(manifest.get("version", ""))
    if not version or len(version) > 64:
        raise SkillError("skill version is required and must be <= 64 characters")
    tools = manifest.get("allowed_tools", [])
    if not isinstance(tools, list) or any(not isinstance(x, str) for x in tools):
        raise SkillError("allowed_tools must be an array of strings")
    prompt = str(manifest.get("system_prompt_append", ""))
    if len(prompt) > 20_000:
        raise SkillError("system_prompt_append is too large")

    if is_enterprise_manifest(manifest):
        try:
            validate_capability_manifest(manifest, expected_kind="Skill")
        except CapabilityError as exc:
            raise SkillError(str(exc)) from exc
