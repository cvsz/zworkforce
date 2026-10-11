"""Non-executing packaging preflight; never builds or installs a Samsung TV app."""
from __future__ import annotations

from typing import Any

from .samsung_compat import compatibility
from .samsung_sdk_probe import inspect_environment


def assess(model: str, model_year: int) -> dict[str, Any]:
    advice = compatibility(model, model_year)
    platform = advice["platform_by_year"]
    environment = inspect_environment(platform)
    installed_directory = any(item["directory_exists"] for item in environment["candidates"])
    return {
        "model": advice["model"], "platform": platform,
        "sdk_directory_present": installed_directory,
        "sdk_verified": False, "signing_verified": False,
        "device_verified": False, "build_executed": False,
        "installer_executed": False, "ready_to_build": False,
        "required_checks": [
            "Confirm the model year and firmware against official support evidence",
            "Verify SDK version, executable provenance, and platform support",
            "Verify signing profile and developer registration",
            "Obtain approval before running a sandboxed builder",
            "Validate the resulting package before any authorized device installation",
        ],
    }
