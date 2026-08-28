"""
zc_thinking.py — Extended Thinking & Adaptive Thinking
AI Model Coder CLI v1.30.0

Wraps the Anthropic SDK to expose:
  • Adaptive thinking  (thinking.type="adaptive" + top-level
    output_config.effort — GA, no beta header, the recommended path on
    zAICoder Opus 4.6+, Sonnet 4.6+, Sonnet 5, Opus 4.7/4.8, Fable 5,
    Mythos 5, Mythos Preview)
  • Legacy manual thinking (thinking.type="enabled" + budget_tokens —
    required on Opus 4.5, Haiku 4.5, and earlier zAICoder 4 models, since
    those don't support adaptive at all; deprecated-but-functional on
    Opus 4.6 / Sonnet 4.6; a 400 error on every newer model)
  • Effort levels      (low / medium / high / max)
  • Streaming thinking blocks
  • Thinking display   (show / hide / summary)

Model routing (see docs/42_upgrade_v1.30.0.md for the full audit):
  budget_tokens is a 400 error — not just deprecated — on zAICoder Opus
  4.8/4.7, zAICoder Sonnet 5, zAICoder Fable 5, zAICoder Mythos 5, and zAICoder
  Mythos Preview. This module now picks adaptive vs. legacy automatically
  per model (see ADAPTIVE_THINKING_MODELS / MANUAL_ONLY_MODELS below)
  instead of always sending budget_tokens, which broke --thinking outright
  on every current-generation model in zc_models.MODEL_CATALOG except
  Opus 4.5 and Haiku 4.5.

CLI flags added in main.py:
  --thinking                 Enable extended thinking
  --thinking-budget N        Token budget (legacy manual mode only)
  --effort low|medium|high|max
  --adaptive                 Force adaptive mode (auto-selected by
                              default on models that support it)
  --effort-legacy-budget     Force the old manual budget_tokens path
                              even on an adaptive-capable model (errors
                              out with a clear message on models where
                              budget_tokens is a hard 400, rather than
                              sending a request known to fail)
  --stream                   Stream the response (with thinking blocks)
  --show-thinking             Print thinking content to stderr
"""

import sys
from typing import Optional, Any, Dict

import anthropic

# ── Effort → budget mapping (legacy manual mode only) ──────────────────────
EFFORT_BUDGETS = {
    "low":    2_000,
    "medium": 8_000,
    "high":   16_000,
    "max":    32_000,
}

# Models where adaptive thinking is the modern, correct path.
# On Opus 4.6 / Sonnet 4.6, manual budget_tokens is deprecated but still
# accepted (--effort-legacy-budget can still target these). On every
# other model in this set, manual budget_tokens is a hard 400 error.
ADAPTIVE_THINKING_MODELS = {
    "zc-mythos-5", "zc-fable-5",
    "zc-opus-4-8", "zc-opus-4-7",
    "zc-xxx",
    "zc-opus-4-6", "zc-sonnet-4-6",
    "zc-mythos-preview",
}

# Models where budget_tokens is a hard 400 — adaptive is the *only*
# working mode, --effort-legacy-budget must refuse rather than fail late.
BUDGET_TOKENS_UNSUPPORTED_MODELS = {
    "zc-mythos-5", "zc-fable-5",
    "zc-opus-4-8", "zc-opus-4-7",
    "zc-xxx",
    "zc-mythos-preview",
}


def _model_key(model: str) -> str:
    # zc_models.MODEL_CATALOG ids are mostly bare ("claude-sonnet-5"),
    # but claude-haiku-4-5-20251001 carries a snapshot date — normalize by
    # matching on prefix membership so a dated snapshot id of a listed
    # model still routes correctly.
    if model in ADAPTIVE_THINKING_MODELS or model in BUDGET_TOKENS_UNSUPPORTED_MODELS:
        return model
    for known in ADAPTIVE_THINKING_MODELS | BUDGET_TOKENS_UNSUPPORTED_MODELS:
        if model.startswith(known):
            return known
    return model


def supports_adaptive_thinking(model: str) -> bool:
    return _model_key(model) in ADAPTIVE_THINKING_MODELS


def supports_manual_budget_tokens(model: str) -> bool:
    return _model_key(model) not in BUDGET_TOKENS_UNSUPPORTED_MODELS


class ThinkingModeError(ValueError):
    """Raised when the requested thinking mode can't work on this model
    (e.g. --effort-legacy-budget on a model where budget_tokens is a
    400), so the caller gets a clear message before an API round trip
    instead of after one."""


class ThinkingCoder:
    """zAICoder client with extended / adaptive thinking support."""

    def __init__(self, api_key: str, model: str = "zc-sonnet-4-6",
                 max_tokens: int = 8000):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model   = model
        self.max_tokens = max_tokens

    # ── Single-shot with thinking ──────────────────────────────────────────

    def generate_with_thinking(
        self,
        prompt: str,
        system: Optional[str] = None,
        budget_tokens: int = 8_000,
        effort: Optional[str] = None,
        adaptive: Optional[bool] = None,
        legacy_budget: bool = False,
        show_thinking: bool = False,
        display_omitted: bool = False,
    ) -> dict:
        """
        Returns {"thinking": str, "response": str, "usage": dict}

        Mode selection (see module docstring / docs/42_upgrade_v1.30.0.md):
          - `legacy_budget=True` forces the old manual
            `thinking.type="enabled"` + `budget_tokens` path. Raises
            `ThinkingModeError` immediately if `self.model` is one where
            that's a hard 400 (no wasted API round trip).
          - Otherwise, `adaptive` (True/False) picks the mode explicitly
            if given; if `adaptive` is None (the default), the mode is
            auto-selected from `self.model` via
            `supports_adaptive_thinking()`.
          - In adaptive mode, `effort` (low/medium/high/max) is sent as a
            top-level `output_config: {"effort": ...}` — NOT nested
            inside `thinking`, and `budget_tokens` is not sent at all
            (adaptive thinking doesn't take one). Effort defaults to the
            API's own default ("high") when not given.
          - In legacy mode, `effort` (if given) maps to a `budget_tokens`
            value via `EFFORT_BUDGETS`, same as before v1.30.0.

        `display_omitted` (v1.25.0; GA, no beta header), when True, sets
        `thinking.display: "omitted"`: the response's thinking block(s)
        come back with an empty `thinking` field but the `signature`
        preserved for multi-turn continuity — faster streaming/smaller
        payloads for a caller that doesn't render thinking text anyway.
        Billing is unchanged: thinking tokens are still generated and
        billed, only the response payload is thinner. Since the thinking
        text itself will be empty in this mode, `show_thinking` has
        nothing to print regardless of its value."""
        use_adaptive = self._resolve_mode(adaptive, legacy_budget)

        kwargs: Dict[str, Any] = dict(model=self.model, messages=[{"role": "user", "content": prompt}])
        if system:
            kwargs["system"] = system

        if use_adaptive:
            thinking_cfg: Dict[str, Any] = {"type": "adaptive"}
            if display_omitted:
                thinking_cfg["display"] = "omitted"
            kwargs["thinking"] = thinking_cfg
            kwargs["output_config"] = {"effort": effort or "high"}
            kwargs["max_tokens"] = self.max_tokens
        else:
            if effort and effort in EFFORT_BUDGETS:
                budget_tokens = EFFORT_BUDGETS[effort]
            thinking_cfg = {"type": "enabled", "budget_tokens": budget_tokens}
            if display_omitted:
                thinking_cfg["display"] = "omitted"
            kwargs["thinking"] = thinking_cfg
            kwargs["max_tokens"] = max(self.max_tokens, budget_tokens + 1000)

        resp = self.client.messages.create(**kwargs)

        thinking_text = ""
        response_text = ""
        for block in resp.content:
            if block.type == "thinking":
                thinking_text = block.thinking
            elif block.type == "text":
                response_text += block.text

        if show_thinking and thinking_text:
            print("\n\033[90m── THINKING ──────────────────────\033[0m", file=sys.stderr)
            print(thinking_text, file=sys.stderr)
            print("\033[90m── END THINKING ──────────────────\033[0m\n", file=sys.stderr)

        return {
            "thinking":  thinking_text,
            "response":  response_text,
            "usage":     resp.usage.model_dump() if hasattr(resp.usage, "model_dump") else {},
            "model":     self.model,
        }

    def _resolve_mode(self, adaptive: Optional[bool], legacy_budget: bool) -> bool:
        """Returns True for adaptive mode, False for legacy manual mode.
        Raises ThinkingModeError instead of building a request known to
        fail with a 400."""
        if legacy_budget:
            if not supports_manual_budget_tokens(self.model):
                raise ThinkingModeError(
                    f"--effort-legacy-budget can't be used with {self.model}: "
                    f"budget_tokens is not accepted by this model (400 error). "
                    f"Drop --effort-legacy-budget and use --effort instead."
                )
            return False
        if adaptive is not None:
            if adaptive and not supports_adaptive_thinking(self.model):
                raise ThinkingModeError(
                    f"{self.model} doesn't support adaptive thinking. "
                    f"Use --effort-legacy-budget with --thinking-budget/--effort instead."
                )
            return adaptive
        # Auto-select: prefer adaptive when the model supports it.
        return supports_adaptive_thinking(self.model)

    # ── Streaming with thinking ────────────────────────────────────────────

    def stream_with_thinking(
        self,
        prompt: str,
        system: Optional[str] = None,
        budget_tokens: int = 8_000,
        effort: Optional[str] = None,
        adaptive: Optional[bool] = None,
        legacy_budget: bool = False,
        show_thinking: bool = False,
        display_omitted: bool = False,
    ) -> str:
        """Stream response, optionally printing thinking blocks to stderr.

        Mode selection and `display_omitted` behave exactly as in
        `generate_with_thinking()` — see that method's docstring."""
        use_adaptive = self._resolve_mode(adaptive, legacy_budget)

        kwargs: Dict[str, Any] = dict(model=self.model, messages=[{"role": "user", "content": prompt}])
        if system:
            kwargs["system"] = system

        if use_adaptive:
            thinking_cfg: Dict[str, Any] = {"type": "adaptive"}
            if display_omitted:
                thinking_cfg["display"] = "omitted"
            kwargs["thinking"] = thinking_cfg
            kwargs["output_config"] = {"effort": effort or "high"}
            kwargs["max_tokens"] = self.max_tokens
        else:
            if effort and effort in EFFORT_BUDGETS:
                budget_tokens = EFFORT_BUDGETS[effort]
            thinking_cfg = {"type": "enabled", "budget_tokens": budget_tokens}
            if display_omitted:
                thinking_cfg["display"] = "omitted"
            kwargs["thinking"] = thinking_cfg
            kwargs["max_tokens"] = max(self.max_tokens, budget_tokens + 1000)

        full_response = ""
        in_thinking   = False

        with self.client.messages.stream(**kwargs) as stream:
            for event in stream:
                etype = getattr(event, "type", "")

                if etype == "content_block_start":
                    cb = getattr(event, "content_block", None)
                    bt = getattr(cb, "type", "") if cb else ""
                    if bt == "thinking":
                        in_thinking = True
                        if show_thinking:
                            print("\n\033[90m[thinking] ", end="", file=sys.stderr, flush=True)
                    elif bt == "text":
                        in_thinking = False

                elif etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta:
                        dt = getattr(delta, "type", "")
                        if dt == "thinking_delta" and show_thinking:
                            print(getattr(delta, "thinking", ""), end="", file=sys.stderr, flush=True)
                        elif dt == "text_delta":
                            text_val = getattr(delta, "text", "")
                            print(text_val, end="", flush=True)
                            full_response += text_val

                elif etype == "content_block_stop" and in_thinking and show_thinking:
                    print("\033[0m", file=sys.stderr)
                    in_thinking = False

        print()  # newline after streaming
        return full_response


# ── CLI entry points ───────────────────────────────────────────────────────

def cmd_thinking(prompt: str, api_key: str, model: str, budget: int,
                 effort: str, adaptive: Optional[bool], show_thinking: bool,
                 stream: bool, system: Optional[str] = None, display_omitted: bool = False,
                 legacy_budget: bool = False):
    """Called from main.py --thinking.

    `adaptive`: True/False forces a mode; None (main.py's default when
    --adaptive isn't passed) auto-selects per model. `legacy_budget`
    (main.py's --effort-legacy-budget) forces the old manual budget_tokens
    path, and raises a clear ThinkingModeError up front on models where
    that's a 400 rather than sending a doomed request.
    """
    tc = ThinkingCoder(api_key=api_key, model=model)

    mode = "adaptive" if tc._resolve_mode(adaptive, legacy_budget) else "manual budget_tokens"
    print(f"\033[94mℹ Extended Thinking | mode={mode} | effort={effort or 'default'} | "
          f"budget={budget} tokens (manual mode only)\033[0m\n")

    if stream:
        stream_res = tc.stream_with_thinking(
            prompt, system=system, budget_tokens=budget,
            effort=effort, adaptive=adaptive, legacy_budget=legacy_budget,
            show_thinking=show_thinking, display_omitted=display_omitted,
        )
        return stream_res
    else:
        gen_res = tc.generate_with_thinking(
            prompt, system=system, budget_tokens=budget,
            effort=effort, adaptive=adaptive, legacy_budget=legacy_budget,
            show_thinking=show_thinking, display_omitted=display_omitted,
        )
        print(gen_res.get("response", ""))
        usage = gen_res.get("usage", {})
        if isinstance(usage, dict):
            details = usage.get("output_tokens_details", {})
            thinking_tokens = details.get("thinking_tokens", 0) if isinstance(details, dict) else 0
            print(f"\n\033[90m[tokens] input={usage.get('input_tokens',0)}  "
                  f"output={usage.get('output_tokens',0)}  "
                  f"thinking={thinking_tokens}\033[0m")
        return gen_res.get("response", "")
