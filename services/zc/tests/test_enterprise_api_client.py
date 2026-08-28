"""Tests for the legacy CLI's enterprise API transport."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from wire.api_client import EnterpriseAPIClient, EnterpriseAPIError


class FakeHTTPResponse:
    """Context-managed response compatible with urllib."""

    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_client_is_disabled_without_api_url(monkeypatch) -> None:
    monkeypatch.delenv("ZC_API_URL", raising=False)
    monkeypatch.delenv("ZC_API_TOKEN", raising=False)

    assert EnterpriseAPIClient.from_env() is None


def test_client_requires_gateway_token(monkeypatch) -> None:
    monkeypatch.setenv("ZC_API_URL", "http://localhost:8420")
    monkeypatch.delenv("ZC_API_TOKEN", raising=False)

    with pytest.raises(EnterpriseAPIError, match="ZC_API_TOKEN"):
        EnterpriseAPIClient.from_env()


def test_client_returns_output_text(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.headers["Authorization"]
        captured["timeout"] = timeout
        return FakeHTTPResponse({"data": {"output_text": "done"}})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = EnterpriseAPIClient("http://api.internal", "gateway-token")

    result = client.create_response({"prompt": "hello"})

    assert result == "done"
    assert captured["url"] == "http://api.internal/v1/ai/responses"
    assert captured["authorization"] == "Bearer gateway-token"


def test_client_maps_structured_api_error(monkeypatch) -> None:
    def fake_urlopen(_request, timeout):
        del timeout
        raise urllib.error.HTTPError(
            "http://api.internal/v1/ai/responses",
            502,
            "Bad Gateway",
            {},
            io.BytesIO(
                json.dumps(
                    {
                        "error": {
                            "code": "provider_error",
                            "message": "Provider unavailable",
                        }
                    }
                ).encode("utf-8")
            ),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = EnterpriseAPIClient("http://api.internal", "gateway-token")

    with pytest.raises(EnterpriseAPIError, match="Provider unavailable"):
        client.create_response({"prompt": "hello"})
