"""Read-only Samsung TV development and open-source resource catalog.

This module intentionally does not scrape the Samsung portal or operate devices.
"""
from __future__ import annotations

import re
from typing import Any

SOURCES = {
    "developer": {
        "title": "Samsung Smart TV Developers",
        "url": "https://developer.samsung.com/smarttv/develop",
        "purpose": "Tizen TV web application SDK, APIs, packaging, testing and distribution",
    },
    "opensource": {
        "title": "Samsung Open Source Release Center",
        "url": "https://opensource.samsung.com/main",
        "purpose": "Model-related open source release discovery and license notices",
    },
}
MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$")


def sources() -> dict[str, Any]:
    return {"sources": [{**{"id": key}, **value} for key, value in SOURCES.items()],
            "live_verified": False, "mode": "curated_links"}


def model_guidance(model: str) -> dict[str, Any]:
    raw = model.strip()
    if not MODEL_PATTERN.fullmatch(raw):
        raise ValueError("model must be 2-64 ASCII letters, numbers, dots, underscores or hyphens")
    normalized = raw.upper()
    # Do not infer a firmware/SDK family from arbitrary model strings.
    return {
        "model": normalized,
        "verification_status": "unverified",
        "os_family": "unknown",
        "package_format": None,
        "developer_docs": SOURCES["developer"]["url"],
        "source_release_search": SOURCES["opensource"]["url"],
        "next_steps": [
            "Confirm model and model year from device label or official Samsung support",
            "Identify whether the device uses the legacy Samsung TV platform or Tizen",
            "Search the Open Source Release Center using the exact model",
            "Verify package availability and licensing on Samsung's portal",
        ],
        "warning": "Open source packages do not imply a flashable firmware or a compatible app installer",
    }
