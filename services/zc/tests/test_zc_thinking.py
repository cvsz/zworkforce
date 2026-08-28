"""tests/test_zc_thinking.py

Covers zc_thinking.py's v1.25.0 addition (thinking.display="omitted",
GA, no beta header) and its v1.30.0 rewrite: real adaptive-thinking
routing (thinking.type="adaptive" + top-level output_config.effort, no
budget_tokens) vs. the legacy manual budget_tokens path, auto-selected
per model. See docs/42_upgrade_v1.30.0.md for the full audit — before
this fix, --thinking always sent manual budget_tokens, which is a 400
error on every current-generation model except Opus 4.5 and Haiku 4.5.
"""
import sys
import types
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def thinking_mod(monkeypatch):
    fake_anthropic = types.ModuleType("anthropic")

    class _FakeClient:
        def __init__(self, api_key=None):
            self.messages = MagicMock()

    fake_anthropic.Anthropic = _FakeClient
    monkeypatch.setitem(sys.modules, "anthropic", fake_anthropic)

    import importlib

    import wire.zc_thinking as mod
    importlib.reload(mod)
    return mod


def _fake_message_response():
    resp = MagicMock()
    resp.content = []
    resp.usage = MagicMock()
    resp.usage.model_dump = lambda: {}
    return resp


# ── display_omitted (pre-existing v1.25.0 behaviour, still correct) ────────

def test_generate_with_thinking_display_omitted_sets_field(thinking_mod):
    tc = thinking_mod.ThinkingCoder(api_key="sk-test", model="zc-opus-4-5")
    tc.client.messages.create.return_value = _fake_message_response()

    tc.generate_with_thinking("q", display_omitted=True)

    _, kwargs = tc.client.messages.create.call_args
    assert kwargs["thinking"]["display"] == "omitted"


def test_generate_with_thinking_display_omitted_default_false_no_regression(thinking_mod):
    tc = thinking_mod.ThinkingCoder(api_key="sk-test", model="zc-opus-4-5")
    tc.client.messages.create.return_value = _fake_message_response()

    tc.generate_with_thinking("q")

    _, kwargs = tc.client.messages.create.call_args
    assert "display" not in kwargs["thinking"]


# ── v1.30.0: model-aware adaptive/legacy routing ───────────────────────────

def test_adaptive_capable_model_auto_selects_adaptive(thinking_mod):
    """Regression test for the core v1.30.0 bug: a bare --thinking on a
    current-gen model must not send budget_tokens (400 on these models)."""
    tc = thinking_mod.ThinkingCoder(api_key="sk-test", model="zc-xxx")
    tc.client.messages.create.return_value = _fake_message_response()

    tc.generate_with_thinking("q")

    _, kwargs = tc.client.messages.create.call_args
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert "budget_tokens" not in kwargs["thinking"]
    assert kwargs["output_config"] == {"effort": "high"}


def test_adaptive_mode_sends_effort_in_output_config_not_thinking(thinking_mod):
    tc = thinking_mod.ThinkingCoder(api_key="sk-test", model="zc-opus-4-8")
    tc.client.messages.create.return_value = _fake_message_response()

    tc.generate_with_thinking("q", effort="low")

    _, kwargs = tc.client.messages.create.call_args
    assert kwargs["output_config"] == {"effort": "low"}
    assert kwargs["thinking"] == {"type": "adaptive"}


def test_manual_only_model_auto_selects_legacy_budget(thinking_mod):
    tc = thinking_mod.ThinkingCoder(api_key="sk-test", model="zc-opus-4-5")
    tc.client.messages.create.return_value = _fake_message_response()

    tc.generate_with_thinking("q", budget_tokens=8_000)

    _, kwargs = tc.client.messages.create.call_args
    assert kwargs["thinking"] == {"type": "enabled", "budget_tokens": 8_000}
    assert "output_config" not in kwargs


def test_effort_legacy_budget_forces_manual_on_deprecated_but_supported_model(thinking_mod):
    """Opus 4.6 / Sonnet 4.6: budget_tokens is deprecated but still
    accepted, so --effort-legacy-budget should be allowed to force it."""
    tc = thinking_mod.ThinkingCoder(api_key="sk-test", model="zc-sonnet-4-6")
    tc.client.messages.create.return_value = _fake_message_response()

    tc.generate_with_thinking("q", effort="high", legacy_budget=True)

    _, kwargs = tc.client.messages.create.call_args
    assert kwargs["thinking"]["type"] == "enabled"
    assert kwargs["thinking"]["budget_tokens"] == thinking_mod.EFFORT_BUDGETS["high"]


def test_effort_legacy_budget_refuses_on_hard_400_model(thinking_mod):
    """Opus 4.7/4.8, Sonnet 5, Fable 5, Mythos 5: budget_tokens is a hard
    400 — --effort-legacy-budget must fail fast with a clear message,
    never send the doomed request."""
    tc = thinking_mod.ThinkingCoder(api_key="sk-test", model="zc-xxx")

    with pytest.raises(thinking_mod.ThinkingModeError, match="budget_tokens is not accepted"):
        tc.generate_with_thinking("q", legacy_budget=True)

    tc.client.messages.create.assert_not_called()


def test_explicit_adaptive_true_on_manual_only_model_raises(thinking_mod):
    tc = thinking_mod.ThinkingCoder(api_key="sk-test", model="zc-haiku-4-5-20251001")

    with pytest.raises(thinking_mod.ThinkingModeError, match="doesn't support adaptive"):
        tc.generate_with_thinking("q", adaptive=True)


def test_explicit_adaptive_false_with_legacy_budget_raises_on_hard_400_model(thinking_mod):
    tc = thinking_mod.ThinkingCoder(api_key="sk-test", model="zc-xxx")
    tc.client.messages.create.return_value = _fake_message_response()

    # adaptive=False + legacy_budget=True on Sonnet 5 (a hard-400 model
    # for budget_tokens) must raise via the same guard as legacy_budget
    # alone would.
    with pytest.raises(thinking_mod.ThinkingModeError):
        tc.generate_with_thinking("q", adaptive=False, legacy_budget=True)


def test_streaming_uses_same_adaptive_routing(thinking_mod):
    tc = thinking_mod.ThinkingCoder(api_key="sk-test", model="zc-xxx")

    class _FakeStreamCtx:
        def __enter__(self):
            return iter([])

        def __exit__(self, *a):
            return False

    tc.client.messages.stream = MagicMock(return_value=_FakeStreamCtx())

    tc.stream_with_thinking("q", effort="max")

    _, kwargs = tc.client.messages.stream.call_args
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["output_config"] == {"effort": "max"}


# ── routing helper functions ────────────────────────────────────────────

def test_supports_adaptive_thinking_matrix(thinking_mod):
    for model in ("zc-xxx", "zc-opus-4-8", "zc-opus-4-7",
                   "zc-mythos-5", "zc-fable-5",
                   "zc-opus-4-6", "zc-sonnet-4-6"):
        assert thinking_mod.supports_adaptive_thinking(model), model
    for model in ("zc-opus-4-5", "zc-haiku-4-5-20251001", "zc-sonnet-4-5"):
        assert not thinking_mod.supports_adaptive_thinking(model), model


def test_supports_manual_budget_tokens_matrix(thinking_mod):
    for model in ("zc-opus-4-8", "zc-opus-4-7", "zc-xxx",
                   "zc-mythos-5", "zc-fable-5"):
        assert not thinking_mod.supports_manual_budget_tokens(model), model
    for model in ("zc-opus-4-6", "zc-sonnet-4-6", "zc-opus-4-5",
                   "zc-haiku-4-5-20251001"):
        assert thinking_mod.supports_manual_budget_tokens(model), model


# ── cmd_thinking wiring ─────────────────────────────────────────────────

def test_cmd_thinking_threads_display_omitted(thinking_mod, monkeypatch):
    captured = {}

    class FakeCoder:
        def __init__(self, api_key, model):
            pass

        def _resolve_mode(self, adaptive, legacy_budget):
            return True

        def generate_with_thinking(self, prompt, **kwargs):
            captured.update(kwargs)
            return {"response": "ok", "usage": {}}

    monkeypatch.setattr(thinking_mod, "ThinkingCoder", FakeCoder)

    thinking_mod.cmd_thinking(
        "q", api_key="sk-test", model="zc-xxx", budget=8000,
        effort=None, adaptive=None, show_thinking=False, stream=False,
        display_omitted=True,
    )

    assert captured["display_omitted"] is True


def test_cmd_thinking_threads_legacy_budget_flag(thinking_mod, monkeypatch):
    captured = {}

    class FakeCoder:
        def __init__(self, api_key, model):
            pass

        def _resolve_mode(self, adaptive, legacy_budget):
            return not legacy_budget

        def generate_with_thinking(self, prompt, **kwargs):
            captured.update(kwargs)
            return {"response": "ok", "usage": {}}

    monkeypatch.setattr(thinking_mod, "ThinkingCoder", FakeCoder)

    thinking_mod.cmd_thinking(
        "q", api_key="sk-test", model="zc-opus-4-5", budget=8000,
        effort=None, adaptive=None, show_thinking=False, stream=False,
        legacy_budget=True,
    )

    assert captured["legacy_budget"] is True


def test_cmd_thinking_reads_correct_thinking_tokens_usage_field(thinking_mod, monkeypatch, capsys):
    """Regression test: the old code read usage['thinking_input_tokens'],
    which doesn't exist in the real API response shape and always printed
    0. The real field is usage['output_tokens_details']['thinking_tokens']."""
    class FakeCoder:
        def __init__(self, api_key, model):
            pass

        def _resolve_mode(self, adaptive, legacy_budget):
            return True

        def generate_with_thinking(self, prompt, **kwargs):
            return {
                "response": "the answer",
                "usage": {
                    "input_tokens": 25,
                    "output_tokens": 348,
                    "output_tokens_details": {"thinking_tokens": 312},
                },
            }

    monkeypatch.setattr(thinking_mod, "ThinkingCoder", FakeCoder)

    thinking_mod.cmd_thinking(
        "q", api_key="sk-test", model="zc-xxx", budget=8000,
        effort=None, adaptive=None, show_thinking=False, stream=False,
    )

    out = capsys.readouterr().out
    assert "thinking=312" in out
