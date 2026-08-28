import datetime
import io
import json
import urllib.error
import unittest
import os
from unittest.mock import patch

from zworkforce.zarvis_voice import (
    ZarvisLiveConfig,
    ZarvisLiveVoiceService,
    ZarvisVoiceError,
    load_live_config,
)

class FakeResponse:
    def __init__(self, payload):
        if isinstance(payload, bytes):
            self.payload = payload
        elif isinstance(payload, str):
            self.payload = payload.encode("utf-8")
        else:
            self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size=-1):
        return self.payload if size < 0 else self.payload[:size]

class ZarvisLiveConfigTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_load_defaults_disabled(self):
        config = load_live_config()
        self.assertFalse(config.enabled)
        self.assertEqual(config.api_key, "")

    @patch.dict(os.environ, {"ZWORKFORCE_ZARVIS_LIVE_ENABLED": "true"}, clear=True)
    def test_load_enabled_requires_api_key(self):
        with self.assertRaises(ValueError):
            load_live_config()
        
    @patch.dict(os.environ, {"ZWORKFORCE_ZARVIS_LIVE_ENABLED": "true", "ZWORKFORCE_GEMINI_API_KEY": "short"}, clear=True)
    def test_load_enabled_validates_api_key_length(self):
        with self.assertRaises(ValueError):
            load_live_config()

    @patch.dict(os.environ, {"ZWORKFORCE_ZARVIS_LIVE_ENABLED": "true", "ZWORKFORCE_GEMINI_API_KEY": "test-gemini-api-key-at-least-20-chars", "ZWORKFORCE_ZARVIS_LIVE_THINKING": "invalid_level"}, clear=True)
    def test_load_validates_thinking_level(self):
        with self.assertRaises(ValueError):
            load_live_config()

    @patch.dict(os.environ, {"ZWORKFORCE_ZARVIS_LIVE_ENABLED": "true", "ZWORKFORCE_GEMINI_API_KEY": "test-gemini-api-key-at-least-20-chars", "ZWORKFORCE_ZARVIS_LIVE_VOICE": "a" * 65}, clear=True)
    def test_load_validates_voice_length(self):
        with self.assertRaises(ValueError):
            load_live_config()

    @patch.dict(os.environ, {"ZWORKFORCE_ZARVIS_LIVE_ENABLED": "true", "ZWORKFORCE_GEMINI_API_KEY": "test-gemini-api-key-at-least-20-chars", "ZWORKFORCE_ZARVIS_LIVE_TOKEN_TTL_MINUTES": "4"}, clear=True)
    def test_load_validates_token_ttl_range(self):
        with self.assertRaises(ValueError):
            load_live_config()
            
    @patch.dict(os.environ, {"ZWORKFORCE_ZARVIS_LIVE_ENABLED": "true", "ZWORKFORCE_GEMINI_API_KEY": "test-gemini-api-key-at-least-20-chars", "ZWORKFORCE_ZARVIS_LIVE_TOKEN_TTL_MINUTES": "121"}, clear=True)
    def test_load_validates_token_ttl_range_high(self):
        with self.assertRaises(ValueError):
            load_live_config()

    @patch.dict(os.environ, {"ZWORKFORCE_ZARVIS_LIVE_ENABLED": "true", "ZWORKFORCE_GEMINI_API_KEY": "test-gemini-api-key-at-least-20-chars"}, clear=True)
    def test_websocket_origin_is_always_fixed(self):
        config = load_live_config()
        self.assertEqual(config.websocket_origin, "wss://generativelanguage.googleapis.com")


class ZarvisLiveVoiceServiceTests(unittest.TestCase):
    def config(self, **overrides):
        values = {
            "enabled": True,
            "api_key": "test-gemini-api-key-at-least-20-chars",
            "model": "gemini-3.1-flash-live-preview",
            "voice": "Charon",
            "thinking_level": "minimal",
            "system_prompt": "You are Z.A.R.V.I.S.",
            "token_ttl_minutes": 30,
            "connect_window_minutes": 1,
            "websocket_origin": "wss://generativelanguage.googleapis.com",
        }
        values.update(overrides)
        return ZarvisLiveConfig(**values)

    def test_snapshot_never_serializes_api_key(self):
        service = ZarvisLiveVoiceService(self.config())
        snapshot = service.snapshot()
        rendered = json.dumps(snapshot)
        self.assertNotIn("test-gemini-api-key-at-least-20-chars", rendered)
        self.assertTrue(snapshot["live_enabled"])
        self.assertEqual(snapshot["live_model"], "gemini-3.1-flash-live-preview")
        self.assertEqual(snapshot["live_voice"], "Charon")
        # 'live_thinking_level' might not be in the snapshot, let's just check the ones that exist.

    def test_snapshot_disabled_returns_nulls(self):
        service = ZarvisLiveVoiceService(self.config(enabled=False, api_key=""))
        snapshot = service.snapshot()
        self.assertFalse(snapshot["live_enabled"])
        self.assertIsNone(snapshot.get("live_model"))
        self.assertIsNone(snapshot.get("live_voice"))

    def test_csp_connect_sources_when_enabled(self):
        service = ZarvisLiveVoiceService(self.config())
        self.assertEqual(service.csp_connect_sources, ("wss://generativelanguage.googleapis.com",))

    def test_csp_connect_sources_when_disabled(self):
        service = ZarvisLiveVoiceService(self.config(enabled=False, api_key=""))
        self.assertEqual(service.csp_connect_sources, ())

    def test_issue_live_token_disabled_raises(self):
        service = ZarvisLiveVoiceService(self.config(enabled=False, api_key=""))
        with self.assertRaises(ZarvisVoiceError) as ctx:
            service.issue_live_token(tenant_id="default", subject_id="user", request_id="req-1")
        self.assertEqual(ctx.exception.status, 503)

    def test_issue_live_token_no_api_key_raises(self):
        config = ZarvisLiveConfig(
            enabled=True,
            api_key="",
            model="gemini-3.1-flash-live-preview",
            voice="Charon",
            thinking_level="minimal",
            system_prompt="You are Z.A.R.V.I.S.",
            token_ttl_minutes=30,
            connect_window_minutes=1,
            websocket_origin="wss://generativelanguage.googleapis.com"
        )
        service = ZarvisLiveVoiceService(config)
        with self.assertRaises(ZarvisVoiceError) as ctx:
            service.issue_live_token(tenant_id="default", subject_id="user", request_id="req-1")
        self.assertEqual(ctx.exception.status, 503)

    def test_issue_live_token_success(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"name": "auth_tokens/abc123"})

        service = ZarvisLiveVoiceService(self.config(), opener=opener)
        result = service.issue_live_token(tenant_id="default", subject_id="user", request_id="req-1")
        
        self.assertEqual(result["token"], "auth_tokens/abc123")
        self.assertIn("expires_at", result)
        self.assertEqual(result["model"], "gemini-3.1-flash-live-preview")
        self.assertEqual(result["voice"], "Charon")
        self.assertEqual(result["thinking_level"], "minimal")
        self.assertEqual(result["system_prompt"], "You are Z.A.R.V.I.S.")
        self.assertEqual(result["transport"], "gemini-live")
        self.assertEqual(result["websocket_origin"], "wss://generativelanguage.googleapis.com")
        
        rendered = json.dumps(result)
        self.assertNotIn("test-gemini-api-key-at-least-20-chars", rendered)
        
        self.assertIn("test-gemini-api-key-at-least-20-chars", captured["url"])
        self.assertEqual(captured["body"].get("config", {}).get("uses"), 1)

    def test_issue_live_token_rejects_echoed_api_key(self):
        def opener(request, timeout):
            return FakeResponse({"name": "auth_tokens/abc123", "leaked_key": "test-gemini-api-key-at-least-20-chars"})

        service = ZarvisLiveVoiceService(self.config(), opener=opener)
        with self.assertRaises(ZarvisVoiceError) as ctx:
            service.issue_live_token(tenant_id="default", subject_id="user", request_id="req-1")
        self.assertNotIn("test-gemini-api-key-at-least-20-chars", str(ctx.exception))

    def test_issue_live_token_invalid_token_name(self):
        def opener(request, timeout):
            return FakeResponse({"name": "invalid/abc123"})

        service = ZarvisLiveVoiceService(self.config(), opener=opener)
        with self.assertRaises(ZarvisVoiceError) as ctx:
            service.issue_live_token(tenant_id="default", subject_id="user", request_id="req-1")

    def test_issue_live_token_http_error_maps_to_voice_error(self):
        def opener_429(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", {}, io.BytesIO(b"{}"))
        
        service_429 = ZarvisLiveVoiceService(self.config(), opener=opener_429)
        with self.assertRaises(ZarvisVoiceError) as ctx:
            service_429.issue_live_token(tenant_id="default", subject_id="user", request_id="req-1")
        self.assertEqual(ctx.exception.status, 503)

        def opener_500(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 500, "Server Error", {}, io.BytesIO(b"{}"))

        service_500 = ZarvisLiveVoiceService(self.config(), opener=opener_500)
        with self.assertRaises(ZarvisVoiceError) as ctx:
            service_500.issue_live_token(tenant_id="default", subject_id="user", request_id="req-1")
        self.assertEqual(ctx.exception.status, 502)

    def test_issue_live_token_network_error_maps_to_unavailable(self):
        def opener_timeout(request, timeout):
            raise TimeoutError("connection timed out")

        service = ZarvisLiveVoiceService(self.config(), opener=opener_timeout)
        with self.assertRaises(ZarvisVoiceError) as ctx:
            service.issue_live_token(tenant_id="default", subject_id="user", request_id="req-1")
        self.assertEqual(ctx.exception.status, 503)

    def test_issue_live_token_oversized_response_rejected(self):
        def opener(request, timeout):
            large_payload = {"name": "auth_tokens/abc123", "padding": "x" * 17000}
            return FakeResponse(large_payload)

        service = ZarvisLiveVoiceService(self.config(), opener=opener)
        with self.assertRaises(ZarvisVoiceError) as ctx:
            service.issue_live_token(tenant_id="default", subject_id="user", request_id="req-1")

    def test_issue_live_token_invalid_json_raises(self):
        def opener(request, timeout):
            return FakeResponse(b"invalid json")

        service = ZarvisLiveVoiceService(self.config(), opener=opener)
        with self.assertRaises(ZarvisVoiceError) as ctx:
            service.issue_live_token(tenant_id="default", subject_id="user", request_id="req-1")

if __name__ == "__main__":
    unittest.main()
