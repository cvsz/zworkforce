from typing import Any
"""
zc_plugins.py — Plugin & Marketplace system
AI Model Coder CLI v1.9.0

Models zAICoder's plugin system (docs.zc.com/plugins-reference):

PLUGIN STRUCTURE
  my-plugin/
    .zc-plugin/plugin.json   — manifest (optional; auto-discovery if absent)
    skills/<name>/SKILL.md       — skills bundled with the plugin
    commands/*.md                — slash commands (flat .md files)
    agents/*.md                  — subagent definitions
    output-styles/*.md           — output style definitions
    hooks/hooks.json             — hook configuration
    .mcp.json                    — MCP server definitions
    bin/                         — executables added to PATH for the session

MARKETPLACES
  A marketplace is a directory (local path or git URL) containing one or
  more plugins plus a marketplace.json index. `--plugin-marketplace-add`
  registers one; `--plugin-install name@marketplace` installs from it.

INSTALL LOCATIONS
  ~/.zc/plugins/marketplaces/<marketplace>/   — cloned/copied marketplace
  ~/.zc/plugins/installed/<plugin>/           — installed plugin (copy)
  ~/.zc/plugins/registry.json                 — installed-plugin index

CLI flags:
  --plugin-marketplace-add PATH_OR_URL [--plugin-marketplace-name NAME]
  --plugin-marketplace-list
  --plugin-marketplace-remove NAME
  --plugin-install NAME[@MARKETPLACE]
  --plugin-uninstall NAME
  --plugin-list
  --plugin-info NAME
  --plugin-enable NAME / --plugin-disable NAME
  --plugin-dir PATH         (load a plugin directly from a local/zip path, no install step)
  --plugin-validate PATH    (lint a plugin directory/manifest before installing)
"""

import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

from wire.exceptions import AICoderError, TransientAPIError
from wire.resilience import retry

PLUGINS_ROOT     = Path(os.path.expanduser("~/.zc/plugins"))
MARKETPLACES_DIR = PLUGINS_ROOT / "marketplaces"
INSTALLED_DIR    = PLUGINS_ROOT / "installed"
REGISTRY_FILE    = PLUGINS_ROOT / "registry.json"

for d in (MARKETPLACES_DIR, INSTALLED_DIR):
    d.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════
# REGISTRY (installed plugins + enabled/disabled state)
# ══════════════════════════════════════════════════════════════════════════

def _load_registry() -> dict:
    if REGISTRY_FILE.exists():
        try:
            return json.loads(REGISTRY_FILE.read_text())
        except Exception:
            pass
    return {"marketplaces": {}, "installed": {}}


def _save_registry(reg: dict):
    REGISTRY_FILE.write_text(json.dumps(reg, indent=2))


# ══════════════════════════════════════════════════════════════════════════
# MANIFEST
# ══════════════════════════════════════════════════════════════════════════

DEFAULT_MANIFEST_FIELDS: dict[str, Any] = {
    "name": "", "displayName": "", "version": "0.0.0", "description": "",
    "author": {}, "homepage": "", "repository": "", "license": "",
    "keywords": [], "skills": None, "commands": None, "agents": None,
    "hooks": None, "mcpServers": None, "outputStyles": None,
    "lspServers": None, "dependencies": [],
}


def read_manifest(plugin_dir: Path) -> dict:
    """Read .zc-plugin/plugin.json, or auto-derive a manifest if absent."""
    manifest_path = plugin_dir / ".zc-plugin" / "plugin.json"
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text())
        except Exception as e:
            raise ValueError(f"invalid plugin.json: {e}")
        merged = {**DEFAULT_MANIFEST_FIELDS, **data}
        if not merged["name"]:
            raise ValueError("plugin.json must include a 'name' field")
        return merged

    # Auto-discovery: no manifest, derive everything from directory layout
    return {
        **DEFAULT_MANIFEST_FIELDS,
        "name": plugin_dir.name,
        "displayName": plugin_dir.name,
        "description": f"Auto-discovered plugin from {plugin_dir.name}",
    }


def validate_plugin(plugin_dir: Path) -> list:
    """Return a list of (level, message) lint findings. Empty = clean."""
    findings = []
    if not plugin_dir.exists():
        return [("error", f"path does not exist: {plugin_dir}")]

    try:
        manifest = read_manifest(plugin_dir)
    except ValueError as e:
        return [("error", str(e))]

    if not (plugin_dir / ".zc-plugin" / "plugin.json").exists():
        findings.append(("info", "no manifest found; using auto-discovery"))

    known_dirs = {"skills", "commands", "agents", "output-styles", "themes",
                  "monitors", "hooks", "bin", "scripts"}
    for child in plugin_dir.iterdir():
        if child.is_dir() and child.name not in known_dirs and child.name != ".zc-plugin":
            findings.append(("warn", f"unrecognised top-level directory: {child.name}/"))

    hooks_json = plugin_dir / "hooks" / "hooks.json"
    if hooks_json.exists():
        try:
            json.loads(hooks_json.read_text())
        except Exception as e:
            findings.append(("error", f"hooks/hooks.json invalid JSON: {e}"))

    mcp_json = plugin_dir / ".mcp.json"
    if mcp_json.exists():
        try:
            data = json.loads(mcp_json.read_text())
            if "mcpServers" not in data:
                findings.append(("warn", ".mcp.json present but has no 'mcpServers' key"))
        except Exception as e:
            findings.append(("error", f".mcp.json invalid JSON: {e}"))

    skills_dir = plugin_dir / "skills"
    if skills_dir.exists():
        for sk in skills_dir.iterdir():
            if sk.is_dir() and not (sk / "SKILL.md").exists():
                findings.append(("warn", f"skills/{sk.name}/ has no SKILL.md"))

    if not findings:
        findings.append(("ok", f"plugin '{manifest['name']}' looks valid"))
    return findings


# ══════════════════════════════════════════════════════════════════════════
# MARKETPLACES
# ══════════════════════════════════════════════════════════════════════════

def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://") or s.startswith("git@")


# No CircuitBreaker: a marketplace source is a one-off, user-specified URL,
# not a fixed downstream dependency this process calls repeatedly.
@retry(max_attempts=2, base_delay=1.0, max_delay=5.0)
def _fetch_marketplace_source(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read()
    except urllib.error.URLError as e:
        raise TransientAPIError(f"could not fetch {url}: {e}") from e


def marketplace_add(source: str, name: Optional[str] = None) -> dict:
    """
    Register a marketplace from a local directory, a .zip, or a URL
    (URLs are fetched as a tarball/zip listing — git clone is not
    available in this sandboxed CLI, so http(s) sources must point at a
    marketplace.json or a zip archive).
    """
    reg = _load_registry()
    mp_name = name or Path(source.rstrip("/")).stem or "marketplace"

    dest = MARKETPLACES_DIR / mp_name
    if dest.exists():
        shutil.rmtree(dest)

    if _is_url(source):
        if source.endswith(".zip"):
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                try:
                    tmp.write(_fetch_marketplace_source(source))
                except AICoderError as e:
                    raise RuntimeError(str(e.message)) from e
                tmp_path = tmp.name
            with zipfile.ZipFile(tmp_path) as zf:
                zf.extractall(dest)
            os.unlink(tmp_path)
        else:
            try:
                raw = _fetch_marketplace_source(source).decode("utf-8", errors="replace")
            except AICoderError as e:
                raise RuntimeError(str(e.message)) from e
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "marketplace.json").write_text(raw)
    else:
        src_path = Path(os.path.expanduser(source))
        if not src_path.exists():
            raise RuntimeError(f"local path does not exist: {src_path}")
        if src_path.suffix == ".zip":
            dest.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(src_path) as zf:
                zf.extractall(dest)
        else:
            shutil.copytree(src_path, dest)

    plugins = _discover_plugins_in_marketplace(dest)
    plugin_names = []
    for p in plugins:
        try:
            plugin_names.append(read_manifest(p)["name"])
        except ValueError:
            plugin_names.append(p.name)
    reg["marketplaces"][mp_name] = {
        "source": source,
        "path": str(dest),
        "plugins": plugin_names,
    }
    _save_registry(reg)
    return reg["marketplaces"][mp_name]


def _discover_plugins_in_marketplace(mp_dir: Path) -> list:
    """A marketplace dir may itself be a single plugin, or contain many."""
    if (mp_dir / ".zc-plugin" / "plugin.json").exists():
        return [mp_dir]
    found = []
    index = mp_dir / "marketplace.json"
    if index.exists():
        try:
            data = json.loads(index.read_text())
            for entry in data.get("plugins", []):
                rel = entry.get("path", entry.get("name", ""))
                cand = mp_dir / rel
                if cand.exists():
                    found.append(cand)
        except Exception as _e:
            pass
    if found:
        return found
    # Fallback: any immediate subdirectory that looks like a plugin
    for child in mp_dir.iterdir():
        if child.is_dir() and (
            (child / ".zc-plugin" / "plugin.json").exists()
            or (child / "skills").exists()
            or (child / "commands").exists()
            or (child / "agents").exists()
        ):
            found.append(child)
    return found


def marketplace_list() -> list:
    reg = _load_registry()
    out = []
    for name, info in reg["marketplaces"].items():
        out.append({"name": name, **info})
    return out


def marketplace_remove(name: str) -> bool:
    reg = _load_registry()
    if name not in reg["marketplaces"]:
        return False
    path = Path(reg["marketplaces"][name]["path"])
    if path.exists():
        shutil.rmtree(path)
    del reg["marketplaces"][name]
    # Also uninstall anything installed from it
    for pname, pinfo in list(reg["installed"].items()):
        if pinfo.get("marketplace") == name:
            del reg["installed"][pname]
    _save_registry(reg)
    return True


# ══════════════════════════════════════════════════════════════════════════
# INSTALL / UNINSTALL
# ══════════════════════════════════════════════════════════════════════════

def plugin_install(spec: str) -> dict:
    """spec is 'name' or 'name@marketplace'."""
    reg = _load_registry()
    if "@" in spec:
        name, mp_name = spec.split("@", 1)
    else:
        name, mp_name = spec, None

    candidates = []
    marketplaces = [mp_name] if mp_name else list(reg["marketplaces"].keys())
    for mp in marketplaces:
        mp_info = reg["marketplaces"].get(mp)
        if not mp_info:
            continue
        mp_path = Path(mp_info["path"])
        for plug_dir in _discover_plugins_in_marketplace(mp_path):
            try:
                manifest = read_manifest(plug_dir)
            except ValueError:
                continue
            if manifest["name"] == name:
                candidates.append((mp, plug_dir, manifest))

    if not candidates:
        raise RuntimeError(
            f"plugin '{name}' not found in "
            f"{'marketplace ' + mp_name if mp_name else 'any registered marketplace'}"
        )

    mp, plug_dir, manifest = candidates[0]
    dest = INSTALLED_DIR / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(plug_dir, dest)

    reg["installed"][name] = {
        "marketplace": mp,
        "version": manifest.get("version", "0.0.0"),
        "path": str(dest),
        "enabled": True,
    }
    _save_registry(reg)
    return reg["installed"][name]


def plugin_install_from_dir(path: str) -> dict:
    """Install directly from a local directory or .zip — bypasses marketplaces."""
    reg = _load_registry()
    src_path = Path(os.path.expanduser(path))
    if not src_path.exists():
        raise RuntimeError(f"path does not exist: {src_path}")

    if src_path.suffix == ".zip":
        tmp_extract = Path(tempfile.mkdtemp())
        with zipfile.ZipFile(src_path) as zf:
            zf.extractall(tmp_extract)
        contents = list(tmp_extract.iterdir())
        plug_dir = contents[0] if len(contents) == 1 and contents[0].is_dir() else tmp_extract
    else:
        plug_dir = src_path

    manifest = read_manifest(plug_dir)
    name = manifest["name"]
    dest = INSTALLED_DIR / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(plug_dir, dest)

    reg["installed"][name] = {
        "marketplace": None,
        "version": manifest.get("version", "0.0.0"),
        "path": str(dest),
        "enabled": True,
    }
    _save_registry(reg)
    return reg["installed"][name]


def plugin_uninstall(name: str) -> bool:
    reg = _load_registry()
    if name not in reg["installed"]:
        return False
    path = Path(reg["installed"][name]["path"])
    if path.exists():
        shutil.rmtree(path)
    del reg["installed"][name]
    _save_registry(reg)
    return True


def plugin_set_enabled(name: str, enabled: bool) -> bool:
    reg = _load_registry()
    if name not in reg["installed"]:
        return False
    reg["installed"][name]["enabled"] = enabled
    _save_registry(reg)
    return True


def plugin_list() -> list:
    reg = _load_registry()
    out = []
    for name, info in reg["installed"].items():
        out.append({"name": name, **info})
    return out


def plugin_info(name: str) -> Optional[dict]:
    reg = _load_registry()
    info = reg["installed"].get(name)
    if not info:
        return None
    plug_dir = Path(info["path"])
    try:
        manifest = read_manifest(plug_dir)
    except ValueError:
        manifest = {}
    return {"name": name, **info, "manifest": manifest}


# ══════════════════════════════════════════════════════════════════════════
# LOADING — pull components from installed (enabled) plugins
# ══════════════════════════════════════════════════════════════════════════

def enabled_plugin_dirs() -> list:
    reg = _load_registry()
    return [Path(info["path"]) for info in reg["installed"].values() if info.get("enabled", True)]


def load_plugin_skills() -> list:
    """Return [{name, path, plugin}] for every SKILL.md across enabled plugins."""
    out = []
    for plug_dir in enabled_plugin_dirs():
        skills_dir = plug_dir / "skills"
        if not skills_dir.exists():
            continue
        for sk in skills_dir.iterdir():
            md = sk / "SKILL.md"
            if md.exists():
                out.append({"name": sk.name, "path": str(md), "plugin": plug_dir.name})
    return out


def load_plugin_commands() -> list:
    """Return [{name, path, plugin}] for every command .md (namespaced as plugin:name)."""
    out = []
    for plug_dir in enabled_plugin_dirs():
        cmd_dir = plug_dir / "commands"
        if not cmd_dir.exists():
            continue
        for f in cmd_dir.rglob("*.md"):
            out.append({
                "name": f"{plug_dir.name}:{f.stem}",
                "path": str(f),
                "plugin": plug_dir.name,
            })
    return out


def load_plugin_agents() -> list:
    out = []
    for plug_dir in enabled_plugin_dirs():
        agents_dir = plug_dir / "agents"
        if not agents_dir.exists():
            continue
        for f in agents_dir.glob("*.md"):
            out.append({"name": f.stem, "path": str(f), "plugin": plug_dir.name})
    return out


def load_plugin_output_styles() -> list:
    out = []
    for plug_dir in enabled_plugin_dirs():
        styles_dir = plug_dir / "output-styles"
        if not styles_dir.exists():
            continue
        for f in styles_dir.glob("*.md"):
            out.append({"name": f.stem, "path": str(f), "plugin": plug_dir.name})
    return out


def load_plugin_hooks() -> dict:
    """Merge hooks.json from every enabled plugin into one HooksEngine-shaped dict."""
    merged: dict = {}
    for plug_dir in enabled_plugin_dirs():
        hooks_file = plug_dir / "hooks" / "hooks.json"
        if not hooks_file.exists():
            continue
        try:
            data = json.loads(hooks_file.read_text())
        except Exception:
            continue
        for event, handlers in data.items():
            merged.setdefault(event, [])
            for h in handlers:
                h = dict(h)
                h["_plugin"] = plug_dir.name
                merged[event].append(h)
    return merged


def load_plugin_mcp_servers() -> dict:
    merged = {}
    for plug_dir in enabled_plugin_dirs():
        mcp_file = plug_dir / ".mcp.json"
        if not mcp_file.exists():
            continue
        try:
            data = json.loads(mcp_file.read_text())
        except Exception:
            continue
        for name, cfg in data.get("mcpServers", {}).items():
            merged[f"{plug_dir.name}:{name}"] = cfg
    return merged


def plugin_bin_paths() -> list:
    """bin/ directories from enabled plugins, to prepend to PATH for Bash tool calls."""
    return [str(p / "bin") for p in enabled_plugin_dirs() if (p / "bin").exists()]


# ══════════════════════════════════════════════════════════════════════════
# CLI command handlers
# ══════════════════════════════════════════════════════════════════════════

def cmd_plugin_marketplace_add(source: str, name: Optional[str] = None):
    try:
        info = marketplace_add(source, name)
        print(f"\033[92m✓ Marketplace added: {name or Path(source.rstrip('/')).stem}\033[0m")
        print(f"  plugins found: {', '.join(info['plugins']) or '(none)'}")
    except Exception as e:
        print(f"\033[91m✗ {e}\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_plugin_marketplace_list():
    mps = marketplace_list()
    if not mps:
        print("No marketplaces registered. Use --plugin-marketplace-add PATH_OR_URL")
        return
    for mp in mps:
        print(f"\033[1m{mp['name']}\033[0m  ({mp['source']})")
        for p in mp["plugins"]:
            print(f"   • {p}")


def cmd_plugin_marketplace_remove(name: str):
    if marketplace_remove(name):
        print(f"\033[92m✓ Removed marketplace: {name}\033[0m")
    else:
        print(f"\033[91m✗ No such marketplace: {name}\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_plugin_install(spec: str):
    try:
        info = plugin_install(spec)
        print(f"\033[92m✓ Installed {spec}\033[0m (v{info['version']})")
    except Exception as e:
        print(f"\033[91m✗ {e}\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_plugin_install_dir(path: str):
    try:
        info = plugin_install_from_dir(path)
        print(f"\033[92m✓ Installed from {path}\033[0m (v{info['version']})")
    except Exception as e:
        print(f"\033[91m✗ {e}\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_plugin_uninstall(name: str):
    if plugin_uninstall(name):
        print(f"\033[92m✓ Uninstalled {name}\033[0m")
    else:
        print(f"\033[91m✗ Not installed: {name}\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_plugin_list():
    plugins = plugin_list()
    if not plugins:
        print("No plugins installed. Use --plugin-install NAME@MARKETPLACE")
        return
    for p in plugins:
        state = "\033[92menabled\033[0m" if p.get("enabled", True) else "\033[90mdisabled\033[0m"
        mp = p.get("marketplace") or "local"
        print(f"  {p['name']:<24} v{p['version']:<10} [{mp}]  {state}")


def cmd_plugin_info(name: str):
    info = plugin_info(name)
    if not info:
        print(f"\033[91m✗ Not installed: {name}\033[0m", file=sys.stderr)
        sys.exit(1)
    m = info["manifest"]
    print(f"\033[1m{m.get('displayName') or name}\033[0m  v{info['version']}")
    print(f"  {m.get('description', '')}")
    print(f"  marketplace: {info.get('marketplace') or 'local'}")
    print(f"  path: {info['path']}")
    plug_dir = Path(info["path"])
    for sub, label in [("skills", "Skills"), ("commands", "Commands"),
                        ("agents", "Agents"), ("output-styles", "Output styles"),
                        ("hooks", "Hooks"), (".mcp.json", "MCP servers")]:
        p = plug_dir / sub
        if p.exists():
            print(f"  • {label}: {p}")


def cmd_plugin_enable(name: str):
    if plugin_set_enabled(name, True):
        print(f"\033[92m✓ Enabled {name}\033[0m")
    else:
        print(f"\033[91m✗ Not installed: {name}\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_plugin_disable(name: str):
    if plugin_set_enabled(name, False):
        print(f"\033[92m✓ Disabled {name}\033[0m")
    else:
        print(f"\033[91m✗ Not installed: {name}\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_plugin_validate(path: str):
    findings = validate_plugin(Path(os.path.expanduser(path)))
    icon = {"ok": "\033[92m✓", "info": "\033[94mℹ", "warn": "\033[93m⚠", "error": "\033[91m✗"}
    for level, msg in findings:
        print(f"{icon.get(level, '')} {msg}\033[0m")
    if any(level == "error" for level, _ in findings):
        sys.exit(1)
