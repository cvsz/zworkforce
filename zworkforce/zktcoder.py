"""zktcoder — free-model coding CLI for the zWorkforce gateway.

A zero-dependency, stdin-driven coding agent that talks to the zWorkforce
OpenAI-compatible provider gateway (Claude Fable 5 / DeepSeek V4 and friends)
over plain HTTP. It deliberately has no telemetry and never contacts any
external analytics endpoint.

Usage::

    echo "Explain this codebase" | zktcoder
    zktcoder --model deepseek/deepseek-v4-flash --cwd src/packages < prompt.txt
    zktcoder --list-models

Environment variables (all optional):

- ``ZKTCODER_BASE_URL`` / ``ZWORKFORCE_PROVIDER_BASE_URL`` — gateway base URL,
  default ``http://127.0.0.1:9569/v1``.
- ``ZKTCODER_API_KEY`` / ``ZWORKFORCE_PROVIDER_API_KEY`` — bearer token. The
  API key is never accepted as a CLI flag: it is read from the environment so
  it cannot leak through ``ps aux``/``/proc/<pid>/cmdline``.
- ``ZKTCODER_MODEL`` — default model id.
- ``ZKTCODER_TIMEOUT_SECONDS`` — request timeout, default 90.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

BANNER = r"""
███████╗██╗  ██╗████████╗ ██████╗ ██████╗ ██████╗ ███████╗██████╗
╚══███╔╝██║ ██╔╝╚══██╔══╝██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗
  ███╔╝ █████╔╝    ██║   ██║     ██║   ██║██║  ██║█████╗  ██████╔╝
 ███╔╝  ██╔═██╗    ██║   ██║     ██║   ██║██║  ██║██╔══╝  ██╔══██╗
███████╗██║  ██╗   ██║   ╚██████╗╚██████╔╝██████╔╝███████╗██║  ██║
╚══════╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝

ZKTCODER — free-model coding agent for the zWorkforce gateway
"""

DEFAULT_BASE_URL = "http://127.0.0.1:9569/v1"
DEFAULT_TIMEOUT_SECONDS = 90

# Fallback catalog used when the gateway is unreachable; the live catalog is
# fetched from the gateway when available.
KNOWN_FREE_MODELS = [
    "anthropic/claude-fable-5",
    "anthropic/claude-fable-5-sonnet",
    "deepseek/deepseek-v4-flash",
    "deepseek/deepseek-v4-pro",
    "openai/gpt-5.6",
    "openai/gpt-5.6-mini",
]


class ZktCoderError(Exception):
    """Raised when the gateway request cannot be completed."""


def _default_base_url() -> str:
    return (
        os.getenv("ZKTCODER_BASE_URL", "").strip()
        or os.getenv("ZWORKFORCE_PROVIDER_BASE_URL", "").strip()
        or DEFAULT_BASE_URL
    )


def _default_api_key() -> str:
    return (
        os.getenv("ZKTCODER_API_KEY", "").strip()
        or os.getenv("ZWORKFORCE_PROVIDER_API_KEY", "").strip()
    )


def _default_model() -> str:
    return os.getenv("ZKTCODER_MODEL", "").strip() or "deepseek/deepseek-v4-flash"


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def chat(
    prompt: str,
    *,
    base_url: str,
    api_key: str = "",
    model: str = "",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    system: str = "You are zktcoder, a precise, security-aware coding agent for the zWorkforce free-model gateway.",
) -> str:
    """Send one chat completion request and return the assistant text."""
    model = model or _default_model()
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "zktcoder/3.0.4",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    url = _normalize_base_url(base_url) + "/chat/completions"
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read(8 * 1024 * 1024)
    except urllib.error.HTTPError as exc:
        detail = exc.read(4096).decode(errors="replace").strip()
        raise ZktCoderError(f"gateway HTTP {exc.code}: {detail or exc.reason}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ZktCoderError(f"gateway unreachable: {exc}") from exc
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ZktCoderError(f"gateway returned invalid JSON: {exc}") from exc
    choices = data.get("choices") or []
    if not choices:
        raise ZktCoderError("gateway returned no choices")
    message = choices[0].get("message") or {}
    content = message.get("content") or ""
    if isinstance(content, list):
        content = "\n".join(
            str(part.get("text", "")) if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content).strip()


def list_models(
    base_url: str,
    api_key: str = "",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[str]:
    """Fetch the gateway model catalog; falls back to the known free catalog."""
    headers = {"Accept": "application/json", "User-Agent": "zktcoder/3.0.4"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    url = _normalize_base_url(base_url) + "/models"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read(4 * 1024 * 1024)
        data = json.loads(raw)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        return list(KNOWN_FREE_MODELS)
    models = [
        str(item.get("id"))
        for item in data.get("data") or []
        if isinstance(item, dict) and item.get("id")
    ]
    return models or list(KNOWN_FREE_MODELS)


def run(
    prompt: str,
    *,
    model: str = "",
    cwd: str = ".",
    base_url: str = "",
    api_key: str = "",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    quiet: bool = False,
) -> int:
    """Execute one coding request. Returns the process exit code."""
    prompt = prompt.strip()
    if not prompt:
        sys.stderr.write("zktcoder: no prompt provided on stdin\n")
        return 2
    if cwd and cwd != ".":
        try:
            os.chdir(cwd)
        except OSError as exc:
            sys.stderr.write(f"zktcoder: cannot change directory to {cwd!r}: {exc}\n")
            return 2
    if not quiet:
        sys.stderr.write(BANNER)
        sys.stderr.write(f"zktcoder: model={model or _default_model()} gateway={_normalize_base_url(base_url or _default_base_url())}\n")
    try:
        output = chat(
            prompt,
            base_url=base_url or _default_base_url(),
            api_key=api_key or _default_api_key(),
            model=model or _default_model(),
            timeout_seconds=timeout_seconds,
        )
    except ZktCoderError as exc:
        sys.stderr.write(f"zktcoder: {exc}\n")
        return 1
    sys.stdout.write(output)
    if output and not output.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zktcoder",
        description="Free-model coding CLI for the zWorkforce gateway. Reads the prompt from stdin.",
    )
    parser.add_argument("--model", default="", help="Gateway model id (default: ZKTCODER_MODEL or deepseek/deepseek-v4-flash)")
    parser.add_argument("--cwd", default=".", help="Directory to change into before running (default: current directory)")
    parser.add_argument("--base-url", default="", help="OpenAI-compatible gateway base URL (default: ZKTCODER_BASE_URL or http://127.0.0.1:9569/v1)")
    parser.add_argument("--timeout", type=int, default=0, help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS})")
    parser.add_argument("--list-models", action="store_true", help="List gateway models and exit")
    parser.add_argument("--quiet", action="store_true", help="Suppress the banner and progress output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    base_url = args.base_url or _default_base_url()
    api_key = _default_api_key()
    timeout = args.timeout or int(os.getenv("ZKTCODER_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))

    if args.list_models:
        if not args.quiet:
            sys.stderr.write(BANNER)
        for model_id in list_models(base_url, api_key, timeout):
            sys.stdout.write(f"{model_id}\n")
        return 0

    prompt = sys.stdin.read()
    return run(
        prompt,
        model=args.model,
        cwd=args.cwd,
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=timeout,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    raise SystemExit(main())
