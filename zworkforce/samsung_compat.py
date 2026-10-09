"""Offline Samsung TV platform compatibility advisory with source provenance."""
from __future__ import annotations

from typing import Any

LEGACY = "https://developer.samsung.com/smarttv/legacy/samsung-legacy-platform-faq.html"
TIZEN = "https://developer.samsung.com/smarttv/develop/getting-started/quick-start-guide.html"
OSRC = "https://opensource.samsung.com/main"


def compatibility(model: str, model_year: int) -> dict[str, Any]:
    from .samsung_tv import MODEL_PATTERN

    if not isinstance(model, str):
        raise ValueError("model must be a string")
    raw = model.strip()
    if not MODEL_PATTERN.fullmatch(raw):
        raise ValueError("invalid Samsung model identifier")
    if type(model_year) is not int or not 2010 <= model_year <= 2026:
        raise ValueError("model_year must be a verified integer from 2010 to 2026")
    legacy = model_year <= 2014
    platform = "samsung-legacy" if legacy else "tizen"
    return {
        "model": raw.upper(),
        "model_year": model_year,
        "model_year_source": "operator_input_unverified",
        "platform_by_year": platform,
        "device_compatibility_verified": False,
        "sdk": "Samsung TV SDK for Legacy Platform" if legacy else "Samsung TV SDK / Tizen Studio",
        "package_type": "legacy ZIP + required signing workflow" if legacy else "signed .wgt",
        "references": [LEGACY if legacy else TIZEN, OSRC],
        "usb_installation_confirmed": False,
        "requirements": (
            ["Verify exact year and firmware", "Use Legacy Samsung TV SDK, not Tizen Studio",
             "Obtain device-specific signing guidance from Samsung Seller Office",
             "Test on actual hardware; do not assume USB installation works"]
            if legacy else
            ["Verify Tizen version and Web API support", "Configure Samsung TV SDK and signing profile",
             "Build and test with Tizen Studio", "Test install only on authorized TV"]
        ),
        "live_lookup": False,
        "hardware_tested": False,
    }
