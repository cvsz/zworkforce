"""
zc_mythos5.py — zAICoder Mythos 5 support (companion to zc_fable5.py)
AI Model Coder CLI v1.10.1

IMPORTANT — confidence note, more pointed than zc_fable5.py's: everything
below is sourced from the same web search results as zc_fable5.py, and
Mythos 5 is described as *limited-availability, approval-gated* access
(Project Glasswing) on top of the general uncertainty already flagged there.
I have no way to independently confirm the model ID, pricing, or even that
Mythos 5 is reachable via the standard Messages API rather than some
separate gated endpoint. Treat this module as a convenience wrapper for
*if and when* you have confirmed access — not as evidence that access
works this way. Verify at https://platform.zc.com/docs and with your
Anthropic/AWS/Google Cloud account team before relying on anything here.

Why this is a separate, thinner module rather than folding into
zc_fable5.py: Mythos 5 is documented as the same underlying model as
Fable 5 *without* the safety classifiers — so there is no refusal/fallback
mechanic to implement here. That's not an oversight; a model with no
refusal classifier has nothing to fall back from. This module is
deliberately smaller than zc_fable5.py because there is genuinely
less to build: an access-gate check, an info command, and a plain call.

UPDATE (2026-07-02): both Mythos-class models were suspended
2026-06-12 through 2026-06-30 for US export-control compliance and
restored 2026-07-01. A 403/404 today is therefore more likely a
Project Glasswing access-gate rejection (see MythosAccessError below)
than a lingering effect of that suspension — but if you tested this
during that window and got blocked, retry now.

CLI flags:
  --mythos5-info               Show what's known about Mythos 5 access/pricing
  --mythos5 PROMPT              Call zAICoder Mythos 5 directly (no refusal handling —
                                 see note above on why)
"""

import json
import urllib.error
import urllib.request
from typing import Optional

from wire.zc_fable5 import FABLE_MYTHOS_INFO, MESSAGES_ENDPOINT, MYTHOS5_MODEL_ID
from wire.exceptions import AICoderError, APIError
from wire.resilience import CircuitBreaker, retry, urlopen_json

_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)

# Re-exported for convenience so callers don't need to import zc_fable5
# directly just to get the model ID or info table.
__all__ = ["MYTHOS5_MODEL_ID", "MythosAccessError", "Mythos5Client",
          "cmd_mythos5_info", "cmd_mythos5_call"]


class MythosAccessError(Exception):
    """Raised when a Mythos 5 call fails in a way that looks like an access-gate
    rejection (HTTP 403/404 on the model ID) rather than an ordinary API error,
    so the caller gets a pointed message instead of a generic stack trace."""
    pass


class Mythos5Client:
    """Minimal Messages API client for zc-mythos-5. No refusal/fallback
    handling — see module docstring for why. Follows the same _post() pattern
    as Fable5Client in zc_fable5.py for consistency."""

    def __init__(self, api_key: str, max_tokens: int = 4096):
        self.api_key = api_key
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(
            MESSAGES_ENDPOINT, data=json.dumps(payload).encode(),
            headers=headers, method="POST",
        )
        return urlopen_json(req, timeout=300)

    def _post(self, payload: dict) -> dict:
        try:
            return self._call(payload)
        except APIError as e:
            if e.status_code in (403, 404):
                body = e.details.get("body", "")
                raise MythosAccessError(
                    f"HTTP {e.status_code} calling zc-mythos-5 — this looks like an "
                    "access-gate rejection rather than a normal API error. Mythos 5 "
                    "requires approved Project Glasswing access; most accounts will "
                    "see this. Use zc-fable-5 instead unless you've confirmed "
                    f"access with Anthropic. Raw response: {body}"
                )
            return {"error": e.message, "status": e.status_code}
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def call(self, prompt: str, system: Optional[str] = None) -> dict:
        payload = {
            "model": MYTHOS5_MODEL_ID,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        return self._post(payload)

    def call_text(self, prompt: str, system: Optional[str] = None) -> str:
        """Convenience wrapper returning just the response text (or an
        [ERROR] string), for callers that don't need the raw response dict."""
        data = self.call(prompt, system=system)
        if "error" in data:
            return f"[ERROR] {data['error']}"
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def cmd_mythos5_info():
    info = FABLE_MYTHOS_INFO[MYTHOS5_MODEL_ID]
    print("\n\033[94mzAICoder Mythos 5\033[0m")
    print("\033[93m⚠ Sourced from the same uncertain web search results as zc_fable5.py.\033[0m")
    print("\033[93m  Access is described as limited/approval-gated (Project Glasswing) —\033[0m")
    print("\033[93m  most accounts will not have this. Verify before relying on anything below.\033[0m\n")
    print(f"    Class:            {info['class']}")
    print(f"    Context window:   {info['context_window']:,} tokens")
    print(f"    Max output:       {info['max_output_tokens']:,} tokens")
    print(f"    Pricing:          ${info['price_input_per_mtok_usd']}/MTok in, "
         f"${info['price_output_per_mtok_usd']}/MTok out")
    print(f"    Data retention:   {info['data_retention']}")
    print("    Safety classifiers: no (unlike Fable 5 — see zc_fable5.py)")
    print(f"    Notes:            {info['notes']}")
    print("\n  To request access: contact your Anthropic, AWS, or Google Cloud account team")
    print("  about Project Glasswing. See also: --fable5-info for the publicly available sibling model.\n")


def cmd_mythos5_call(prompt: str, api_key: str, system: Optional[str] = None):
    client = Mythos5Client(api_key=api_key)
    try:
        text = client.call_text(prompt, system=system)
    except MythosAccessError as e:
        print(f"\033[91m✗ {e}\033[0m")
        return None
    print(text)
    return text
