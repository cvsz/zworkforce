"""tests/test_tui.py — tui.py (the --tui Textual front end).

Runs Textual's headless test harness (App.run_test()) so no real terminal
is needed. Every test is skipped, not failed, if `textual` isn't
installed, matching how tests for other optional-dependency modules
(zc_excel.py/zc_powerpoint.py) handle the same situation — see
tests/test_config.py's pattern for the equivalent skip-if-missing idiom.
"""
import pytest

textual = pytest.importorskip("textual", reason="optional dependency for --tui, see requirements.txt")

import wire.tui as tui  # noqa: E402


@pytest.mark.asyncio
async def test_compose_builds_sidebar_and_transcript():
    app = tui.wireTUI(api_key="test-key")
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#sidebar") is not None
        assert app.query_one("#transcript") is not None
        assert app.query_one("#prompt_input") is not None


@pytest.mark.asyncio
async def test_missing_api_key_shows_error_message():
    app = tui.wireTUI(api_key="")
    async with app.run_test() as pilot:
        await pilot.pause()
        transcript = app.query_one("#transcript")
        texts = [c.raw_text for c in transcript.children if isinstance(c, tui.ChatMessage)]
        assert any("ANTHROPIC_API_KEY" in t for t in texts)


@pytest.mark.asyncio
async def test_submitting_prompt_adds_user_and_assistant_messages(monkeypatch):
    # Keep the UI test hermetic and avoid leaving a provider worker running
    # after Textual's test harness exits. Generation has its own unit tests.
    def fake_generation(self, prompt, model, system, temperature, streaming, reply_widget):
        reply_widget.update_text("mock assistant reply")

    monkeypatch.setattr(tui.wireTUI, "_run_generation", fake_generation)
    app = tui.wireTUI(api_key="test-key")
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#prompt_input").value = "hello there"
        await pilot.press("enter")
        await pilot.pause(0.2)
        transcript = app.query_one("#transcript")
        roles = [c.role for c in transcript.children if isinstance(c, tui.ChatMessage)]
        assert "user" in roles
        assert "assistant" in roles


@pytest.mark.asyncio
async def test_new_session_clears_transcript_and_history():
    app = tui.wireTUI(api_key="test-key")
    async with app.run_test() as pilot:
        await pilot.pause()
        app.history = [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]
        app.action_new_session()
        await pilot.pause()
        assert app.history == []
        transcript = app.query_one("#transcript")
        assert len(transcript.children) == 1  # just the "new session started" system message


@pytest.mark.asyncio
async def test_build_system_prompt_combines_agent_skill_personality():
    app = tui.wireTUI(api_key="test-key")
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#agent_select").value = "code_reviewer"
        app.query_one("#skill_select").value = "testing"
        app.query_one("#personality_select").value = "precise"
        prompt = app._build_system_prompt()
        assert "code review agent" in prompt
        assert "testing" in prompt
        assert "concise" in prompt.lower()


@pytest.mark.asyncio
async def test_temperature_falls_back_to_default_on_bad_input():
    app = tui.wireTUI(api_key="test-key")
    async with app.run_test() as pilot:
        await pilot.pause()
        temp_input = app.query_one("#temp_input")
        temp_input.value = "not-a-number"
        assert app._temperature() == 0.3
        temp_input.value = "5.0"  # out of 0..1 range
        assert app._temperature() == 1.0


def test_run_tui_entry_point_exists():
    assert callable(tui.run_tui)


def test_streamed_reply_shows_full_text_even_when_gated(monkeypatch):
    """A fast, short stream must flush its final unpainted deltas."""
    import sys
    import types

    class Delta:
        type = "text_delta"

        def __init__(self, text):
            self.text = text

    class Event:
        type = "content_block_delta"

        def __init__(self, text):
            self.delta = Delta(text)

    class Stream:
        def __enter__(self):
            return iter([Event("Hi"), Event(" there"), Event("!")])

        def __exit__(self, *args):
            return False

    class Messages:
        def stream(self, **kwargs):
            return Stream()

    class Client:
        def __init__(self, **kwargs):
            self.messages = Messages()

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Client))
    monkeypatch.setattr(tui.time, "monotonic", lambda: 1.0)

    updates = []
    transcript = types.SimpleNamespace(scroll_end=lambda **kwargs: None)
    owner = types.SimpleNamespace(
        api_key="test-key",
        call_from_thread=lambda callback, *args, **kwargs: callback(*args, **kwargs),
        query_one=lambda selector: transcript,
    )
    widget = types.SimpleNamespace(update_text=updates.append)

    result = tui.wireTUI._stream_reply(owner, "hello", "test", None, 0.3, [], widget)

    assert result == "Hi there!"
    assert updates == ["Hi", "Hi there!"]


def test_import_error_message_is_actionable_when_textual_missing(monkeypatch):
    # Simulate the "not installed" path without actually uninstalling
    # textual -- checks tui.py's own guard message stays informative.
    import importlib
    import sys as _sys
    real_textual = _sys.modules.get("textual")
    _sys.modules["textual"] = None  # forces an ImportError on next import
    for mod in list(_sys.modules):
        if mod == "wire.tui" or mod.startswith("wire.tui."):
            del _sys.modules[mod]
    try:
        with pytest.raises(ImportError, match="pip install textual"):
            importlib.import_module("wire.tui")
    finally:
        if real_textual is not None:
            _sys.modules["textual"] = real_textual
        else:
            _sys.modules.pop("textual", None)
        for mod in list(_sys.modules):
            if mod == "wire.tui" or mod.startswith("wire.tui."):
                del _sys.modules[mod]
        importlib.import_module("wire.tui")
