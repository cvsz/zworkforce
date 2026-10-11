"""Deterministic integration tests for the SAGI browser runtime.

Uses installed Playwright Chromium and local 127.0.0.1 test servers.
Verifies redirect SSRF blocking, POST/PUT/PATCH/DELETE rejection,
WebSocket denial, exact target binding, and strict boolean authorization.
Every forbidden request must never reach its destination (hit count zero).

Requires ``playwright`` plus its Chromium runtime; skips cleanly when the
optional dependency is absent so repository checks stay green.
"""
from __future__ import annotations

import http.server
import subprocess
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from zworkforce.sagi_browser_runtime import (
    BrowserPolicy,
    close_browser_socket,
    handle_browser_route,
    run_browser_action,
    validate_navigation,
)
from zworkforce.sagi_computer_use import ComputerAction, prepare_computer_use_intent
from zworkforce.sagi_zloop_binding import PlanBinding


def _make_intent(target: str):
    binding = PlanBinding("loop-1", "tenant-a", "actor-a", "a" * 64, True)
    return prepare_computer_use_intent(
        binding=binding, session_id="s1", step_id="a",
        action=ComputerAction.OBSERVE, target=target,
        screen_evidence_digest="b" * 64,
    )


class _RecordingHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that records hits and serves deterministic fixtures."""

    server_version = "SagiTest/1.0"

    def log_message(self, *args):  # Quiet during tests.
        pass

    def _record(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length:
            try:
                self.rfile.read(length)
            except Exception:
                pass
        self.server.hits.append((self.command, self.path))

    def _send(self, status=200, body=b"ok", extra=None):
        try:
            self.send_response(status)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _handle(self):
        self._record()
        if self.path == "/redirect":
            target = f"http://127.0.0.1:{self.server.secret_port}/secret"
            self._send(status=302, body=b"redirect", extra={"Location": target})
        elif self.path == "/secret":
            self._send(body=b"SECRET-MUST-NOT-LEAK")
        elif self.path == "/page":
            self._send(body=b"<html><body>fixture</body></html>")
        else:
            self._send(body=b"ok")

    do_GET = _handle
    do_POST = _handle
    do_PUT = _handle
    do_PATCH = _handle
    do_DELETE = _handle
    do_HEAD = _handle
    do_OPTIONS = _handle


class LocalTestServer:
    """Deterministic local HTTP server on 127.0.0.1 with hit counters."""

    def __init__(self, secret_port: int = 0):
        self._srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _RecordingHandler)
        self._srv.hits = []
        self._srv.secret_port = secret_port
        self._thread = threading.Thread(target=self._srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)

    @property
    def port(self) -> int:
        return self._srv.server_address[1]

    @property
    def hits(self):
        return list(self._srv.hits)

    def hit_count(self, path: str) -> int:
        return sum(1 for _, hit_path in self.hits if hit_path == path)

    def total_hits(self) -> int:
        return len(self.hits)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._srv.shutdown()
        self._thread.join(timeout=5)
        self._srv.server_close()


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE, "playwright Chromium is required")
class BrowserRuntimeIntegrationTests(unittest.TestCase):
    POLICY_TIMEOUT_MS = 5000

    def setUp(self):
        self.policy = BrowserPolicy(frozenset({"https://example.com"}), timeout_ms=self.POLICY_TIMEOUT_MS)

    def _launch(self, playwright):
        return playwright.chromium.launch(headless=True)

    def test_forbidden_get_never_reaches_destination(self):
        """Strict guard blocks local SSRF targets with real Chromium."""
        from playwright.sync_api import sync_playwright
        with LocalTestServer() as srv, sync_playwright() as playwright:
            browser = self._launch(playwright)
            try:
                context = browser.new_context(service_workers="block")
                try:
                    page = context.new_page()
                    page.goto(f"http://127.0.0.1:{srv.port}/page", timeout=8000)
                    baseline = srv.total_hits()
                    self.assertGreaterEqual(baseline, 1)
                    context.route("**/*", lambda route: handle_browser_route(route, self.policy))
                    outcome = page.evaluate(
                        f"""async () => {{
                            try {{
                                await fetch("http://127.0.0.1:{srv.port}/secret");
                                return "reached-VULN";
                            }} catch (e) {{ return "blocked"; }}
                        }}"""
                    )
                    self.assertEqual(outcome, "blocked")
                    self.assertEqual(srv.total_hits(), baseline,
                                     "forbidden request reached its destination")
                finally:
                    context.close()
            finally:
                browser.close()

    def test_mutation_methods_rejected_and_never_hit(self):
        """POST/PUT/PATCH/DELETE are denied before any network fetch."""
        from playwright.sync_api import sync_playwright
        with LocalTestServer() as srv, sync_playwright() as playwright:
            browser = self._launch(playwright)
            try:
                context = browser.new_context(service_workers="block")
                try:
                    page = context.new_page()
                    page.goto(f"http://127.0.0.1:{srv.port}/page", timeout=8000)
                    context.route("**/*", lambda route: handle_browser_route(route, self.policy))
                    baseline = srv.total_hits()
                    for method in ("POST", "PUT", "PATCH", "DELETE"):
                        with self.subTest(method=method):
                            outcome = page.evaluate(
                                f"""async () => {{
                                    try {{
                                        await fetch("http://127.0.0.1:{srv.port}/secret",
                                                    {{method: "{method}"}});
                                        return "reached-VULN";
                                    }} catch (e) {{ return "blocked"; }}
                                }}"""
                            )
                            self.assertEqual(outcome, "blocked")
                    self.assertEqual(srv.total_hits(), baseline,
                                     "mutating request reached its destination")
                finally:
                    context.close()
            finally:
                browser.close()

    def test_redirect_ssrf_blocked_and_secret_never_hit(self):
        """Allowed redirector returning 302 is aborted; secret server sees zero hits."""
        from playwright.sync_api import sync_playwright
        with LocalTestServer() as secret, LocalTestServer(secret_port=secret.port) as redirector:
            allow_prefix = f"http://127.0.0.1:{redirector.port}/"

            def allow_redirector_only(url, policy):
                if url.startswith(allow_prefix):
                    return None
                validate_navigation(url, policy)

            with patch("zworkforce.sagi_browser_runtime.validate_navigation",
                       side_effect=lambda url, policy: allow_redirector_only(url, policy)):
                # Re-imported handle uses the patched validator via module global.
                from zworkforce import sagi_browser_runtime as runtime
                with sync_playwright() as playwright:
                    browser = self._launch(playwright)
                    try:
                        context = browser.new_context(service_workers="block")
                        try:
                            context.route("**/*", lambda route: runtime.handle_browser_route(route, self.policy))
                            page = context.new_page()
                            page.goto(f"http://127.0.0.1:{redirector.port}/page", timeout=8000)
                            secret_before = secret.total_hits()
                            outcome = page.evaluate(
                                f"""async () => {{
                                    try {{
                                        await fetch("http://127.0.0.1:{redirector.port}/redirect");
                                        return "followed-VULN";
                                    }} catch (e) {{ return "blocked"; }}
                                }}"""
                            )
                            self.assertEqual(outcome, "blocked")
                            self.assertEqual(secret.total_hits(), secret_before,
                                             "redirect target was reached")
                            self.assertEqual(secret.hit_count("/secret"), 0)
                        finally:
                            context.close()
                    finally:
                        browser.close()

    def test_fetch_failure_fails_closed_without_propagating(self):
        """Network/timeout failures abort instead of leaking handler errors."""
        from playwright.sync_api import sync_playwright

        events = []

        class DeadRoute:
            def __init__(self):
                self.request = SimpleNamespace(method="GET", url="https://example.com/dead")
                self.aborted = False

            def fetch(self, **kwargs):
                raise TimeoutError("simulated network timeout")

            def abort(self):
                self.aborted = True
                events.append("aborted")

            def fulfill(self, **kwargs):
                events.append("fulfilled-VULN")

        handle_browser_route(DeadRoute(), self.policy)
        self.assertEqual(events, ["aborted"])

        # Real browser: closed port must fail closed with no destination hit.
        with LocalTestServer() as srv, sync_playwright() as playwright:
            browser = self._launch(playwright)
            try:
                context = browser.new_context()
                try:
                    page = context.new_page()
                    page.goto(f"http://127.0.0.1:{srv.port}/page", timeout=8000)
                    context.route("**/*", lambda route: handle_browser_route(route, self.policy))
                    baseline = srv.total_hits()
                    outcome = page.evaluate(
                        """async () => {
                            try { await fetch("http://127.0.0.1:9/unreachable"); return "reached-VULN"; }
                            catch (e) { return "blocked"; }
                        }"""
                    )
                    self.assertEqual(outcome, "blocked")
                    self.assertEqual(srv.total_hits(), baseline)
                finally:
                    context.close()
            finally:
                browser.close()

    def test_websocket_denied_and_never_dials_destination(self):
        """WebSocket interception fires and the local destination sees zero handshakes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hits_file = str(Path(tmpdir) / "hits.txt")
            Path(hits_file).write_text("", encoding="utf-8")
            probe = (
                "import http.server, threading\n"
                "hits_file = %r\n"
                "class H(http.server.BaseHTTPRequestHandler):\n"
                "    def log_message(self, *a): pass\n"
                "    def do_GET(self):\n"
                "        with open(hits_file, 'a') as f:\n"
                "            f.write(self.path + '\\n')\n"
                "        self.send_response(200)\n"
                "        self.send_header('Access-Control-Allow-Origin', '*')\n"
                "        self.end_headers()\n"
                "        try: self.wfile.write(b'<html>hi</html>')\n"
                "        except Exception: pass\n"
                "srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)\n"
                "threading.Thread(target=srv.serve_forever, daemon=True).start()\n"
                "port = srv.server_address[1]\n"
                "print('probe-port=' + str(port), flush=True)\n"
                "from playwright.sync_api import sync_playwright\n"
                "from zworkforce.sagi_browser_runtime import close_browser_socket\n"
                "with sync_playwright() as p:\n"
                "    b = p.chromium.launch(headless=True)\n"
                "    ctx = b.new_context()\n"
                "    def ws_handler(ws):\n"
                "        print('probe-wsguard=' + ws.url, flush=True)\n"
                "        close_browser_socket(ws)\n"
                "    ctx.route_web_socket('**/*', ws_handler)\n"
                "    def http_guard(route):\n"
                "        if route.request.url.endswith('/page'):\n"
                "            resp = route.fetch(max_redirects=0, timeout=5000)\n"
                "            route.fulfill(response=resp)\n"
                "        else:\n"
                "            route.abort()\n"
                "    ctx.route('**/*', http_guard)\n"
                "    pg = ctx.new_page()\n"
                "    pg.goto(f'http://127.0.0.1:{port}/page', timeout=8000)\n"
                "    print('probe-goto-ok', flush=True)\n"
                "    js = (\"async () => { return new Promise((res) => {\"\n"
                "            \" const ws = new WebSocket('ws://127.0.0.1:\" + str(port) + \"/ws');\"\n"
                "            \" ws.onclose = () => res('CLOSED');\"\n"
                "            \" ws.onerror = () => res('ERR');\"\n"
                "            \" setTimeout(() => res('TIMEOUT'), 2500);\"\n"
                "            \" }); }\")\n"
                "    r = pg.evaluate(js)\n"
                "    print('probe-ws-result=' + r, flush=True)\n"
                "    ctx.close(); b.close()\n"
                "srv.shutdown()\n"
                "print('probe-done', flush=True)\n"
            ) % hits_file
            try:
                completed = subprocess.run(
                    [sys.executable, "-c", probe],
                    capture_output=True, text=True, timeout=40, cwd=".",
                )
                output = (completed.stdout or "") + (completed.stderr or "")
            except subprocess.TimeoutExpired as exc:
                output = ((exc.stdout or b"").decode("utf-8", "replace")
                          if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
                output += ((exc.stderr or b"").decode("utf-8", "replace")
                           if isinstance(exc.stderr, bytes) else (exc.stderr or ""))
            self.assertIn("probe-wsguard=", output,
                          f"WebSocket route did not intercept; output={output[-2000:]}")
            hits = Path(hits_file).read_text(encoding="utf-8").split()
            self.assertIn("/page", hits)
            self.assertNotIn("/ws", hits,
                             "forbidden WebSocket handshake reached its destination")

    def test_exact_target_binding_never_launches_browser(self):
        intent = _make_intent("https://example.com")
        launched = []

        class NoLaunchChromium:
            def launch(self, **kwargs):
                launched.append(kwargs)
                raise AssertionError("browser must not launch for mismatched target")

        fake = SimpleNamespace(
            sync_playwright=lambda: SimpleNamespace(
                __enter__=lambda self: SimpleNamespace(chromium=NoLaunchChromium()),
                __exit__=lambda self, *args: False,
            )
        )
        with patch.dict(sys.modules, {"playwright": SimpleNamespace(sync_api=fake),
                                      "playwright.sync_api": fake}):
            with self.assertRaises(PermissionError):
                run_browser_action(intent=intent, policy=self.policy,
                                   url="https://example.com/other",
                                   authorized=lambda _: True)
        self.assertEqual(launched, [])

    def test_strict_boolean_authorization_never_launches_browser(self):
        intent = _make_intent("https://example.com")
        for verdict in (1, "true", [True], object(), None, False, 0):
            with self.subTest(verdict=repr(verdict)):
                launched = []

                class NoLaunchChromium:
                    def launch(self, **kwargs):
                        launched.append(kwargs)
                        raise AssertionError("browser must not launch without True")

                fake = SimpleNamespace(
                    sync_playwright=lambda: SimpleNamespace(
                        __enter__=lambda self: SimpleNamespace(chromium=NoLaunchChromium()),
                        __exit__=lambda self, *args: False,
                    )
                )
                with patch.dict(sys.modules, {"playwright": SimpleNamespace(sync_api=fake),
                                              "playwright.sync_api": fake}):
                    with self.assertRaises(PermissionError):
                        run_browser_action(intent=intent, policy=self.policy,
                                           url="https://example.com",
                                           authorized=lambda _, v=verdict: v)
                self.assertEqual(launched, [])


if __name__ == "__main__":
    unittest.main()
