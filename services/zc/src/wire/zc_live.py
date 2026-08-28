from typing import Any, cast
"""
zc_live.py — Real-time streaming REPL (zai-live mode)
AI Model Coder CLI v1.10.0

Streams tokens as they arrive, maintains ambient context (background
events pushed without triggering a reply), and supports the same
slash-command set as interactive mode.
"""

import json
import sys
import threading

import anthropic

from wire.utils import sampling_kwargs

LIVE_SYSTEM = (
    "You are an always-on assistant. Respond to the user's message directly. "
    "Ambient context events (background observations) are provided in the system "
    "prompt for awareness — address them only if the user refers to them."
)


class AmbientBuffer:
    def __init__(self, maxlen: int = 20):
        self._events: list[dict[str, str]] = []
        self._lock = threading.Lock()
        self._maxlen = maxlen

    def push(self, source: str, content: str):
        with self._lock:
            self._events.append({"source": source, "content": content})
            if len(self._events) > self._maxlen:
                self._events = self._events[-self._maxlen:]

    def block(self) -> str:
        with self._lock:
            if not self._events: return ""
            lines = ["## Ambient Context"]
            for e in self._events[-10:]:
                lines.append(f"- [{e['source']}] {e['content']}")
            return "\n".join(lines)

    def clear(self):
        with self._lock: self._events = []


class LiveSession:
    def __init__(self, api_key: str, model: str = "zc-xxx",
                 temperature: float = 0.7, personality_prompt: str = ""):
        self.client      = anthropic.Anthropic(api_key=api_key)
        self.model       = model
        self.temperature = temperature
        self.personality = personality_prompt
        self.history: list[dict[str, str]] = []
        self.ambient     = AmbientBuffer()
        self.streaming   = False

    def _system(self) -> str:
        parts = [LIVE_SYSTEM]
        if self.personality: parts.append(self.personality)
        amb = self.ambient.block()
        if amb: parts.append(amb)
        return "\n\n".join(parts)

    def send(self, text: str) -> str:
        self.history.append({"role": "user", "content": text})
        full: list[str] = []
        self.streaming = True
        try:
            with self.client.messages.stream(
                model=self.model, max_tokens=4096,
                # Was hardcoded temperature=self.temperature, unguarded — 400s
                # (invalid_request_error) the moment self.model is zc-xxx
                # (the default), which rejects any explicit sampling param. Route
                # through sampling_kwargs() like coder.py/zc_eval.py do.
                **sampling_kwargs(self.model, temperature=self.temperature),
                system=self._system(), messages=cast(Any, self.history),
            ) as stream:
                for chunk in stream.text_stream:
                    full.append(chunk)
                    sys.stdout.write(chunk); sys.stdout.flush()
        finally:
            self.streaming = False
        result = "".join(full)
        self.history.append({"role": "assistant", "content": result})
        return result

    def stats(self) -> dict[str, Any]:
        return {"model": self.model, "turns": len(self.history),
                "ambient_events": len(self.ambient._events), "streaming": self.streaming}


def _handle_slash(cmd: str, session: LiveSession) -> bool:
    """Return True if handled, False to let the main loop treat it as normal input."""
    parts  = cmd[1:].split(maxsplit=1)
    name   = parts[0].lower() if parts else ""
    arg    = parts[1] if len(parts) > 1 else ""

    if name == "help":
        print("  /ambient <note>  — push background context")
        print("  /clear-ambient   — clear ambient buffer")
        print("  /model [name]    — show or change model")
        print("  /status          — session stats")
        print("  /clear           — clear conversation history")
        print("  /exit            — end session")
        return True
    if name == "ambient" and arg:
        session.ambient.push("manual", arg); print("(ambient noted)"); return True
    if name == "clear-ambient":
        session.ambient.clear(); print("(ambient buffer cleared)"); return True
    if name == "model":
        if arg: session.model = arg.strip(); print(f"Model → {session.model}")
        else:   print(f"Current model: {session.model}")
        return True
    if name == "status":
        print(json.dumps(session.stats(), indent=2)); return True
    if name == "clear":
        session.history = []; print("(history cleared)"); return True
    if name in ("exit", "quit"):
        raise KeyboardInterrupt
    return False


def cmd_live(api_key: str, model: str = "zc-xxx",
             temperature: float = 0.7, personality_prompt: str = ""):
    session = LiveSession(api_key, model, temperature, personality_prompt)
    print(f"⚡ zai-live  model={model}  /help for commands  Ctrl+C to quit\n")
    while True:
        try:
            text = input("You: ").strip()
            if not text: continue
            if text.startswith("/"):
                if not _handle_slash(text, session): print(f"Unknown: {text}")
                continue
            print("Assistant: ", end="", flush=True)
            session.send(text)
            print("\n")
        except KeyboardInterrupt:
            print("\nSession ended."); break
        except EOFError:
            break
