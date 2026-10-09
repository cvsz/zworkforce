"""Offline, non-executing Samsung SDK environment inspection."""
from __future__ import annotations

import os
from typing import Any


def inspect_environment(platform: str, env: dict[str, str] | None = None) -> dict[str, Any]:
    if platform not in ("samsung-legacy", "tizen"):
        raise ValueError("platform must be samsung-legacy or tizen")
    source = os.environ if env is None else env
    if not isinstance(source, dict) and env is not None:
        raise ValueError("env must be a mapping")
    candidates = (("SAMSUNG_LEGACY_SDK_HOME",) if platform == "samsung-legacy"
                  else ("TIZEN_STUDIO_HOME", "TIZEN_SDK_HOME"))
    found = []
    for name in candidates:
        value = source.get(name, "")
        if isinstance(value, str) and value and os.path.isabs(value):
            found.append({"variable": name, "configured": True, "directory_exists": os.path.isdir(value)})
    return {
        "platform": platform, "configured": bool(found),
        "candidates": found, "sdk_verified": False, "packaging_available": False,
        "executed_commands": [], "device_connected": False, "signing_verified": False,
        "next_steps": ["Verify installed SDK version and license outside MCP",
                       "Confirm approved signing profile and model compatibility",
                       "Use a separate approved builder before any device installation"],
    }
