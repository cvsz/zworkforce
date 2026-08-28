"""
zc_interactive.py — Interactive chat interface
AI Model Coder CLI v1.14.0

A persistent, multi-turn REPL against the Messages API. `-i`/`--interactive`
existed as a bare argparse flag since v1.7.0 but was never read anywhere in
main.py — this module is the first actual implementation behind it.

This is a plain chat loop (no tool execution, no filesystem access) — for
an agentic loop that can read/write files and run commands, use
`--code-agent` instead. `history` here is a simple list of
{"role": "user"|"assistant", "content": str} dicts, matching the shape
`Coder.generate()` has accepted (but never actually received) since it was
added to the method signature.

CLI:
  -i / --interactive              Start the chat REPL
  --interactive-system TEXT       Optional starting system prompt

Slash commands inside the REPL are documented in HELP_TEXT below.
"""

HELP_TEXT = """\
Commands:
  /help              Show this help
  /exit, /quit       End the session
  /reset             Clear conversation history (keeps system prompt)
  /system [TEXT]     Set/replace the system prompt, or clear it if empty
  /model [NAME]      Switch model for subsequent turns, or show current
  /save FILE         Write the full transcript to FILE (markdown)
  /history           Show turn count
"""


def _format_transcript(history, system=None):
    lines = []
    if system:
        lines.append(f"### system\n{system}\n")
    for m in history:
        lines.append(f"### {m.get('role', '?')}\n{m.get('content', '')}\n")
    return "\n".join(lines)


def cmd_interactive(api_key, model, system=None, temperature=0.3, max_tokens=4096,
                     personality_style=None):
    """Run the interactive chat REPL until the user exits."""
    from wire.coder import Coder

    history = []
    c = Coder(api_key=api_key, model=model, temperature=temperature,
              max_tokens=max_tokens, personality_style=personality_style)

    print(f"\033[94mAI Model Coder — interactive chat\033[0m  (model: {c.model})")
    print("Type /help for commands, /exit (or Ctrl-D) to quit.\n")

    while True:
        try:
            user_input = input("\033[92myou›\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            rest = parts[1].strip() if len(parts) > 1 else ""

            if cmd in ("/exit", "/quit"):
                break
            if cmd == "/help":
                print(HELP_TEXT)
                continue
            if cmd == "/reset":
                history = []
                print("[history cleared]")
                continue
            if cmd == "/system":
                system = rest or None
                print("[system prompt set]" if system else "[system prompt cleared]")
                continue
            if cmd == "/model":
                if rest:
                    c.model = rest
                    print(f"[model switched to {c.model}]")
                else:
                    print(f"[current model: {c.model}]")
                continue
            if cmd == "/save":
                path = rest or "transcript.md"
                try:
                    with open(path, "w") as f:
                        f.write(_format_transcript(history, system))
                    print(f"[saved transcript to {path}]")
                except OSError as e:
                    print(f"[ERROR] could not save: {e}")
                continue
            if cmd == "/history":
                print(f"[{len(history)} messages in history]")
                continue
            print(f"[unknown command {cmd!r}; try /help]")
            continue

        reply = c.generate(user_input, system=system, history=history)
        print(f"\033[96mzc›\033[0m {reply}\n")
        # Coder.generate() takes `history` as the turns *before* this one
        # and appends the new user turn internally, but only returns text —
        # so the running history is maintained here, not inside Coder.
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})

    print("\033[94mSession ended.\033[0m")
    return history
