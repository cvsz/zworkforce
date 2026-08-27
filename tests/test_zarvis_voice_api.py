import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from common import stack
from zworkforce.api import App


class FakeVoice:
    microphone_enabled = True
    csp_connect_sources = ("wss://voice.example.com",)

    def __init__(self):
        self.calls = []

    def snapshot(self):
        return {
            "enabled": True,
            "configured": True,
            "model": "voice-test",
            "websocket_origins": list(self.csp_connect_sources),
            "transport": "realtime-pcm16",
        }

    def issue_session(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "ticket": "browser-one-time-ticket",
            "expires_at": "2026-08-15T00:01:00.000Z",
            "websocket_url": "wss://voice.example.com/v1/realtime",
            "ticket_transport": "sec-websocket-protocol",
            "model": kwargs.get("model") or "voice-test",
            "transport": "realtime-pcm16",
        }


class FakeLiveVoice:
    csp_connect_sources = ("wss://generativelanguage.googleapis.com",)

    def __init__(self):
        self.calls = []

    def snapshot(self):
        return {
            "live_enabled": True,
            "live_model": "gemini-3.1-flash-live-preview",
            "live_voice": "Charon",
            "live_transport": "gemini-live",
            "live_websocket_origin": "wss://generativelanguage.googleapis.com",
        }

    def issue_live_token(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "token": "auth_tokens/test-ephemeral-token",
            "expires_at": "2026-08-27T08:00:00.000Z",
            "model": "gemini-3.1-flash-live-preview",
            "voice": "Charon",
            "thinking_level": "minimal",
            "system_prompt": "You are Z.A.R.V.I.S.",
            "websocket_origin": "wss://generativelanguage.googleapis.com",
            "transport": "gemini-live",
        }


class ZarvisVoiceApiTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.settings, self.db, self.provider, self.engine, self.auth = stack()
        self.app = App(self.settings, self.db, self.engine, self.auth, self.provider)
        self.voice = FakeVoice()
        self.live_voice = FakeLiveVoice()
        self.app.voice = self.voice
        self.app.live_voice = self.live_voice
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.app.handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.engine.shutdown()
        self.temp.cleanup()

    def req(self, path, method="GET", body=None, secret="test-admin-secret"):
        headers = {"Authorization": f"Bearer {secret}"} if secret else {}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read()) if response.headers.get_content_type() == "application/json" else None
            return response.status, dict(response.headers), payload

    def test_voice_health_requires_voice_scope_and_contains_no_server_secret(self):
        status, _, payload = self.req("/api/v1/zarvis/voice")
        self.assertEqual(status, 200)
        self.assertTrue(payload["enabled"])
        self.assertTrue(payload["live_enabled"])
        self.assertNotIn("service_token", payload)
        self.assertNotIn("gateway_url", payload)
        self.assertNotIn("api_key", payload)

        _, viewer_secret = self.auth.create_key("default", "viewer", "viewer", ["workforce:read"])
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.req("/api/v1/zarvis/voice", secret=viewer_secret)
        self.assertEqual(ctx.exception.code, 403)

    def test_voice_session_uses_authenticated_tenant_and_subject(self):
        status, _, payload = self.req("/api/v1/zarvis/voice/session", "POST", {"model": "voice-test"})
        self.assertEqual(status, 201)
        self.assertEqual(payload["ticket"], "browser-one-time-ticket")
        self.assertEqual(self.voice.calls[0]["tenant_id"], "default")
        self.assertIn("test-admin", self.voice.calls[0]["subject_id"])
        self.assertNotIn("Authorization", json.dumps(payload))
        self.assertNotIn("service_token", payload)

        audit = self.db.list_audit("default", 20, 0)
        self.assertTrue(any(item["action"] == "zarvis.voice.session" for item in audit))
        rendered = json.dumps(audit)
        self.assertNotIn("browser-one-time-ticket", rendered)

    def test_voice_live_token_uses_authenticated_tenant_and_audits(self):
        status, _, payload = self.req("/api/v1/zarvis/voice/live-token", "POST", {})
        self.assertEqual(status, 201)
        self.assertEqual(payload["token"], "auth_tokens/test-ephemeral-token")
        self.assertEqual(payload["transport"], "gemini-live")
        self.assertEqual(self.live_voice.calls[0]["tenant_id"], "default")
        self.assertIn("test-admin", self.live_voice.calls[0]["subject_id"])
        self.assertNotIn("Authorization", json.dumps(payload))
        self.assertNotIn("api_key", payload)

        audit = self.db.list_audit("default", 20, 0)
        self.assertTrue(any(item["action"] == "zarvis.voice.live_token" for item in audit))
        rendered = json.dumps(audit)
        self.assertNotIn("test-ephemeral-token", rendered)

    def test_voice_security_headers_are_narrow_and_enable_microphone_self(self):
        request = urllib.request.Request(self.base + "/")
        with urllib.request.urlopen(request, timeout=5) as response:
            permissions = response.headers["Permissions-Policy"]
            csp = response.headers["Content-Security-Policy"]
        self.assertIn("microphone=(self)", permissions)
        self.assertIn("connect-src 'self' wss://voice.example.com wss://generativelanguage.googleapis.com", csp)
        self.assertNotIn("connect-src 'self' ws: wss:", csp)

    def test_voice_worklet_is_served_as_javascript(self):
        request = urllib.request.Request(self.base + "/zarvis-voice-worklet.js")
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.headers["Content-Type"], "text/javascript; charset=utf-8")
            source = response.read().decode("utf-8")
        self.assertIn("zworkforce-voice-capture", source)


if __name__ == "__main__":
    unittest.main()
