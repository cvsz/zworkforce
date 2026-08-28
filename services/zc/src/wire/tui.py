"""
tui.py — Full interactive terminal UI for wire, built on Textual.

Launched via `python main.py --tui` (see main.py). This is a second front
end alongside the plain-argparse CLI and the FastAPI web console
(webapp/), reusing the exact same core the other two do:

    coder.Coder               -> chat/generation (streamed, via the
                                  anthropic SDK -- same shape as
                                  zc_stream.StreamCoder)
    personalities.py          -> PersonalityManager
    skills.py                 -> SkillManager
    zc_models.py          -> MODEL_CATALOG
    main.py                   -> AGENT_SYSTEM_PROMPTS, VERSION
    config.py                 -> Config (persisted to ~/.ai-coder-config.json)

No business logic lives here -- this module is purely presentation, same
principle webapp/backend/server.py documents for itself.

`textual` is an optional dependency (see requirements.txt): importing
this module raises a clear, actionable ImportError if it isn't
installed, rather than an ugly traceback, matching the pattern used by
zc_excel.py / zc_powerpoint.py for their own optional deps.
"""
from __future__ import annotations

import time

try:
    from textual import work
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.widgets import (
        Button,
        Footer,
        Header,
        Input,
        Label,
        Select,
        Static,
        Switch,
    )
    from textual.worker import Worker, get_current_worker
except ImportError as e:  # pragma: no cover - exercised only w/o textual installed
    raise ImportError(
        "The --tui flag needs the 'textual' package, which isn't installed.\n"
        "Install it with:  pip install textual>=0.80.0\n"
        "(or: pip install -r requirements.txt, it's an optional extra there)"
    ) from e

from wire.zc_models import MODEL_CATALOG
from wire.config import Config
from wire.personalities import PersonalityManager
from wire.skills import SkillManager
from wire.tui_streaming import StreamRenderGate

DEFAULT_MODEL = "zc-xxx"


def _agent_prompts() -> dict:
    # Imported lazily (not at module scope) to avoid a circular import --
    # main.py imports tui.py to wire up --tui, so tui.py can't import
    # main.py at module load time.
    from wire.main import AGENT_SYSTEM_PROMPTS
    return AGENT_SYSTEM_PROMPTS


class ChatMessage(Static):
    """A single rendered turn in the transcript."""

    def __init__(self, role: str, text: str = ""):
        super().__init__(self._format(role, text), markup=False)
        self.role = role
        self.raw_text = text
        self.add_class(f"msg-{role}")

    @staticmethod
    def _format(role: str, text: str) -> str:
        sym = {"user": "$", "assistant": ">", "error": "!", "system": "·"}.get(role, ">")
        return f"{sym} {text}"

    def update_text(self, text: str) -> None:
        self.raw_text = text
        self.update(self._format(self.role, text))


class SessionSidebar(Vertical):
    """Left-hand control panel: model / personality / agent / skill /
    temperature / streaming toggle. Mirrors webapp/frontend's sidebar so
    the two front ends stay conceptually in sync."""

    def compose(self) -> ComposeResult:
        model_options = [
            (f"{info.get('display_name', mid)} ({info.get('tier', '')})", mid)
            for mid, info in MODEL_CATALOG.items()
        ]
        personality_options = [("none", "")] + [
            (p["name"], p["name"]) for p in PersonalityManager().list_personalities()
        ]
        agent_options = [("none", "")] + [
            (name, name) for name in _agent_prompts().keys()
        ]
        skill_options = [("none", "")] + [
            (s["name"], s["name"]) for s in SkillManager().list_skills()
        ]

        yield Label("model", classes="side-label")
        yield Select(model_options, value=DEFAULT_MODEL, id="model_select")
        yield Label("personality", classes="side-label")
        yield Select(personality_options, value="", id="personality_select")
        yield Label("agent role", classes="side-label")
        yield Select(agent_options, value="", id="agent_select")
        yield Label("skill focus", classes="side-label")
        yield Select(skill_options, value="", id="skill_select")
        yield Label("temperature: 0.3", id="temp_label", classes="side-label")
        yield Input(value="0.3", id="temp_input", placeholder="0.0 - 1.0")
        with Horizontal(classes="stream-row"):
            yield Label("stream", classes="side-label")
            yield Switch(value=True, id="stream_switch")


class wireTUI(App):
    """Interactive chat TUI. Same request semantics as the CLI's
    --interactive REPL and the web console's /api/chat[/stream], just a
    third surface for the same underlying Coder calls."""

    CSS = """
    Screen { layout: horizontal; }
    #sidebar {
        width: 32;
        border-right: solid $panel-darken-2;
        padding: 1 2;
        overflow-y: auto;
    }
    #main { width: 1fr; }
    #transcript { padding: 1 2; }
    .side-label { color: $text-muted; text-style: bold; margin-top: 1; }
    .stream-row { height: 3; align: left middle; }
    #input_row { height: 3; dock: bottom; padding: 0 1; }
    #prompt_input { width: 1fr; }
    .msg-user { color: $accent; margin: 1 0 0 0; }
    .msg-assistant { color: $success; margin: 1 0 0 0; }
    .msg-error { color: $error; margin: 1 0 0 0; }
    .msg-system { color: $text-muted; margin: 1 0 0 0; }
    """

    BINDINGS = [
        ("ctrl+n", "new_session", "New session"),
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+t", "toggle_dark", "Toggle theme"),
    ]

    def __init__(self, api_key: str | None = None):
        super().__init__()
        self.api_key = api_key or Config().get("api_key")
        self.history: list = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with SessionSidebar(id="sidebar"):
                pass
            with Vertical(id="main"):
                yield VerticalScroll(id="transcript")
                with Horizontal(id="input_row"):
                    yield Input(placeholder="Ask ai-coder anything…  (Enter to send)", id="prompt_input")
                    yield Button("run", id="send_btn", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#transcript").mount(
            ChatMessage("system", "ai-coder TUI ready. Same Coder core as the CLI and web console.")
        )
        if not self.api_key:
            self.query_one("#transcript").mount(
                ChatMessage("error", "No ANTHROPIC_API_KEY configured — set the env var, run "
                                       "`python main.py --setup`, or restart with --api-key.")
            )
        self.query_one("#prompt_input").focus()

    def action_new_session(self) -> None:
        self.history = []
        transcript = self.query_one("#transcript")
        transcript.remove_children()
        transcript.mount(ChatMessage("system", "new session started."))

    def action_toggle_dark(self) -> None:
        # textual >= 0.80 replaced the boolean `.dark` attribute with a
        # named `theme` property; toggle between the two builtin themes
        # rather than relying on the removed attribute.
        self.theme = "textual-light" if self.theme == "textual-dark" else "textual-dark"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "prompt_input":
            self._send()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send_btn":
            self._send()

    def _selected(self, widget_id: str) -> str:
        val = self.query_one(f"#{widget_id}", Select).value
        return str(val) if val not in (None, Select.BLANK) else ""

    def _temperature(self) -> float:
        raw = self.query_one("#temp_input", Input).value.strip()
        try:
            t = float(raw)
        except ValueError:
            t = 0.3
        return max(0.0, min(1.0, t))

    def _build_system_prompt(self) -> str | None:
        parts = []
        agent = self._selected("agent_select")
        if agent:
            parts.append(_agent_prompts().get(agent, ""))
        skill = self._selected("skill_select")
        if skill:
            info = SkillManager().get_skill(skill)
            if info:
                parts.append(f"Apply the '{info['name']}' skill: {info['description']}")
        personality = self._selected("personality_select")
        if personality:
            parts.append(PersonalityManager().build_prompt_addition(personality))
        return "\n\n".join(p for p in parts if p) or None

    def _send(self) -> None:
        prompt_input = self.query_one("#prompt_input", Input)
        text = prompt_input.value.strip()
        if not text or not self.api_key:
            return
        prompt_input.value = ""
        transcript = self.query_one("#transcript")
        transcript.mount(ChatMessage("user", text))
        transcript.scroll_end(animate=False)

        model = self._selected("model_select") or DEFAULT_MODEL
        system = self._build_system_prompt()
        temperature = self._temperature()
        streaming = self.query_one("#stream_switch", Switch).value

        reply_widget = ChatMessage("assistant", "…")
        transcript.mount(reply_widget)
        transcript.scroll_end(animate=False)

        self._run_generation(text, model, system, temperature, streaming, reply_widget)

    @work(exclusive=False, thread=True)
    def _run_generation(self, prompt, model, system, temperature, streaming, reply_widget) -> None:
        history_snapshot = list(self.history)
        try:
            if streaming:
                full_text = self._stream_reply(prompt, model, system, temperature, history_snapshot, reply_widget)
            else:
                from wire.coder import Coder
                coder = Coder(api_key=self.api_key, model=model, temperature=temperature)
                full_text = coder.generate(prompt, system=system, history=history_snapshot)
                self.call_from_thread(reply_widget.update_text, full_text)
        except Exception as e:  # keep the TUI alive on any generation failure
            full_text = f"[ERROR] {e}"
            self.call_from_thread(reply_widget.update_text, full_text)
            self.call_from_thread(reply_widget.add_class, "msg-error")

        self.history = history_snapshot + [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": full_text},
        ]

    def _stream_reply(self, prompt, model, system, temperature, history, reply_widget) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        messages = list(history) + [{"role": "user", "content": prompt}]
        kwargs = dict(model=model, max_tokens=4096, messages=messages)
        if system:
            kwargs["system"] = system
        if 0.0 <= temperature <= 1.0:
            kwargs["temperature"] = temperature

        full_text = ""
        render_gate = StreamRenderGate()
        try:
            with client.messages.stream(**kwargs) as stream:
                for event in stream:
                    if getattr(event, "type", "") == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta and getattr(delta, "type", "") == "text_delta":
                            text = getattr(delta, "text", "")
                            full_text += text
                            # Rendering every provider delta can enqueue hundreds of
                            # expensive layout/scroll operations per second. Coalesce
                            # them to at most ~30 fps (or a visibly large chunk).
                            if render_gate.should_render(text, time.monotonic()):
                                self.call_from_thread(reply_widget.update_text, full_text)
                                self.call_from_thread(
                                    self.query_one("#transcript").scroll_end, animate=False
                                )
        except Exception as e:
            full_text = full_text or f"[ERROR] {e}"
        finally:
            # A final delta frequently arrives before the next render interval
            # or character threshold. Flush it unconditionally so the visible
            # transcript always matches the saved assistant history.
            self.call_from_thread(reply_widget.update_text, full_text)
            self.call_from_thread(self.query_one("#transcript").scroll_end, animate=False)
        return full_text


def run_tui(api_key: str | None = None) -> None:
    """Entry point used by main.py's --tui flag."""
    wireTUI(api_key=api_key).run()


if __name__ == "__main__":  # pragma: no cover
    run_tui()
