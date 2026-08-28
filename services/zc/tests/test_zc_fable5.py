"""tests/test_zc_fable5.py

Covers both fallback patterns documented in zc_fable5.py:
  - server-side (`fallback_chain` set -> one HTTP call, platform retries
    internally on a refusal, response echoes back which model served it)
  - legacy client-side manual retry (`fallback_chain` unset -> this
    module makes a second HTTP call itself on a refusal)
"""
import pytest

from wire.zc_fable5 import (
    FABLE5_MODEL_ID,
    Fable5Client,
    RefusalError,
    estimate_cost_usd,
    parse_fallback_chain,
)


def _response(text="ok", stop_reason="end_turn", model=None, category=None):
    data = {
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
    }
    if model:
        data["model"] = model
    if stop_reason == "refusal":
        data["stop_details"] = {"type": "refusal", "category": category, "explanation": ""}
    return data


# ── server-side fallback_chain path ─────────────────────────────────────


def test_fallback_chain_no_refusal_reports_primary_served(monkeypatch):
    client = Fable5Client(api_key="k", fallback_chain=["zc-opus-4-8"])
    monkeypatch.setattr(client, "_post", lambda payload, extra_headers=None: _response(
        text="hello", stop_reason="end_turn", model=FABLE5_MODEL_ID))

    result = client.call_with_fallback("hi")

    assert result["refused"] is False
    assert result["fell_back"] is False
    assert result["served_by"] == FABLE5_MODEL_ID
    assert result["text"] == "hello"


def test_fallback_chain_refusal_served_by_fallback_model_single_call(monkeypatch):
    calls = []

    def fake_post(payload, extra_headers=None):
        calls.append(payload)
        # Platform handled the refusal+retry server-side; the response
        # reports the fallback model actually served the request.
        return _response(text="handled by fallback", stop_reason="refusal",
                         model="zc-opus-4-8", category="cyber")

    client = Fable5Client(api_key="k", fallback_chain=["zc-opus-4-8"])
    monkeypatch.setattr(client, "_post", fake_post)

    result = client.call_with_fallback("do something risky")

    # Exactly one HTTP call -- the whole point of the server-side path.
    assert len(calls) == 1
    assert payload_has_fallbacks(calls[0])
    assert result["refused"] is True
    assert result["fell_back"] is True
    assert result["served_by"] == "zc-opus-4-8"
    assert result["classifier"] == "cyber"
    assert result["category"] == "cyber"
    assert result["text"] == "handled by fallback"


def test_fallback_chain_attached_to_call_payload():
    client = Fable5Client(api_key="k", fallback_chain=["zc-opus-4-8", "zc-xxx"])
    captured = {}

    def fake_post(payload, extra_headers=None):
        captured["payload"] = payload
        captured["headers"] = extra_headers
        return _response()

    client._post = fake_post
    client.call("hi")

    assert captured["payload"]["fallbacks"] == ["zc-opus-4-8", "zc-xxx"]
    assert captured["headers"] is None  # no fallback-credit beta on the primary call


def test_fallback_chain_not_attached_on_explicit_model_override():
    client = Fable5Client(api_key="k", fallback_chain=["zc-opus-4-8"])
    captured = {}
    client._post = lambda payload, extra_headers=None: (captured.update(payload=payload) or _response())

    client.call("hi", model="zc-xxx")

    assert "fallbacks" not in captured["payload"]


def payload_has_fallbacks(payload):
    return "fallbacks" in payload


# ── legacy client-side manual retry path ────────────────────────────────


def test_manual_retry_no_refusal_returns_primary_response(monkeypatch):
    client = Fable5Client(api_key="k")  # no fallback_chain -> legacy path
    monkeypatch.setattr(client, "_post", lambda payload, extra_headers=None: _response(text="fine"))

    result = client.call_with_fallback("hi")

    assert result["refused"] is False
    assert result["fell_back"] is False
    assert result["served_by"] == FABLE5_MODEL_ID
    assert result["text"] == "fine"


def test_manual_retry_falls_back_on_refusal_with_second_call(monkeypatch):
    client = Fable5Client(api_key="k", fallback_model="zc-opus-4-8")
    calls = []

    def fake_post(payload, extra_headers=None):
        calls.append((payload, extra_headers))
        if len(calls) == 1:
            return _response(stop_reason="refusal", category="bio")
        return _response(text="fallback answer", stop_reason="end_turn")

    monkeypatch.setattr(client, "_post", fake_post)
    result = client.call_with_fallback("risky prompt", allow_fallback=True)

    assert len(calls) == 2
    first_payload, first_headers = calls[0]
    second_payload, second_headers = calls[1]
    assert first_payload["model"] == FABLE5_MODEL_ID
    assert second_payload["model"] == "zc-opus-4-8"
    # Fallback-credit beta only sent on the manual retry call, not the primary.
    assert first_headers is None
    assert second_headers == {"anthropic-beta": "fallback-credit-2026-06-01"}

    assert result["refused"] is True
    assert result["fell_back"] is True
    assert result["served_by"] == "zc-opus-4-8"
    assert result["classifier"] == "bio"
    assert result["text"] == "fallback answer"


def test_manual_retry_raises_refusal_error_when_fallback_disabled(monkeypatch):
    client = Fable5Client(api_key="k")
    monkeypatch.setattr(client, "_post", lambda payload, extra_headers=None: _response(
        stop_reason="refusal", category="frontier_llm"))

    with pytest.raises(RefusalError) as exc_info:
        client.call_with_fallback("prompt", allow_fallback=False)

    assert exc_info.value.classifier == "frontier_llm"


def test_manual_retry_raises_refusal_error_when_no_fallback_requested_and_category_null(monkeypatch):
    # category/explanation can legitimately be null even on a refusal.
    client = Fable5Client(api_key="k")
    monkeypatch.setattr(client, "_post", lambda payload, extra_headers=None: _response(
        stop_reason="refusal", category=None))

    with pytest.raises(RefusalError) as exc_info:
        client.call_with_fallback("prompt", allow_fallback=False)

    assert exc_info.value.classifier is None


def test_manual_retry_fallback_itself_errors(monkeypatch):
    client = Fable5Client(api_key="k")
    calls = []

    def fake_post(payload, extra_headers=None):
        calls.append(payload)
        if len(calls) == 1:
            return _response(stop_reason="refusal", category="cyber")
        return {"error": "503 overloaded"}

    monkeypatch.setattr(client, "_post", fake_post)
    result = client.call_with_fallback("prompt", allow_fallback=True)

    assert result["refused"] is True
    assert result["fell_back"] is False
    assert "[ERROR on fallback]" in result["text"]


def test_primary_call_transport_error_short_circuits():
    client = Fable5Client(api_key="k")
    client._post = lambda payload, extra_headers=None: {"error": "timeout"}

    result = client.call_with_fallback("prompt")

    assert result["refused"] is False
    assert result["fell_back"] is False
    assert "[ERROR]" in result["text"]


# ── helpers unrelated to the two call paths, but part of this module ────


def test_parse_fallback_chain_splits_and_strips():
    assert parse_fallback_chain(" zc-opus-4-8 , zc-xxx ") == [
        "zc-opus-4-8", "zc-xxx"
    ]


def test_parse_fallback_chain_none_when_empty():
    assert parse_fallback_chain(None) is None
    assert parse_fallback_chain("") is None


def test_parse_fallback_chain_rejects_more_than_three():
    with pytest.raises(ValueError):
        parse_fallback_chain("m1,m2,m3,m4")


def test_estimate_cost_usd_known_model():
    cost = estimate_cost_usd(FABLE5_MODEL_ID, input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == pytest.approx(10.0 + 50.0)


def test_estimate_cost_usd_unknown_model():
    assert estimate_cost_usd("not-a-real-model", 100, 100) is None