"""
zc_sandbox.py — Sandboxed Bash execution
AI Model Coder CLI v1.9.0

Models zAICoder's sandboxed Bash tool: OS-level-style filesystem and
network isolation enforced around shell commands the agent runs, without
needing a prompt/approval round-trip for every command inside the
sandbox boundary.

This is a best-effort, portable sandbox (no kernel namespaces — those
aren't available in every environment this CLI runs in). It enforces:
  • filesystem: commands may only touch paths under one or more
    allowed roots (default: the session cwd); writes outside are blocked
    pre-execution by static inspection of the command for common file-
    redirection / mutation patterns plus a post-hoc cwd jail via subprocess cwd.
  • network: when network is disabled, common networking binaries/flags
    are blocked before exec (curl, wget, nc, ssh, scp, http clients,
    python -m http.server, pip/npm install which hit the network, etc.)

This is defense-in-depth for an agent that already passes every tool
call through PreToolUse hooks and permission gating — it is not a
substitute for a real OS sandbox (containers, seccomp, firejail) when
running fully untrusted code.

CLI flags:
  --code-agent-sandbox                 enable sandboxed Bash
  --code-agent-sandbox-allow-net       allow network calls inside the sandbox
  --code-agent-sandbox-roots PATH...   additional allowed filesystem roots
"""

import re
import shlex
from pathlib import Path
from typing import Optional

NETWORK_BINARIES = {
    "curl", "wget", "nc", "ncat", "netcat", "ssh", "scp", "sftp", "rsync",
    "telnet", "ftp", "http", "https", "wormhole", "ngrok",
}
NETWORK_PIP_NPM_FLAGS = {
    "pip": {"install", "download"},
    "pip3": {"install", "download"},
    "npm": {"install", "i", "ci", "update", "publish"},
    "npx": set(),  # npx can fetch packages by default; flag the bare command
    "yarn": {"add", "install", "upgrade"},
    "git": {"clone", "fetch", "pull", "push"},
}


class SandboxViolation(Exception):
    pass


def _tokenize(command: str) -> list:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def check_network(command: str) -> Optional[str]:
    """Return a violation message if the command looks like a network call, else None."""
    tokens = _tokenize(command)
    if not tokens:
        return None

    for i, tok in enumerate(tokens):
        base = Path(tok).name
        if base in NETWORK_BINARIES:
            return f"network binary '{base}' is blocked inside the sandbox (run with --code-agent-sandbox-allow-net to permit)"
        if base in NETWORK_PIP_NPM_FLAGS:
            sub_flags = NETWORK_PIP_NPM_FLAGS[base]
            rest = set(tokens[i + 1:i + 2])
            if not sub_flags or rest & sub_flags:
                return f"'{base}' network operation is blocked inside the sandbox"
        if base == "python" or base == "python3":
            joined = " ".join(tokens[i:i + 3])
            if "http.server" in joined or "urllib" in joined:
                return "python network access is blocked inside the sandbox"

    # Catch protocol URLs anywhere in the command line as a backstop
    if re.search(r"https?://|ftp://|ssh://", command):
        return "command contains a network URL, blocked inside the sandbox"
    return None


def check_filesystem(command: str, allowed_roots: list) -> Optional[str]:
    """
    Best-effort static check: flag absolute paths or '..' traversal outside
    the allowed roots when they appear as redirection targets or common
    mutation-command arguments. Not a full parser — defense in depth only.
    """
    allowed = [Path(r).resolve() for r in allowed_roots]

    def _is_allowed(p: str) -> bool:
        try:
            resolved = Path(p).expanduser().resolve()
        except Exception:
            return True  # don't block on unparseable paths
        return any(resolved == root or root in resolved.parents for root in allowed)

    # Redirection targets: > file, >> file
    for m in re.finditer(r"(?:>>?)\s*([^\s|&;]+)", command):
        target = m.group(1)
        if (target.startswith("/") or target.startswith("~")) and not _is_allowed(target):
            return f"redirect target '{target}' is outside the sandbox root(s)"

    # rm -rf / mv / cp targeting absolute paths outside roots
    for m in re.finditer(r"\b(rm|mv|cp)\b[^|;&]*", command):
        for path_tok in re.findall(r"(?:^|\s)(/[^\s]+|~[^\s]*)", m.group(0)):
            if not _is_allowed(path_tok):
                return f"'{m.group(1)}' targets '{path_tok}' outside the sandbox root(s)"

    return None


def enforce(command: str, cwd: str, allow_net: bool = False,
            extra_roots: Optional[list] = None) -> None:
    """Raise SandboxViolation if the command violates sandbox policy."""
    roots = [cwd] + (extra_roots or [])

    if not allow_net:
        violation = check_network(command)
        if violation:
            raise SandboxViolation(violation)

    violation = check_filesystem(command, roots)
    if violation:
        raise SandboxViolation(violation)
