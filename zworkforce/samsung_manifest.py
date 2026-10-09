"""Offline analysis of operator-supplied Samsung source release manifests.

This is not a Samsung Open Source Release Center lookup or a legal opinion.
"""
from __future__ import annotations

import re
from typing import Any

_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$")
_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
_SPDX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+-]{0,99}$")


def analyze(model: str, packages: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(model, str) or not _MODEL.fullmatch(model.strip()):
        raise ValueError("Invalid Samsung model")
    if not isinstance(packages, list) or len(packages) > 100:
        raise ValueError("packages must contain at most 100 items")
    result = []
    for i, item in enumerate(packages):
        if not isinstance(item, dict) or set(item) != {"name", "license", "sha256"}:
            raise ValueError(f"package {i} requires name, license, sha256")
        name, license_id, digest = item["name"], item["license"], item["sha256"]
        if not isinstance(name, str) or not _MODEL.fullmatch(name):
            raise ValueError(f"invalid package name at index {i}")
        if not isinstance(license_id, str) or not _SPDX.fullmatch(license_id):
            raise ValueError(f"invalid license identifier at index {i}")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ValueError(f"invalid sha256 at index {i}")
        result.append({"name": name, "license_declared": license_id,
                       "sha256_declared": digest.lower(), "verified": False})
    return {
        "model": model.strip().upper(), "packages": result,
        "source": "operator_supplied_unverified",
        "licenses_verified": False, "checksums_verified": False,
        "legal_review_required": True,
        "warning": "Declared licenses and hashes have not been validated against original releases",
    }
