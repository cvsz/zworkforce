"""utils.py — Terminal utilities & formatters"""
import os
import sys
import textwrap


def print_header(title):
    width = min(os.get_terminal_size().columns if sys.stdout.isatty() else 80, 80)
    print("\n" + "═" * width)
    print(f"  {title}")
    print("═" * width)

def print_success(msg):
    print(f"\033[92m✓ {msg}\033[0m")

def print_error(msg):
    print(f"\033[91m✗ {msg}\033[0m", file=sys.stderr)

def print_info(msg):
    print(f"\033[94mℹ {msg}\033[0m")

def print_warn(msg):
    print(f"\033[93m⚠ {msg}\033[0m")

def format_code_block(code, lang=""):
    return f"```{lang}\n{code}\n```"

def wrap_text(text, width=80):
    return textwrap.fill(text, width=width)

def confirm(prompt):
    try:
        ans = input(f"{prompt} [y/N] ").strip().lower()
        return ans in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


# Models that reject explicit sampling parameters. Per platform.zc.com/docs
# (checked 2026-07-02, "What's new in zAICoder Sonnet 5"): zAICoder Sonnet 5 returns
# a 400 invalid_request_error if temperature/top_p/top_k are set to non-default
# values at all. Any call site that hardcodes temperature=... needs to route
# through sampling_kwargs() instead of building the dict itself, or it will
# 400 the moment someone points it at zc-xxx (the default model in
# config.py / coder.py).
NO_SAMPLING_PARAMS_MODEL_PREFIXES = ("zc-xxx", "zc-fable-5", "zc-mythos-5")


def sampling_kwargs(model, temperature=None, top_p=None, top_k=None):
    """Build the temperature/top_p/top_k kwargs dict for a request, omitting
    all of them when `model` is one that 400s on explicit sampling params
    (Sonnet 5 and newer). Use this instead of hardcoding temperature=0.3 etc.
    directly into a payload/kwargs dict."""
    if model and str(model).startswith(NO_SAMPLING_PARAMS_MODEL_PREFIXES):
        return {}
    out = {}
    if temperature is not None: out["temperature"] = temperature
    if top_p is not None: out["top_p"] = top_p
    if top_k is not None: out["top_k"] = top_k
    return out