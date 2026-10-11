import unittest
from dataclasses import replace
from unittest.mock import patch
from types import SimpleNamespace
import sys

from zworkforce.sagi_browser_runtime import (
    BrowserPolicy, run_browser_action, validate_navigation,
)
from zworkforce.sagi_computer_use import (
    ComputerAction, prepare_computer_use_intent,
)
from zworkforce.sagi_zloop_binding import PlanBinding


class BrowserRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.policy = BrowserPolicy(frozenset({"https://example.com"}))
        binding = PlanBinding("loop-1", "tenant-a", "actor-a", "a" * 64, True)
        self.observe = prepare_computer_use_intent(
            binding=binding, session_id="s1", step_id="a",
            action=ComputerAction.OBSERVE, target="https://example.com",
            screen_evidence_digest="b" * 64,
        )
        # Simulate an interactive intent at the browser authorization boundary.
        # Browser runtime must reject it before any Playwright operation.
        self.click = replace(self.observe, action=ComputerAction.CLICK)

    def test_denies_unapproved_observation_before_importing_playwright(self):
        with self.assertRaises(PermissionError):
            run_browser_action(intent=self.observe, policy=self.policy,
                               url="https://example.com", authorized=lambda _: False)

    def test_requires_explicit_true_authorization(self):
        for verdict in ("deny", object(), None, 1):
            with self.subTest(verdict=repr(verdict)), self.assertRaises(PermissionError):
                run_browser_action(intent=self.observe, policy=self.policy,
                                   url="https://example.com", authorized=lambda _: verdict)

    def test_denies_changed_navigation_target(self):
        with self.assertRaises(PermissionError):
            run_browser_action(intent=self.observe, policy=self.policy,
                               url="https://example.com/other", authorized=lambda _: True)

    def test_denies_interactive_actions(self):
        with self.assertRaises(PermissionError):
            run_browser_action(intent=self.click, policy=self.policy,
                               url="https://example.com", authorized=lambda _: True)

    def test_exact_origin_and_https_are_required(self):
        validate_navigation("https://example.com/page", self.policy)
        for url in ("http://example.com", "https://example.com.evil.org",
                    "https://example.com:443", "https://user@example.com",
                    "https://127.0.0.1", "file:///etc/passwd"):
            with self.subTest(url=url), self.assertRaises(PermissionError):
                validate_navigation(url, self.policy)

    def test_cannot_allow_ip_localhost_or_bad_origin(self):
        for origin in ("http://example.com", "https://localhost",
                       "https://127.0.0.1", "https://example.com/path",
                       "https://foo.localhost", "https://localhost."):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                BrowserPolicy(frozenset({origin}))


    def test_browser_route_guard_denies_redirect_post_and_websocket(self):
        """Exercise installed Playwright handlers without external networking."""
        events = []
        class Route:
            def __init__(self, method="GET", status=200, url="https://example.com"):
                self.request = SimpleNamespace(method=method, url=url)
                self.status = status
                self.aborted = False
                self.fulfilled = False
            def fetch(self, **kwargs):
                events.append(("fetch", self.request.url, kwargs))
                return SimpleNamespace(status=self.status)
            def abort(self):
                self.aborted = True
            def fulfill(self, **kwargs):
                self.fulfilled = True

        class FakeContext:
            def route_web_socket(self, pattern, handler):
                self.ws_handler = handler
            def route(self, pattern, handler):
                self.handler = handler
            def new_page(self):
                return SimpleNamespace(
                    goto=lambda *args, **kwargs: self.run_routes(),
                    screenshot=lambda **kwargs: b"test-image",
                )
            def run_routes(self):
                successful = Route()
                self.handler(successful)
                assert successful.fulfilled
                for method in ("POST", "PUT", "PATCH", "DELETE"):
                    blocked = Route(method=method)
                    before = len(events)
                    self.handler(blocked)
                    assert blocked.aborted and len(events) == before
                blocked_destination = Route(url="https://127.0.0.1/private")
                before = len(events)
                self.handler(blocked_destination)
                assert blocked_destination.aborted and len(events) == before
                redirect = Route(status=302)
                self.handler(redirect)
                assert redirect.aborted and not redirect.fulfilled
                socket = SimpleNamespace(close=lambda: events.append(("ws_closed",)))
                self.ws_handler(socket)
                assert ("ws_closed",) in events
            def close(self):
                pass

        ctx = FakeContext()
        class FakeBrowser:
            def new_context(self, **kwargs):
                return ctx
            def close(self):
                pass
        class Manager:
            def __enter__(self):
                return SimpleNamespace(chromium=SimpleNamespace(
                    launch=lambda **kwargs: FakeBrowser()))
            def __exit__(self, *args):
                return False
        fake = SimpleNamespace(sync_playwright=lambda: Manager())
        with patch.dict(sys.modules, {"playwright": SimpleNamespace(sync_api=fake),
                                      "playwright.sync_api": fake}):
            screenshot = run_browser_action(
                intent=self.observe, policy=self.policy,
                url="https://example.com", authorized=lambda _: True)
        self.assertEqual(screenshot, b"test-image")
        self.assertEqual(sum(1 for x in events if x[0] == "fetch"), 2)

    def test_invalid_timeout(self):
        with self.assertRaises(ValueError):
            BrowserPolicy(frozenset({"https://example.com"}), timeout_ms=0)


if __name__ == "__main__":
    unittest.main()
