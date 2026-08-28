from typing import Any
"""
zc_settings.py — Settings precedence & statusLine
AI Model Coder CLI v1.9.0

Models zAICoder's layered settings.json (docs.zc.com):

  ~/.zc/settings.json              user settings   (lowest precedence)
  .zc/settings.json                project settings
  .zc/settings.local.json           local overrides (gitignored, highest)
  CLI flags                             always win over all of the above

Recognised keys (subset relevant to this CLI):
  model, permission, tools, env, hooks, mcpServers, statusLine,
  outputStyle, cleanupPeriodDays, includeCoAuthoredBy

statusLine:
  A small renderer that prints session/cost/model info to the terminal,
  similar to a custom statusLine script in real zAICoder. Either a
  built-in template string with {model} {cwd} {cost} {turns} placeholders,
  or a shell `command` that receives session JSON on stdin (matches the
  real statusLine hook contract) and prints a line to render.

CLI flags:
  --settings-show           Print the merged, resolved settings + provenance
  --status-line             Render the statusLine once for the current state
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional

USER_SETTINGS    = Path(os.path.expanduser("~/.zc/settings.json"))
PROJECT_SETTINGS = Path(".zc/settings.json")
LOCAL_SETTINGS   = Path(".zc/settings.local.json")

DEFAULT_STATUS_LINE_TEMPLATE = "[{model}] {cwd} · turns:{turns} · ${cost}"


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as e:
        print(f"  \033[93m[WARN] could not parse {path}: {e}\033[0m")
        return {}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings(cli_overrides: Optional[dict] = None) -> dict:
    """
    Merge settings in ascending precedence: user -> project -> local -> CLI.
    Returns the merged dict.
    """
    merged: dict[str, Any] = {}
    for path in (USER_SETTINGS, PROJECT_SETTINGS, LOCAL_SETTINGS):
        merged = _deep_merge(merged, _read_json(path))
    if cli_overrides:
        merged = _deep_merge(merged, {k: v for k, v in cli_overrides.items() if v is not None})
    return merged


def load_settings_with_provenance() -> dict:
    """Like load_settings, but also report which file each top-level key came from."""
    layers = [
        ("user", _read_json(USER_SETTINGS)),
        ("project", _read_json(PROJECT_SETTINGS)),
        ("local", _read_json(LOCAL_SETTINGS)),
    ]
    merged: dict[str, Any] = {}; provenance: dict[str, str] = {}
    for layer_name, data in layers:
        merged = _deep_merge(merged, data)
        for k in data:
            provenance[k] = layer_name
    return {"settings": merged, "provenance": provenance}


def write_setting(scope: str, key: str, value) -> Path:
    """scope is 'user' | 'project' | 'local'."""
    path = {"user": USER_SETTINGS, "project": PROJECT_SETTINGS, "local": LOCAL_SETTINGS}[scope]
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_json(path)
    data[key] = value
    path.write_text(json.dumps(data, indent=2))
    return path


def cmd_settings_show():
    result = load_settings_with_provenance()
    print("\nResolved settings (precedence: user < project < local < CLI flags)\n")
    if not result["settings"]:
        print("  (none set — using built-in defaults)")
    for k, v in result["settings"].items():
        src = result["provenance"].get(k, "?")
        print(f"  {k:<20} = {json.dumps(v):<40} [{src}]")
    print(f"\n  user:    {USER_SETTINGS}  {'(exists)' if USER_SETTINGS.exists() else '(absent)'}")
    print(f"  project: {PROJECT_SETTINGS}  {'(exists)' if PROJECT_SETTINGS.exists() else '(absent)'}")
    print(f"  local:   {LOCAL_SETTINGS}  {'(exists)' if LOCAL_SETTINGS.exists() else '(absent)'}")


# ══════════════════════════════════════════════════════════════════════════
# STATUS LINE
# ══════════════════════════════════════════════════════════════════════════

def render_status_line(session_state: dict) -> str:
    """
    session_state keys used: model, cwd, turns, cost (all optional; missing
    values render as '?'). If settings define a statusLine.command, run it
    instead, piping session_state as JSON to stdin (matches the real
    statusLine hook contract) and using its stdout.
    """
    settings = load_settings()
    sl = settings.get("statusLine", {})

    if isinstance(sl, dict) and sl.get("command"):
        try:
            import shlex
            cmd_args = shlex.split(sl["command"]) if isinstance(sl["command"], str) else sl["command"]
            r = subprocess.run(
                cmd_args, shell=False,
                input=json.dumps(session_state),
                capture_output=True, text=True, timeout=5,
            )
            line = r.stdout.strip()
            if line:
                return line
        except Exception as e:
            return f"[statusLine error: {e}]"

    template = sl.get("template") if isinstance(sl, dict) else None
    template = template or DEFAULT_STATUS_LINE_TEMPLATE
    return template.format(
        model=session_state.get("model", "?"),
        cwd=session_state.get("cwd", "?"),
        turns=session_state.get("turns", "?"),
        cost=session_state.get("cost", "0.00"),
    )


def cmd_status_line(model: str, cwd: str = ".", turns: int = 0, cost: float = 0.0):
    line = render_status_line({
        "model": model, "cwd": cwd, "turns": turns, "cost": f"{cost:.4f}",
    })
    print(line)
