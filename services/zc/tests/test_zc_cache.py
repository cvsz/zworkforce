"""tests/test_zc_cache.py

Covers zc_cache.py's three features:
  - explicit cache breakpoints / basic generate_cached()
  - Cache diagnostics (beta): diagnose=True threading and cache_miss_reason
    surfaced through cache_stats()
  - Mid-conversation system messages (v1.18.0): build_mid_system_message(),
    validate_system_message_placement(), and the model gate on
    generate_cached()/multi_turn_cached()

Previously this module (zc_cache.py) had zero test coverage at all.
"""
import pytest

from wire.zc_cache import (
    MID_SYSTEM_SUPPORTED_MODELS,
    CachingCoder,
    SystemMessagePlacementError,
    build_mid_system_message,
    validate_system_message_placement,
)


def _response(text="ok", usage=None, diagnostics=None, message_id="msg_1"):
    data = {
        "id": message_id,
        "content": [{"type": "text", "text": text}],
        "usage": usage or {"input_tokens": 10, "output_tokens": 5,
                            "cache_creation_input_tokens": 0,
                            "cache_read_input_tokens": 0},
    }
    if diagnostics is not None:
        data["diagnostics"] = diagnostics
    return data


# ── basic caching ────────────────────────────────────────────────────────


def test_generate_cached_returns_text(monkeypatch):
    cc = CachingCoder(api_key="k", model="zc-xxx")
    monkeypatch.setattr(cc, "_post", lambda payload, diagnose=False: _response("hello"))

    result = cc.generate_cached("hi", system="be nice")

    assert result == "hello"


def test_generate_cached_caches_system_and_docs(monkeypatch):
    captured = {}

    def fake_post(payload, diagnose=False):
        captured["payload"] = payload
        return _response("ok")

    cc = CachingCoder(api_key="k", model="zc-xxx")
    monkeypatch.setattr(cc, "_post", fake_post)

    cc.generate_cached("hi", system="sys prompt", cached_docs=["doc one"])

    payload = captured["payload"]
    assert payload["system"][0]["cache_control"] == {"type": "ephemeral"}
    user_blocks = payload["messages"][0]["content"]
    assert user_blocks[0]["text"] == "doc one"
    assert user_blocks[0]["cache_control"] == {"type": "ephemeral"}


# ── Cache diagnostics (beta) ─────────────────────────────────────────────


def test_diagnose_sends_previous_message_id_none_on_first_call(monkeypatch):
    captured = {}

    def fake_post(payload, diagnose=False):
        captured["payload"] = payload
        captured["diagnose"] = diagnose
        return _response("ok", diagnostics=None, message_id="msg_1")

    cc = CachingCoder(api_key="k", model="zc-xxx")
    monkeypatch.setattr(cc, "_post", fake_post)

    cc.generate_cached("hi", diagnose=True)

    assert captured["diagnose"] is True
    assert captured["payload"]["diagnostics"] == {"previous_message_id": None}


def test_diagnose_second_call_references_prior_message_id_and_surfaces_miss_reason(monkeypatch):
    calls = []

    def fake_post(payload, diagnose=False):
        calls.append(payload)
        if len(calls) == 1:
            return _response("first", message_id="msg_1")
        return _response(
            "second", message_id="msg_2",
            diagnostics={"cache_miss_reason": {"type": "system_changed"}},
        )

    cc = CachingCoder(api_key="k", model="zc-xxx")
    monkeypatch.setattr(cc, "_post", fake_post)

    cc.generate_cached("first turn", diagnose=True)
    cc.generate_cached("second turn", diagnose=True)

    assert calls[1]["diagnostics"] == {"previous_message_id": "msg_1"}
    assert cc.cache_stats()["cache_miss_reason"] == "system_changed"


def test_diagnose_adds_beta_header(monkeypatch):

    cc = CachingCoder(api_key="k", model="zc-xxx")
    captured = {}

    def fake_call(req):
        captured["headers"] = dict(req.headers)
        return _response("ok")

    monkeypatch.setattr(cc, "_call", fake_call)
    cc._post({"model": "zc-xxx"}, diagnose=True)

    # urllib.request.Request title-cases header keys
    assert "cache-diagnosis-2026-04-07" in captured["headers"]["Anthropic-beta"]


# ── Mid-conversation system messages ─────────────────────────────────────


def test_build_mid_system_message_shape():
    msg = build_mid_system_message("new instruction")
    assert msg == {"role": "system", "content": [{"type": "text", "text": "new instruction"}]}


def test_validate_placement_rejects_system_as_first_message():
    messages = [build_mid_system_message("x")]
    with pytest.raises(SystemMessagePlacementError, match="first entry"):
        validate_system_message_placement(messages)


def test_validate_placement_rejects_consecutive_system_messages():
    messages = [
        {"role": "user", "content": "hi"},
        build_mid_system_message("a"),
        build_mid_system_message("b"),
    ]
    with pytest.raises(SystemMessagePlacementError, match="adjacent"):
        validate_system_message_placement(messages)


def test_validate_placement_rejects_after_assistant_without_server_tool_use():
    messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        build_mid_system_message("x"),
    ]
    with pytest.raises(SystemMessagePlacementError, match="server tool use"):
        validate_system_message_placement(messages)


def test_validate_placement_allows_after_assistant_server_tool_use():
    messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": [{"type": "server_tool_use", "id": "t1"}]},
        build_mid_system_message("x"),
    ]
    validate_system_message_placement(messages)  # should not raise


def test_validate_placement_rejects_between_tool_use_and_tool_result():
    messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1"}]},
        build_mid_system_message("x"),
    ]
    with pytest.raises(SystemMessagePlacementError, match="tool_use"):
        validate_system_message_placement(messages)


def test_validate_placement_rejects_followed_by_non_assistant():
    messages = [
        {"role": "user", "content": "hi"},
        build_mid_system_message("x"),
        {"role": "user", "content": "another user turn"},
    ]
    with pytest.raises(SystemMessagePlacementError, match="last entry"):
        validate_system_message_placement(messages)


def test_validate_placement_allows_as_last_entry():
    messages = [
        {"role": "user", "content": "hi"},
        build_mid_system_message("x"),
    ]
    validate_system_message_placement(messages)  # should not raise


def test_generate_cached_mid_system_rejects_unsupported_model(monkeypatch):
    cc = CachingCoder(api_key="k", model="zc-xxx")
    monkeypatch.setattr(cc, "_post", lambda payload, diagnose=False: _response("ok"))

    with pytest.raises(ValueError, match="zc-opus-4-8"):
        cc.generate_cached("hi", history=[{"role": "user", "content": "prior"}],
                           mid_system="update")


def test_generate_cached_mid_system_appends_message_on_supported_model(monkeypatch):
    captured = {}

    def fake_post(payload, diagnose=False):
        captured["payload"] = payload
        return _response("ok")

    cc = CachingCoder(api_key="k", model="zc-opus-4-8")
    monkeypatch.setattr(cc, "_post", fake_post)

    cc.generate_cached("hi", history=[{"role": "user", "content": "prior"}],
                       mid_system="update instructions")

    messages = captured["payload"]["messages"]
    assert messages[1] == build_mid_system_message("update instructions")


def test_multi_turn_cached_mid_system_update(monkeypatch):
    calls = []

    def fake_post(payload, diagnose=False):
        calls.append([m.get("role") for m in payload["messages"]])
        return _response(f"reply {len(calls)}")

    cc = CachingCoder(api_key="k", model="zc-opus-4-8")
    monkeypatch.setattr(cc, "_post", fake_post)

    responses = cc.multi_turn_cached(
        ["turn one", "turn two"],
        mid_system_updates={0: "mid-conversation update"},
    )

    assert responses == ["reply 1", "reply 2"]
    # After turn 0: [user] then system appended -> ["user", "system"]
    assert calls[0] == ["user", "system"]
    # Turn 1's request includes the full history including the system msg
    assert calls[1] == ["user", "system", "assistant", "user"]


def test_multi_turn_cached_mid_system_rejects_unsupported_model():
    cc = CachingCoder(api_key="k", model="zc-xxx")
    with pytest.raises(ValueError, match="zc-opus-4-8"):
        cc.multi_turn_cached(["a", "b"], mid_system_updates={0: "x"})


def test_mid_system_supported_models_is_opus_4_8_only():
    assert MID_SYSTEM_SUPPORTED_MODELS == {"zc-opus-4-8"}
