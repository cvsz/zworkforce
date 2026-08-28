"""
zc_output_styles.py — Output Styles
AI Model Coder CLI v1.9.0

Output styles change how the agent formats and frames its responses,
without changing what tools it can use. Modelled on zAICoder's
output-style system (built-ins + custom .md styles with frontmatter).

Built-in styles: default, explanatory, concise, learning

Custom styles: .zc/output-styles/<name>.md or a plugin's
output-styles/<name>.md, with frontmatter:
  ---
  name: terse
  description: Minimal, no preamble, code-first
  keep-coding-instructions: true
  ---
  <body becomes additional system-prompt text>

CLI flags:
  --code-agent-output-style NAME
  --list-output-styles
"""

import os
import re
from pathlib import Path
from typing import Optional

PROJECT_STYLES_DIR = Path(".zc/output-styles")
USER_STYLES_DIR     = Path(os.path.expanduser("~/.zc/output-styles"))

BUILTIN_STYLES = {
    "default": {
        "description": "Standard zAICoder behaviour — concise, tool-using, no extra narration.",
        "prompt": "",  # no extra injection; this is the baseline
    },
    "explanatory": {
        "description": "Adds educational insights about implementation choices and codebase patterns.",
        "prompt": (
            "After completing each significant step, briefly explain the *why* behind "
            "the implementation choice you made — patterns used, trade-offs considered, "
            "and anything notable about the surrounding codebase. Keep these insights to "
            "1-3 sentences; do not let them overwhelm the actual work."
        ),
    },
    "concise": {
        "description": "Minimal narration. Output is mostly tool calls and final results.",
        "prompt": (
            "Be extremely concise. Skip preamble and restating the task. Narrate only "
            "what is necessary to track progress. Prefer terse confirmations over "
            "explanations unless the user asks why."
        ),
    },
    "learning": {
        "description": "Interactive mode that pauses at decision points for the user to write a small piece of code themselves.",
        "prompt": (
            "Work collaboratively rather than autonomously. At natural decision points "
            "(e.g. before writing a non-trivial function or fixing a bug), pause and ask "
            "the user to write a small (5-10 line) piece of the implementation themselves, "
            "giving them just enough context to do so, then continue from what they wrote. "
            "Use this as a teaching opportunity — explain the concept briefly before they write."
        ),
    },
}

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_style_file(path: Path) -> Optional[dict]:
    try:
        text = path.read_text()
    except Exception:
        return None
    m = FRONTMATTER_RE.match(text)
    meta, body = {}, text
    if m:
        front, body = m.group(1), m.group(2)
        for line in front.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"').strip("'")
    name = meta.get("name", path.stem)
    return {
        "name": name,
        "description": meta.get("description", ""),
        "keep_coding_instructions": meta.get("keep-coding-instructions", "false").lower() == "true",
        "prompt": body.strip(),
        "source": str(path),
    }


def discover_custom_styles() -> dict:
    """Scan project and user output-style dirs, plus enabled plugins."""
    out = {}
    for d in (USER_STYLES_DIR, PROJECT_STYLES_DIR):
        if d.exists():
            for f in d.glob("*.md"):
                style = _parse_style_file(f)
                if style:
                    out[style["name"]] = style
    try:
        from wire.zc_plugins import load_plugin_output_styles
        for entry in load_plugin_output_styles():
            style = _parse_style_file(Path(entry["path"]))
            if style:
                style["plugin"] = entry["plugin"]
                out[style["name"]] = style
    except ImportError as _e:
        pass
    return out


def list_styles() -> list:
    out = [{"name": n, "description": s["description"], "builtin": True}
           for n, s in BUILTIN_STYLES.items()]
    for n, s in discover_custom_styles().items():
        out.append({
            "name": n, "description": s["description"], "builtin": False,
            "plugin": s.get("plugin"),
        })
    return out


def get_style(name: str) -> Optional[dict]:
    if name in BUILTIN_STYLES:
        return {"name": name, **BUILTIN_STYLES[name], "keep_coding_instructions": True}
    return discover_custom_styles().get(name)


def system_prompt_fragment(name: str) -> str:
    """Return text to append to the agent's system prompt for this style, or ''."""
    style = get_style(name)
    if not style or not style.get("prompt"):
        return ""
    return f"[Output style: {name}]\n{style['prompt']}"


def cmd_list_output_styles():
    styles = list_styles()
    print("\nOutput styles:")
    for s in styles:
        tag = "(builtin)" if s["builtin"] else f"(plugin: {s.get('plugin')})" if s.get("plugin") else "(custom)"
        print(f"  {s['name']:<14} {tag:<22} {s['description']}")
    print(f"\nProject styles dir: {PROJECT_STYLES_DIR}")
    print(f"User styles dir:    {USER_STYLES_DIR}")
