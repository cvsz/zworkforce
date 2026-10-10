"""Opt-in, single-action Playwright browser adapter for SAGI.

No browser is launched until an external canonical permission checker grants
the exact intent. A digest is not a grant. No persistent browser profile.
This adapter intentionally does not expose an HTTP API or run by default.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit
import ipaddress

from zworkforce.sagi_computer_use import ComputerAction, ComputerUseIntent


@dataclass(frozen=True)
class BrowserPolicy:
    allowed_origins: frozenset[str]
    timeout_ms: int = 10000

    def __post_init__(self) -> None:
        if not self.allowed_origins or not 100 <= self.timeout_ms <= 30000:
            raise ValueError("invalid browser policy")
        for origin in self.allowed_origins:
            parts = urlsplit(origin)
            if (parts.scheme != "https" or not parts.hostname or
                parts.username or parts.password or parts.path or
                parts.query or parts.fragment or parts.port is not None):
                raise ValueError("only canonical HTTPS origins are allowed")
            try:
                ipaddress.ip_address(parts.hostname)
            except ValueError:
                if parts.hostname == "localhost" or "." not in parts.hostname:
                    raise ValueError("private hostname not allowed")
            else:
                raise ValueError("IP address origins are not allowed")


def validate_navigation(url: str, policy: BrowserPolicy) -> None:
    """Exact HTTPS origin enforcement; network sandbox is still required."""
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if (parts.scheme != "https" or parts.username or parts.password or
        parts.hostname is None or parts.port is not None or
        origin not in policy.allowed_origins):
        raise PermissionError("destination not permitted")


def run_browser_action(
    *,
    intent: ComputerUseIntent,
    policy: BrowserPolicy,
    url: str,
    authorized: Callable[[ComputerUseIntent], bool],
) -> bytes:
    """Execute only approved OBSERVE via ephemeral Chromium; return screenshot bytes.

    Interactive inputs require a separate implementation with exact durable
    approval, fresh trusted screen verification, and replay protection.
    """
    if not isinstance(intent, ComputerUseIntent):
        raise PermissionError("invalid computer intent")
    if not isinstance(policy, BrowserPolicy):
        raise PermissionError("browser policy required")
    if intent.action is not ComputerAction.OBSERVE:
        raise PermissionError("interactive computer actions are disabled")
    validate_navigation(url, policy)
    if not authorized(intent):
        raise PermissionError("canonical permission denied")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("install playwright and its Chromium runtime") from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                accept_downloads=False,
                permissions=[],
                service_workers="block",
            )
            try:
                def guard(route):
                    try:
                        validate_navigation(route.request.url, policy)
                    except PermissionError:
                        route.abort()
                    else:
                        route.continue_()

                context.route("**/*", guard)
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=policy.timeout_ms)
                return page.screenshot(timeout=policy.timeout_ms)
            finally:
                context.close()
        finally:
            browser.close()
