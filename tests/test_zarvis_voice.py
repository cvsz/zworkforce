import io
import json
import urllib.error
import unittest

from zworkforce.zarvis_voice import ZarvisVoiceConfig, ZarvisVoiceError, ZarvisVoiceService


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size=-1):
        return self.payload if size < 0 else self.payload[:size]


class ZarvisVoiceTests(unittest.TestCase):
    def config(self, **overrides):
        values = {
            "enabled": True,
            "gateway_url": "http://voice-gateway:8450",
            "service_token": "synthetic-voice-service-token-for-tests-000000000000",
            "websocket_allowlist": ("wss://voice.example.com",),
            "model": "voice-local",
            "timeout_seconds": 2.0,
        }
        values.update(overrides)
        return ZarvisVoiceConfig(**values)

    def test_snapshot_never_serializes_service_token_or_gateway_url(self):
        service = ZarvisVoiceService(self.config())
        snapshot = service.snapshot()
        rendered = json.dumps(snapshot)
        self.assertNotIn("synthetic-voice-service-token-for-tests-000000000000", rendered)
        self.assertNotIn("voice-gateway:8450", rendered)
        self.assertTrue(snapshot["enabled"])
        self.assertEqual(snapshot["websocket_origins"], ["wss://voice.example.com"])

    def test_issue_session_forwards_server_identity_and_returns_browser_safe_material(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse({
                "ticket": "signed-ticket",
                "expires_at": "2026-08-15T00:01:00.000Z",
                "websocket_url": "wss://voice.example.com/v1/realtime",
                "ticket_transport": "sec-websocket-protocol",
            })

        service = ZarvisVoiceService(self.config(), opener=opener)
        result = service.issue_session(
            tenant_id="default",
            subject_id="bootstrap-test:operator",
            request_id="request-1",
        )
        self.assertEqual(captured["url"], "http://voice-gateway:8450/v1/voice/tickets")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer synthetic-voice-service-token-for-tests-000000000000")
        self.assertEqual(captured["headers"]["X-tenant-id"], "default")
        self.assertEqual(captured["headers"]["X-subject-id"], "bootstrap-test:operator")
        self.assertEqual(captured["body"], {"model": "voice-local"})
        self.assertEqual(result["ticket"], "signed-ticket")
        self.assertEqual(result["websocket_url"], "wss://voice.example.com/v1/realtime")
        self.assertNotIn("service_token", result)
        self.assertNotIn("gateway_url", result)

    def test_denies_websocket_origin_not_in_allowlist(self):
        service = ZarvisVoiceService(
            self.config(),
            opener=lambda *_args, **_kwargs: FakeResponse({
                "ticket": "signed-ticket",
                "expires_at": "2026-08-15T00:01:00.000Z",
                "websocket_url": "wss://attacker.example/v1/realtime",
            }),
        )
        with self.assertRaises(ZarvisVoiceError) as ctx:
            service.issue_session(tenant_id="default", subject_id="user", request_id="request-2")
        self.assertEqual(ctx.exception.code, "voice_websocket_origin_denied")

    def test_disabled_service_fails_closed(self):
        service = ZarvisVoiceService(self.config(enabled=False))
        with self.assertRaises(ZarvisVoiceError) as ctx:
            service.issue_session(tenant_id="default", subject_id="user", request_id="request-3")
        self.assertEqual(ctx.exception.status, 503)
        self.assertEqual(ctx.exception.code, "voice_disabled")

    def test_enabled_service_rejects_short_or_whitespace_service_tokens(self):
        for token in ("short-token", "x" * 31, " " * 40, "\t" * 40):
            with self.subTest(token_length=len(token)):
                with self.assertRaisesRegex(ValueError, "at least 32 non-whitespace characters"):
                    ZarvisVoiceService(self.config(service_token=token))

        # The boundary is inclusive: 32 non-whitespace characters are accepted.
        ZarvisVoiceService(self.config(service_token="x" * 32))

    def test_upstream_http_error_does_not_reflect_upstream_body(self):
        def opener(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                hdrs=None,
                fp=io.BytesIO(b'{"error":{"message":"secret details"}}'),
            )

        service = ZarvisVoiceService(self.config(), opener=opener)
        with self.assertRaises(ZarvisVoiceError) as ctx:
            service.issue_session(tenant_id="default", subject_id="user", request_id="request-4")
        self.assertEqual(ctx.exception.code, "voice_gateway_rejected")
        self.assertNotIn("secret details", str(ctx.exception))

    def test_rejects_upstream_payload_that_echoes_service_token(self):
        def opener(request, timeout):
            return FakeResponse({
                "ticket": "synthetic-voice-service-token-for-tests-000000000000",
                "expires_at": "2026-08-15T00:01:00.000Z",
                "websocket_url": "wss://voice.example.com/v1/realtime",
            })

        service = ZarvisVoiceService(self.config(), opener=opener)
        with self.assertRaises(ZarvisVoiceError) as ctx:
            service.issue_session(tenant_id="default", subject_id="user", request_id="request-5")
        self.assertEqual(ctx.exception.code, "voice_gateway_invalid_response")
        self.assertNotIn("synthetic-voice-service-token-for-tests-000000000000", str(ctx.exception))

    def test_issue_session_result_never_contains_token_or_authorization_keys(self):
        def opener(request, timeout):
            return FakeResponse({
                "ticket": "signed-ticket",
                "expires_at": "2026-08-15T00:01:00.000Z",
                "websocket_url": "wss://voice.example.com/v1/realtime",
                "service_token": "leaked",
                "Authorization": "Bearer leaked",
            })

        service = ZarvisVoiceService(self.config(), opener=opener)
        result = service.issue_session(tenant_id="default", subject_id="user", request_id="request-6")
        rendered = json.dumps(result)
        self.assertNotIn("service_token", rendered)
        self.assertNotIn("Authorization", rendered)
        self.assertNotIn("Bearer", rendered)
        self.assertNotIn("synthetic-voice-service-token-for-tests-000000000000", rendered)
        self.assertEqual(set(result), {"ticket", "expires_at", "websocket_url", "ticket_transport", "model", "transport"})


class ZarvisVoiceApiTests(unittest.TestCase):
    """API-level coverage: the 201 session response must never carry the service token."""

    def setUp(self):
        import threading
        from http.server import ThreadingHTTPServer

        from tests.common import stack
        from zworkforce.api import App

        self.temp, self.settings, self.db, self.provider, self.engine, self.auth = stack()
        self.app = App(self.settings, self.db, self.engine, self.auth, self.provider)
        self.app.voice = ZarvisVoiceService(
            ZarvisVoiceConfig(
                enabled=True,
                gateway_url="http://voice-gateway:8450",
                service_token="synthetic-voice-service-token-for-tests-000000000000",
                websocket_allowlist=("wss://voice.example.com",),
                model="voice-local",
                timeout_seconds=2.0,
            ),
            opener=self._opener,
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.app.handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.engine.shutdown()
        self.temp.cleanup()

    def _opener(self, request, timeout):
        return FakeResponse({
            "ticket": "signed-ticket",
            "expires_at": "2026-08-15T00:01:00.000Z",
            "websocket_url": "wss://voice.example.com/v1/realtime",
        })

    def _session(self, body=None):
        import urllib.request

        payload = json.dumps(body or {}).encode("utf-8")
        req = urllib.request.Request(
            self.base + "/api/v1/zarvis/voice/session",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": "Bearer test-admin-secret"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())

    def test_session_response_body_is_browser_safe(self):
        status, data = self._session()
        self.assertEqual(status, 201)
        rendered = json.dumps(data)
        self.assertNotIn("service_token", rendered)
        self.assertNotIn("Authorization", rendered)
        self.assertNotIn("synthetic-voice-service-token-for-tests-000000000000", rendered)
        self.assertEqual(set(data), {"ticket", "expires_at", "websocket_url", "ticket_transport", "model", "transport"})
        self.assertEqual(data["ticket"], "signed-ticket")

    def test_session_response_rejects_upstream_token_echo(self):
        import urllib.error

        original_opener = self._opener

        def echoing_opener(request, timeout):
            return FakeResponse({
                "ticket": "synthetic-voice-service-token-for-tests-000000000000",
                "expires_at": "2026-08-15T00:01:00.000Z",
                "websocket_url": "wss://voice.example.com/v1/realtime",
            })

        self.app.voice = ZarvisVoiceService(self.app.voice.config, opener=echoing_opener)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._session()
        self.assertEqual(ctx.exception.code, 502)
        body = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(body["error"]["code"], "voice_gateway_invalid_response")
        self.assertNotIn("synthetic-voice-service-token-for-tests-000000000000", json.dumps(body))


if __name__ == "__main__":
    unittest.main()
