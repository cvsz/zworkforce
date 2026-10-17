"""Cloudflare Access service token contract for existing Provider router."""
from __future__ import annotations

import json
import os
from unittest import mock
import unittest

from zworkforce.config import ProviderConfig, _providers_from_env
from zworkforce.providers import OpenAICompatibleEndpoint, ProviderError, NoAccessCredentialRedirect


class Response:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, limit):
        return json.dumps({"choices": [{"message": {"role": "assistant", "content": "OK"}}]}).encode()


class FakeOpener:
    def __init__(self):
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return Response()


class CloudflareAccessTests(unittest.TestCase):
    def test_existing_provider_without_access_token_is_unchanged(self):
        provider = OpenAICompatibleEndpoint(ProviderConfig(
            name="existing", kind="openai-compatible",
            base_url="https://existing.example.net/v1", api_key="fake-provider-key",
            retries=1, models={"luna": "model-a"}))
        with mock.patch("zworkforce.providers.urllib.request.urlopen", return_value=Response()) as fetch:
            result = provider.chat("luna", [{"role": "user", "content": "hello"}], [])
        self.assertEqual(result.content, "OK")
        fetch.assert_called_once()

    def test_access_token_headers_are_forwarded_only_to_https(self):
        cfg = ProviderConfig(name="cloudflare", kind="openai-compatible",
                             base_url="https://api.example.net/v1", api_key="fake-provider-token",
                             cf_access_client_id="fake-client-id.access",
                             cf_access_client_secret="fake-client-secret",
                             models={"luna": "zeaz-free"}, retries=1)
        opener = FakeOpener()
        with mock.patch("zworkforce.providers.urllib.request.build_opener", return_value=opener) as factory, \
             mock.patch("zworkforce.providers.urllib.request.urlopen") as normal:
            result = OpenAICompatibleEndpoint(cfg).chat("luna", [{"role": "user", "content": "hi"}], [])
        self.assertEqual(result.content, "OK")
        self.assertTrue(isinstance(factory.call_args.args[0], NoAccessCredentialRedirect))
        normal.assert_not_called()
        request, _ = opener.calls[0]
        sent = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(sent["cf-access-client-id"], "fake-client-id.access")
        self.assertEqual(sent["cf-access-client-secret"], "fake-client-secret")
        self.assertEqual(sent["authorization"], "Bearer fake-provider-token")
        self.assertTrue(request.full_url.startswith("https://api.example.net/"))

    def test_access_redirect_is_rejected(self):
        handler = NoAccessCredentialRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "redirect", {}, "https://untrusted.example.net"))

    def test_incomplete_or_plaintext_access_configuration_rejected(self):
        for cfg in (
            ProviderConfig(name="partial", kind="openai-compatible", base_url="https://api.example.net/v1",
                           api_key="dummy", models={"luna": "zeaz-free"}, cf_access_client_id="only-id"),
            ProviderConfig(name="plaintext", kind="openai-compatible", base_url="http://10.0.0.10:8080/v1",
                           api_key="dummy", models={"luna": "zeaz-free"},
                           cf_access_client_id="id", cf_access_client_secret="secret"),
        ):
            with self.subTest(name=cfg.name), self.assertRaisesRegex(ProviderError, "Access"):
                OpenAICompatibleEndpoint(cfg).chat("luna", [], [])

    def test_json_config_resolves_environment_names(self):
        raw = [{"name": "cloud", "base_url": "https://api.example.net/v1",
                "api_key_env": "SAMPLE_API_KEY", "cf_access_client_id_env": "SAMPLE_ACCESS_ID",
                "cf_access_client_secret_env": "SAMPLE_ACCESS_SECRET",
                "models": {"luna": "zeaz-free"}}]
        with mock.patch.dict(os.environ, {
            "ZWORKFORCE_PROVIDERS_JSON": json.dumps(raw),
            "SAMPLE_API_KEY": "test-model-token",
            "SAMPLE_ACCESS_ID": "test-id",
            "SAMPLE_ACCESS_SECRET": "test-secret"}, clear=True):
            config = _providers_from_env("production")[0]
        self.assertEqual(config.cf_access_client_id, "test-id")
        self.assertEqual(config.cf_access_client_secret, "test-secret")
        self.assertEqual(config.api_key, "test-model-token")

    def test_partial_or_http_env_config_fails_closed(self):
        raw = [{"name": "cloud", "base_url": "https://api.example.net/v1",
                "api_key_env": "SAMPLE_API_KEY", "cf_access_client_id_env": "SAMPLE_ACCESS_ID",
                "cf_access_client_secret_env": "SAMPLE_ACCESS_SECRET",
                "models": {"luna": "zeaz-free"}}]
        base = {"ZWORKFORCE_PROVIDERS_JSON": json.dumps(raw), "SAMPLE_API_KEY": "dummy",
                "SAMPLE_ACCESS_ID": "id"}
        with mock.patch.dict(os.environ, base, clear=True), self.assertRaises(ValueError):
            _providers_from_env("production")
        raw[0]["base_url"] = "http://10.0.0.10:8080/v1"
        with mock.patch.dict(os.environ, {
            **base, "ZWORKFORCE_PROVIDERS_JSON": json.dumps(raw),
            "SAMPLE_ACCESS_SECRET": "secret"}, clear=True), self.assertRaisesRegex(ValueError, "HTTPS"):
            _providers_from_env("production")


if __name__ == "__main__":
    unittest.main()
