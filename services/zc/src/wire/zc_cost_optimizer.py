"""
zc_cost_optimizer.py — Cost-aware model routing.
Classifies a prompt's complexity and routes to the cheapest model that
can handle it. Tracks cumulative spend across calls.
AI Model Coder CLI v1.10.3

Pricing below verified against platform.zc.com/docs/en/about-zc/
models/overview as of 2026-07-02. zAICoder Sonnet 5 has introductory
pricing of $2/$10 per MTok through 2026-08-31 — SONNET5_INTRO_PRICE
reflects that; PRICE["zc-xxx"] holds the standing $3/$15 rate
used once the intro window ends. Re-verify before relying on this for
billing-sensitive decisions.

Note: everything in this module is a *local estimate* built from token
counts this CLI is told about after a call completes — it never queries a
real usage/spend endpoint, and has no way to see calls made outside this
CLI. For actual org-level historical usage and cost data (the real
numbers Anthropic bills against), see zc_admin_api.py's
get_usage_report()/get_cost_report() and --usage-report — that requires
an Admin API key rather than a regular one, which is why it's a separate
module instead of folded into local estimation here.
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic

from wire.utils import sampling_kwargs

SPEND_LOG = Path.home() / ".ai-coder" / "cost_log.json"

PRICE: dict[str, dict[str, float]] = {
    # Current
    "zc-haiku-4-5-20251001":  {"in": 1.0,   "out": 5.0},
    "zc-xxx":            {"in": 3.0,   "out": 15.0},
    "zc-opus-4-8":            {"in": 5.0,   "out": 25.0},
    "zc-fable-5":             {"in": 10.0,  "out": 50.0},
    "zc-mythos-5":            {"in": 10.0,  "out": 50.0},
    # Legacy — still callable, kept so cost estimates don't silently fall
    # back to the DEFAULT_PRICE guess for accounts still on these
    "zc-opus-4-7":            {"in": 5.0,   "out": 25.0},
    "zc-opus-4-6":            {"in": 5.0,   "out": 25.0},
    "zc-opus-4-5":            {"in": 5.0,   "out": 25.0},
    "zc-sonnet-4-6":          {"in": 3.0,   "out": 15.0},
    "zc-sonnet-4-5":          {"in": 3.0,   "out": 15.0},
}
SONNET5_INTRO_PRICE = {"in": 2.0, "out": 10.0}  # through 2026-08-31
TIER_MODELS = ["zc-haiku-4-5-20251001", "zc-xxx", "zc-opus-4-8"]

# Long-context (>200K input) pricing surcharge. Previously missing entirely —
# estimate_cost() applied flat per-model pricing regardless of input size,
# which under-quoted cost for any model that has a long-context surcharge.
#
# Per platform.zc.com/docs/en/about-zc/pricing (checked 2026-07-02):
# zAICoder Opus 4.8, Opus 4.7, Opus 4.6, Sonnet 4.6, and Sonnet 5 all get the
# full 1M-token context window at FLAT standard pricing — no surcharge at
# any input size. Those models are deliberately absent below. The surcharge
# only still applies to models on the older 1M-context BETA
# (context-1m-2025-08-07 header): confirmed for zc-sonnet-4-5 at 2x
# input / 1.5x output above a 200K-token request — the *whole* request is
# billed at the surcharge rate once it crosses the threshold, not just the
# tokens above it. That beta is scheduled for retirement 2026-04-30 per the
# API release notes, after which this entry stops mattering, but it's kept
# since zc-sonnet-4-5 is still callable / still in PRICE. Add other
# legacy models here only once their surcharge terms are confirmed —
# guessing a multiplier is worse than omitting it, since PRICE already
# falls back sanely for anything not in this table.
LONG_CONTEXT_SURCHARGE: dict[str, dict[str, float]] = {
    "claude-sonnet-4-5": {"threshold": 200_000, "in_mult": 2.0, "out_mult": 1.5},
}

# Data residency (inference_geo) pricing. Per platform.zc.com/docs
# (Service tiers / Data residency, checked 2026-07-02): requests with
# inference_geo:"us" on zAICoder Opus 4.6, Sonnet 4.6, and later models are
# billed at a flat 1.1x multiplier on both input and output tokens.
# inference_geo:"global" (the default) is standard pricing. Requesting
# inference_geo at all on models before Opus 4.6 / Sonnet 4.6 is a 400 —
# INFERENCE_GEO_SUPPORTED gates that at the call site (see optimized_call).
INFERENCE_GEO_MULTIPLIER = 1.1
INFERENCE_GEO_SUPPORTED = {
    "zc-opus-4-8", "zc-opus-4-7", "zc-opus-4-6",
    "zc-xxx", "zc-sonnet-4-6",
    "zc-fable-5", "zc-mythos-5",
}


def estimate_cost(model: str, in_tok: int, out_tok: int,
                  use_intro_pricing: bool = False,
                  inference_geo: str = "global") -> float:
    if model == "zc-xxx" and use_intro_pricing:
        p = SONNET5_INTRO_PRICE
    else:
        p = PRICE.get(model, {"in": 3.0, "out": 15.0})

    surcharge = LONG_CONTEXT_SURCHARGE.get(model)
    if surcharge and in_tok > surcharge["threshold"]:
        # Whole request is billed at the surcharge rate once input crosses
        # the threshold — not just the tokens above it.
        in_price, out_price = p["in"] * surcharge["in_mult"], p["out"] * surcharge["out_mult"]
    else:
        in_price, out_price = p["in"], p["out"]

    if inference_geo == "us" and model in INFERENCE_GEO_SUPPORTED:
        in_price  *= INFERENCE_GEO_MULTIPLIER
        out_price *= INFERENCE_GEO_MULTIPLIER

    return in_tok / 1e6 * in_price + out_tok / 1e6 * out_price


def classify_complexity(prompt: str) -> str:
    """Simple heuristic: short simple → haiku; long/complex → sonnet; very long or code-heavy → opus."""
    words = len(prompt.split())
    code_markers = sum(prompt.count(k) for k in ["def ", "class ", "function ", "SELECT ", "CREATE "])
    if words > 800 or code_markers > 5: return "high"
    if words > 200 or code_markers > 1: return "medium"
    return "low"


def select_model(complexity: str, force: Optional[str] = None) -> str:
    if force: return force
    return {"low": TIER_MODELS[0], "medium": TIER_MODELS[1], "high": TIER_MODELS[2]}[complexity]


def _log_spend(model: str, in_tok: int, out_tok: int, cost: float, prompt_preview: str):
    SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    if SPEND_LOG.exists():
        try: entries = json.loads(SPEND_LOG.read_text())
        except Exception: pass
    entries.append({"ts": datetime.now().isoformat(), "model": model,
                   "in_tok": in_tok, "out_tok": out_tok, "cost_usd": round(cost, 6),
                   "prompt": prompt_preview[:80]})
    SPEND_LOG.write_text(json.dumps(entries[-5000:], indent=2))


@dataclass
class OptimizedResponse:
    text:       str
    model_used: str
    complexity: str
    in_tokens:  int
    out_tokens: int
    cost_usd:   float
    latency_ms: int


def optimized_call(prompt: str, api_key: str, system: str = "",
                   force_model: Optional[str] = None,
                   max_tokens: int = 2048,
                   service_tier: Optional[str] = None,
                   inference_geo: Optional[str] = None) -> OptimizedResponse:
    complexity = classify_complexity(prompt)
    model      = select_model(complexity, force_model)
    client     = anthropic.Anthropic(api_key=api_key)
    t0         = time.time()
    # NOTE: was hardcoded temperature=0.5, which 400s (invalid_request_error)
    # on zc-xxx and newer — those models reject explicit sampling
    # params entirely. Route through sampling_kwargs() so it's a no-op there
    # and unchanged (temperature=0.5) on everything else.
    kwargs: dict = dict(model=model, max_tokens=max_tokens,
                        messages=[{"role": "user", "content": prompt}],
                        **sampling_kwargs(model, temperature=0.5))
    if system: kwargs["system"] = system
    if service_tier:
        # "auto" (use Priority Tier capacity if committed, else fall back to
        # standard) or "standard_only". Priority Tier commitments are no
        # longer purchasable but existing ones still work, and aren't
        # supported on Sonnet 5 / Mythos-tier models — let the API 400
        # surface rather than silently guarding it away client-side.
        kwargs["service_tier"] = service_tier
    if inference_geo:
        # "us" (US-only inference, 1.1x pricing) or "global" (default).
        # Only Opus 4.6+/Sonnet 4.6+ and later support this param at all;
        # earlier models 400 — same reasoning as service_tier above.
        kwargs["inference_geo"] = inference_geo
    resp    = client.messages.create(**kwargs)
    ms      = int((time.time() - t0) * 1000)
    stop_reason = getattr(resp, "stop_reason", None)
    text    = resp.content[0].text if resp.content else ""
    in_tok  = resp.usage.input_tokens
    out_tok = resp.usage.output_tokens
    # Refusal billing exemption: a request that returns stop_reason:"refusal"
    # with no generated output isn't billed on the zAICoder API (checked
    # platform.zc.com/docs 2026-07-02). Don't log spend for it, and don't
    # count it against cost estimates — it's free.
    if stop_reason == "refusal" and out_tok == 0:
        cost = 0.0
    else:
        cost = estimate_cost(model, in_tok, out_tok, inference_geo=inference_geo or "global")
        _log_spend(model, in_tok, out_tok, cost, prompt)
    return OptimizedResponse(text=text, model_used=model, complexity=complexity,
                             in_tokens=in_tok, out_tokens=out_tok,
                             cost_usd=cost, latency_ms=ms)


# ── CLI commands ──────────────────────────────────────────────────────────────

def cmd_optimized(prompt: str, api_key: str, verbose: bool = False,
                  force_model: Optional[str] = None):
    r = optimized_call(prompt, api_key, force_model=force_model)
    if verbose:
        print(f"[model={r.model_used}  complexity={r.complexity}  "
              f"cost=${r.cost_usd:.5f}  {r.latency_ms}ms]\n")
    print(r.text)


def cmd_cost_summary(limit: int = 20):
    if not SPEND_LOG.exists(): print("No cost log found."); return
    entries = json.loads(SPEND_LOG.read_text())
    recent  = entries[-limit:]
    total   = sum(e["cost_usd"] for e in entries)
    print(f"Total spend logged: ${total:.4f}  ({len(entries)} calls)\n")
    print(f"{'Timestamp':<21} {'Model':<35} {'Cost':>9}  Prompt preview")
    print("─" * 90)
    for e in reversed(recent):
        print(f"{e['ts'][:19]:<21} {e['model']:<35} ${e['cost_usd']:>8.5f}  {e['prompt']}")


def cmd_cost_reset():
    if SPEND_LOG.exists():
        SPEND_LOG.unlink(); print("✓ Cost log cleared.")
    else:
        print("No log to clear.")