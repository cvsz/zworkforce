"""tests/test_coder.py — Coder.generate() with urllib.request.urlopen mocked out.

No real network calls are made anywhere in this file.
"""
import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

import wire.resilience as resilience
from wire.coder import Coder


@pytest.fixture(autouse=True)
def fresh_breaker(monkeypatch):
    """Give every test its own circuit breaker so failures in one test
    don't trip the breaker for the next one."""
    monkeypatch.setattr("wire.coder._default_breaker", resilience.CircuitBreaker(failure_threshold=10, reset_timeout=0.01))


def _fake_response(payload: dict):
    body = json.dumps(payload).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


def test_generate_returns_error_without_api_key():
    c = Coder(api_key="", model="zc-xxx")
    result = c.generate("hello")
    assert "[ERROR]" in result
    assert "API key" in result


def test_generate_concatenates_multiple_text_blocks():
    c = Coder(api_key="sk-ant-test", model="zc-xxx")
    payload = {"content": [{"type": "thinking", "thinking": "..."},
                            {"type": "text", "text": "Hello "},
                            {"type": "text", "text": "world"}]}
    with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
        result = c.generate("hi")
    assert result == "Hello world"


def test_generate_handles_refusal():
    c = Coder(api_key="sk-ant-test", model="zc-xxx")
    payload = {"content": [], "stop_reason": "refusal"}
    with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
        result = c.generate("hi")
    assert result == "[REFUSED] Model declined this request."


def test_generate_no_sampling_params_for_sonnet5():
    c = Coder(api_key="sk-ant-test", model="zc-xxx", temperature=0.9)
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["payload"] = json.loads(req.data.decode())
        return _fake_response({"content": [{"type": "text", "text": "ok"}]})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        c.generate("hi")
    assert "temperature" not in captured["payload"]


def test_generate_401_does_not_retry():
    c = Coder(api_key="sk-ant-bad", model="zc-xxx")
    call_count = {"n": 0}

    def raise_401(req, timeout=None):
        call_count["n"] += 1
        raise urllib.error.HTTPError(url="", code=401, msg="unauthorized",
                                      hdrs=None, fp=io.BytesIO(b'{"error":"bad key"}'))

    with patch("urllib.request.urlopen", side_effect=raise_401):
        result = c.generate("hi")
    assert "[API ERROR 401]" in result
    assert call_count["n"] == 1  # auth errors are not retryable


def test_generate_500_retries_then_succeeds():
    c = Coder(api_key="sk-ant-test", model="zc-xxx")
    call_count = {"n": 0}

    def flaky(req, timeout=None):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise urllib.error.HTTPError(url="", code=503, msg="unavailable",
                                          hdrs=None, fp=io.BytesIO(b"{}"))
        return _fake_response({"content": [{"type": "text", "text": "recovered"}]})

    with patch("urllib.request.urlopen", side_effect=flaky), \
         patch("time.sleep", return_value=None):
        result = c.generate("hi")
    assert result == "recovered"
    assert call_count["n"] == 3


def test_generate_429_exhausts_retries_returns_error():
    c = Coder(api_key="sk-ant-test", model="zc-xxx")

    def always_429(req, timeout=None):
        raise urllib.error.HTTPError(url="", code=429, msg="rate limited",
                                      hdrs=None, fp=io.BytesIO(b"{}"))

    with patch("urllib.request.urlopen", side_effect=always_429), \
         patch("time.sleep", return_value=None):
        result = c.generate("hi")
    assert "[API ERROR 429]" in result
