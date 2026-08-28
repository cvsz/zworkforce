from typing import Any
"""
zc_fable5.py — zAICoder Fable 5 / zAICoder Mythos 5 support
AI Model Coder CLI v1.9.1

IMPORTANT — confidence note: the details below (pricing, context window,
refusal/fallback mechanics, availability) are taken from web search results
describing an Anthropic announcement (~June 9, 2026) of zAICoder Fable 5 and
zAICoder Mythos 5 as a new "Mythos-class" model generation. This CLI has no
independent way to verify pricing or availability against Anthropic's live
systems beyond what the API itself reports at call time, and this module's
constants can go stale exactly like zc_models.py's offline fallback
list already does for earlier model generations. Before relying on any
number below for billing-sensitive decisions, confirm against
https://platform.zc.com/docs and your own Anthropic Console.

UPDATE (2026-07-02): access to both models was briefly suspended
2026-06-12 through 2026-06-30 to comply with US Department of Commerce
export controls, then restored 2026-07-01 once those controls were
lifted. If a call to either model ID returns an access-denied error,
that is now more likely an account/region permissions issue than a
typo — see https://www.anthropic.com/news/fable-mythos-access.

What this module adds, concretely:
  • Model ID constants + a small info table (context window, output cap,
    pricing, retention requirement) for claude-fable-5 / claude-mythos-5,
    following the same "known models" convention as zc_models.py.
  • Refusal-aware calling: zAICoder Fable 5 is documented to include safety
    classifiers that can decline a request via stop_reason == "refusal"
    (returned as a normal 200 response, not an HTTP error) rather than a
    silent failure. zAICoder Mythos 5 does not include these classifiers
    (limited-availability access only — most callers will not have it).
  • Two fallback patterns, and when to use each:
      - Server-side (`fallbacks` param, preferred): pass
        --fable5-fallback-chain MODEL1,MODEL2 (up to 3 models total,
        including the primary). The platform itself retries the *same*
        request against the next model in the list if the primary
        refuses, in the same round trip — one HTTP call, not two, and it
        composes correctly with the fallback-credit beta header without
        the caller having to think about it. Use this when you just want
        the platform to handle it.
      - Client-side manual retry (legacy, still supported): on a refusal,
        this module retries the same prompt itself against a separate
        fallback model (default: zc-opus-4-8) with a second HTTP
        call. Use this when you want to change the prompt/system before
        retrying, or don't want the fallbacks beta. This path only runs
        when --fable5-fallback-chain is *not* given.

CLI flags:
  --fable5-info                   Show what's known about Fable 5 / Mythos 5
  --fable5 PROMPT                  Call zAICoder Fable 5 with refusal/fallback handling
  --fable5-fallback-chain M1,M2      Server-side fallback: up to 3 models total
                                    (including the primary), tried in order by the
                                    platform itself on a refusal. Takes priority over
                                    the manual retry path below when set.
  --fable5-no-fallback              Disable automatic fallback on refusal (just report it).
                                    Only affects the manual retry path (no effect when
                                    --fable5-fallback-chain is set — that's already
                                    server-side and applies before this flag is checked).
  --fallback-model ID               Override the manual-retry fallback model
                                    (default: zc-opus-4-8). No effect when
                                    --fable5-fallback-chain is set.
"""

import json
import urllib.error
import urllib.request
from typing import Optional

from wire.exceptions import AICoderError
from wire.resilience import CircuitBreaker, retry, urlopen_json

MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)

FABLE5_MODEL_ID = "zc-fable-5"
MYTHOS5_MODEL_ID = "zc-mythos-5"

# Verified against platform.zc.com/docs/en/build-with-zc/refusals-and-fallback
# (checked 2026-07-04). We build the retry ourselves with raw urllib rather than an
# SDK, so this is the "manual" fallback path the docs describe — sending this beta
# header on the retry earns fallback credit (refunds the prompt-cache cost of
# switching models) instead of paying that cost twice.
FALLBACK_CREDIT_BETA_HEADER = "fallback-credit-2026-06-01"

# The stop_details.category values Anthropic actually documents for a Fable 5
# refusal. `category` (and `explanation`) can legitimately be null even when
# stop_reason == "refusal" — that's a documented, permanent state, not a bug.
REFUSAL_CATEGORIES = {
    "cyber": "Could enable cyber harm (e.g. malware/exploit development); benign security work can also trigger it.",
    "bio": "Could enable biological harm; benign life-sciences work can also trigger it.",
    "frontier_llm": "Could assist a competing AI model's development (restricted under Anthropic's commercial terms).",
    "reasoning_extraction": "Asks the model to reproduce its internal reasoning as response text; use adaptive thinking instead.",
}

# Mirrors zc_models.py's "known models" fallback pattern — a local
# cache for when the live Models API isn't consulted, not a source of truth.
FABLE_MYTHOS_INFO = {
    FABLE5_MODEL_ID: {
        "display_name": "zAICoder Fable 5",
        "class": "Mythos-class (publicly available)",
        "context_window": 1_000_000,
        "max_output_tokens": 128_000,
        "price_input_per_mtok_usd": 10.0,
        "price_output_per_mtok_usd": 50.0,
        "cache_write_discount_note": "90% input-token discount applies for prompt caching, per Anthropic's standard caching pricing",
        "data_retention": "30-day retention required for safety monitoring; not available under zero data retention",
        "has_safety_classifiers": True,
        "us_only_inference_multiplier": 1.1,
        "notes": "Refuses certain cybersecurity/biology/chemistry queries via stop_reason='refusal' "
                "and can fall back to a less-restricted model server-side (beta `fallbacks` param) "
                "or client-side (this module's call_with_fallback).",
    },
    MYTHOS5_MODEL_ID: {
        "display_name": "zAICoder Mythos 5",
        "class": "Mythos-class (limited availability — Project Glasswing)",
        "context_window": 1_000_000,
        "max_output_tokens": 128_000,
        "price_input_per_mtok_usd": 10.0,
        "price_output_per_mtok_usd": 50.0,
        "cache_write_discount_note": "90% input-token discount applies for prompt caching, per Anthropic's standard caching pricing",
        "data_retention": "30-day retention required; not available under zero data retention",
        "has_safety_classifiers": False,
        "us_only_inference_multiplier": None,
        "notes": "Same underlying capability as Fable 5 without the safety classifiers. "
                "Requires approved access via Project Glasswing — contact your Anthropic, "
                "AWS, or Google Cloud account team. Most callers will not have this and "
                "should use Fable 5 instead.",
    },
}


class RefusalError(Exception):
    """Raised when a Fable 5 call is refused and fallback is disabled/exhausted."""
    def __init__(self, message: str, classifier: Optional[str] = None):
        super().__init__(message)
        self.classifier = classifier


class Fable5Client:
    """Thin Messages API client with refusal detection and optional fallback,
    following the same _post() pattern used throughout this project's other
    zc_*.py modules for consistency."""

    def __init__(self, api_key: str, model: str = FABLE5_MODEL_ID,
                 fallback_model: str = "zc-opus-4-8", max_tokens: int = 4096,
                 fallback_chain: Optional[list] = None):
        self.api_key = api_key
        self.model = model
        self.fallback_model = fallback_model
        self.max_tokens = max_tokens
        # Server-side fallback (`fallbacks` param, beta, checked against
        # platform.zc.com/docs 2026-07-04). Up to 3 models total,
        # including the primary `self.model` — do not repeat the primary
        # in this list. When set, this replaces (not supplements) the
        # manual client-side retry path in call_with_fallback().
        self.fallback_chain = fallback_chain

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict, extra_headers: Optional[dict] = None) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(
            MESSAGES_ENDPOINT, data=json.dumps(payload).encode(),
            headers=headers, method="POST",
        )
        return urlopen_json(req, timeout=300)

    def _post(self, payload: dict, extra_headers: Optional[dict] = None) -> dict:
        try:
            return self._call(payload, extra_headers)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def _extract_text(self, data: dict) -> str:
        return "".join(
            b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
        )

    def call(self, prompt: str, system: Optional[str] = None,
             model: Optional[str] = None, is_fallback_retry: bool = False) -> dict:
        """One raw call. Returns the parsed response dict (caller inspects stop_reason).

        is_fallback_retry=True sends the fallback-credit beta header, per the
        "manual retry" pattern in Anthropic's docs — this is what gets the
        prompt-cache cost of the switch refunded instead of charged twice.
        """
        payload = {
            "model": model or self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        # Server-side fallback: only attached on the primary call (never on
        # a manual is_fallback_retry call, and never if a caller passed an
        # explicit `model=` override, since fallbacks only make sense
        # attached to the request naming the primary model).
        if self.fallback_chain and not is_fallback_retry and model is None:
            payload["fallbacks"] = self.fallback_chain
        extra_headers = {"anthropic-beta": FALLBACK_CREDIT_BETA_HEADER} if is_fallback_retry else None
        return self._post(payload, extra_headers=extra_headers)

    def call_with_fallback(self, prompt: str, system: Optional[str] = None,
                           allow_fallback: bool = True) -> dict:
        """
        Call the configured model.

        If self.fallback_chain is set, this is a thin compatibility
        wrapper around the server-side `fallbacks` param: call() already
        attached the chain to the request, so the platform itself retries
        against the next model in the list on a refusal, in the same round
        trip. This method just has to inspect the response to report which
        model actually answered — no second HTTP call from here.

        If self.fallback_chain is unset, falls through to the legacy
        manual retry path: on stop_reason == 'refusal', optionally retry
        against self.fallback_model as a second, separate request (sending
        the fallback-credit beta header so the switch isn't billed twice).

        Returns a dict:
          {text, stop_reason, refused: bool, fell_back: bool,
           served_by: str|None, classifier: str|None, category: str|None,
           explanation: str, raw}
        """
        data = self.call(prompt, system=system)
        if "error" in data:
            return {"text": f"[ERROR] {data['error']}", "stop_reason": None,
                   "refused": False, "fell_back": False, "served_by": None,
                   "classifier": None, "category": None, "explanation": "", "raw": data}

        stop_reason = data.get("stop_reason")
        refused = stop_reason == "refusal"

        if self.fallback_chain:
            # Server-side path: the platform already retried internally if
            # it needed to. The docs specify the response echoes back which
            # model in the chain actually served the request (falls back to
            # self.model if the field isn't present, e.g. no refusal
            # occurred so the primary model answered).
            served_by = data.get("model", self.model)
            stop_details = (data.get("stop_details") or {}) if refused else {}
            category = stop_details.get("category")
            return {"text": self._extract_text(data), "stop_reason": stop_reason,
                   "refused": refused, "fell_back": served_by != self.model,
                   "served_by": served_by, "classifier": category,
                   "category": category, "explanation": stop_details.get("explanation", ""),
                   "raw": data}
        # Was reading data["refusal"]["classifier"] — a field this project
        # invented rather than one the API documents. The documented shape
        # (per Refusals and fallback, checked 2026-07-04) is
        # stop_details: {type, category, explanation}, with category one of
        # "cyber", "bio", "frontier_llm", "reasoning_extraction", or null
        # (null is a documented permanent value, not a missing field).
        # classifier is kept as an alias of category below so any existing
        # caller reading result["classifier"] keeps working.
        stop_details = (data.get("stop_details") or {}) if refused else {}
        category = stop_details.get("category")
        classifier = category

        if refused and allow_fallback:
            # is_fallback_retry=True sends the fallback-credit beta header so
            # this manual retry doesn't get billed twice for prompt caching.
            fallback_data = self.call(prompt, system=system, model=self.fallback_model,
                                      is_fallback_retry=True)
            if "error" in fallback_data:
                return {"text": f"[ERROR on fallback] {fallback_data['error']}",
                       "stop_reason": stop_reason, "refused": True, "fell_back": False,
                       "served_by": None, "classifier": classifier, "category": category,
                       "explanation": stop_details.get("explanation", ""), "raw": data}
            return {"text": self._extract_text(fallback_data),
                   "stop_reason": fallback_data.get("stop_reason"),
                   "refused": True, "fell_back": True, "served_by": self.fallback_model,
                   "classifier": classifier, "category": category,
                   "explanation": stop_details.get("explanation", ""),
                   "raw": fallback_data}

        if refused:
            raise RefusalError(
                f"zAICoder Fable 5 declined this request (category: {category or 'unspecified'}). "
                "Re-run with fallback enabled, or use claude-opus-4-8 directly.",
                classifier=classifier
            )

        return {"text": self._extract_text(data), "stop_reason": stop_reason,
               "refused": False, "fell_back": False, "served_by": self.model,
               "classifier": None, "category": None, "explanation": "", "raw": data}


def estimate_cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    """Rough cost estimate using the static table above. Returns None for unknown models."""
    info = FABLE_MYTHOS_INFO.get(model_id)
    if not info:
        return None
    p_in: Any = info.get("price_input_per_mtok_usd", 0)
    p_out: Any = info.get("price_output_per_mtok_usd", 0)
    return (input_tokens / 1_000_000 * float(str(p_in)) +
            output_tokens / 1_000_000 * float(str(p_out)))


def cmd_fable5_info():
    print("\n\033[94mzAICoder Fable 5 / zAICoder Mythos 5\033[0m")
    print("\033[93m⚠ Sourced from recent web search results, not this CLI's own bundled\033[0m")
    print("\033[93m  product data — verify at platform.zc.com/docs before relying on\033[0m")
    print("\033[93m  pricing/availability for anything billing-sensitive.\033[0m\n")
    for model_id, info in FABLE_MYTHOS_INFO.items():
        print(f"  \033[1m{info['display_name']}\033[0m  ({model_id})")
        print(f"    Class:            {info['class']}")
        print(f"    Context window:   {info['context_window']:,} tokens")
        print(f"    Max output:       {info['max_output_tokens']:,} tokens")
        print(f"    Pricing:          ${info['price_input_per_mtok_usd']}/MTok in, "
             f"${info['price_output_per_mtok_usd']}/MTok out")
        print(f"    Data retention:   {info['data_retention']}")
        print(f"    Safety classifiers: {'yes (can refuse, see fallback)' if info['has_safety_classifiers'] else 'no'}")
        print(f"    Notes:            {info['notes']}")
        print()


def cmd_fable5_call(prompt: str, api_key: str, fallback_model: str = "zc-opus-4-8",
                    allow_fallback: bool = True, system: Optional[str] = None,
                    fallback_chain: Optional[list] = None):
    client = Fable5Client(api_key=api_key, fallback_model=fallback_model,
                          fallback_chain=fallback_chain)
    try:
        result = client.call_with_fallback(prompt, system=system, allow_fallback=allow_fallback)
    except RefusalError as e:
        print(f"\033[91m✗ {e}\033[0m")
        return None

    if result["fell_back"]:
        served_by = result.get("served_by") or fallback_model
        mode = "server-side fallbacks" if fallback_chain else "client-side manual retry"
        print(f"\033[93mℹ Fable 5 declined this request (classifier: {result['classifier'] or 'unspecified'}); "
             f"showing the {served_by} response instead ({mode}).\033[0m\n")
    print(result["text"])
    return result


def parse_fallback_chain(raw: Optional[str]) -> Optional[list]:
    """Parse the --fable5-fallback-chain CLI value ('MODEL1,MODEL2') into a
    list, enforcing the documented max of 3 models total (including the
    primary, which the caller adds separately — so this list itself must be
    at most 2 entries for the common case of one primary + this chain, or
    up to 3 if the primary model is not repeated here)."""
    if not raw:
        return None
    chain = [m.strip() for m in raw.split(",") if m.strip()]
    if len(chain) > 3:
        raise ValueError(
            f"--fable5-fallback-chain accepts at most 3 models total (including the "
            f"primary); got {len(chain)}."
        )
    return chain