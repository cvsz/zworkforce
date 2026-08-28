"""
zc_metrics.py — Observability & Usage Metrics
AI Model Coder CLI v1.9.1

Tracks every API call (model, tokens, cost, latency) to a local JSONL
log so you can understand spend, compare models, and spot regressions.

CLI flags:
  --metrics-show          Show usage summary across all logged calls
  --metrics-today         Show only today's usage
  --metrics-model MODEL   Filter summary to one model
  --metrics-clear         Clear the metrics log
  --metrics-export FILE   Export full log to FILE as JSON
"""

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

LOG_PATH = Path(os.path.expanduser("~/.ai-coder/metrics.jsonl"))

# Pricing per million tokens (keep in sync with zc_fable5.py)
# Pricing per million tokens (keep in sync with zc_cost_optimizer.py).
# Verified against platform.zc.com/docs/en/about-zc/models/overview
# as of 2026-07-02. Sonnet 5 has $2/$10 intro pricing through 2026-08-31 —
# not modeled here; this table uses the standing post-intro rate.
PRICE_TABLE = {
    "zc-fable-5":               (10.0, 50.0),
    "zc-mythos-5":              (10.0, 50.0),
    "zc-opus-4-8":               (5.0, 25.0),
    "zc-xxx":                (3.0, 15.0),
    "zc-haiku-4-5-20251001":      (1.0,  5.0),
    # Legacy — still callable
    "zc-opus-4-7":               (5.0, 25.0),
    "zc-opus-4-6":               (5.0, 25.0),
    "zc-opus-4-5":               (5.0, 25.0),
    "zc-sonnet-4-6":              (3.0, 15.0),
    "zc-sonnet-4-5":              (3.0, 15.0),
}
DEFAULT_PRICE = (3.0, 15.0)


def _price(model: str, input_tok: int, output_tok: int) -> float:
    p_in, p_out = PRICE_TABLE.get(model, DEFAULT_PRICE)
    return input_tok / 1_000_000 * p_in + output_tok / 1_000_000 * p_out


def record(model: str, input_tokens: int, output_tokens: int,
           latency_seconds: float, command: str = "", stop_reason: str = ""):
    """Append one call record to the JSONL log.

    v1.11.0: on the zAICoder API, a request that returns stop_reason:"refusal"
    with no generated output is documented as not billed. Previously this
    function always priced input_tokens + output_tokens regardless of
    stop_reason, which overstated cost for refusals — Anthropic doesn't
    charge for them, so this log shouldn't either. Pass stop_reason through
    from the caller (see zc_fable5.py's call_with_fallback(), which now
    surfaces not_billed for exactly this case) to get an accurate $0 entry
    instead of a phantom charge."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    not_billed = stop_reason == "refusal" and output_tokens == 0
    entry = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": 0.0 if not_billed else round(_price(model, input_tokens, output_tokens), 6),
        "latency_seconds": round(latency_seconds, 3),
        "command": command,
        "stop_reason": stop_reason,
        "not_billed": not_billed,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def load_log(today_only: bool = False, model_filter: Optional[str] = None) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    today_str = date.today().isoformat()
    entries = []
    with open(LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if today_only and not e.get("ts", "").startswith(today_str):
                continue
            if model_filter and e.get("model") != model_filter:
                continue
            entries.append(e)
    return entries


def summarise(entries: list[dict]) -> dict:
    if not entries:
        return {"calls": 0}
    by_model: dict[str, dict] = {}
    for e in entries:
        m = e.get("model", "unknown")
        if m not in by_model:
            by_model[m] = {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                           "cost_usd": 0.0, "latency_seconds": 0.0}
        s = by_model[m]
        s["calls"] += 1
        s["input_tokens"] += e.get("input_tokens", 0)
        s["output_tokens"] += e.get("output_tokens", 0)
        s["cost_usd"] += e.get("cost_usd", 0.0)
        s["latency_seconds"] += e.get("latency_seconds", 0.0)
    for m in by_model:
        s = by_model[m]
        s["avg_latency_seconds"] = round(s["latency_seconds"] / s["calls"], 3)
        s["cost_usd"] = round(s["cost_usd"], 6)

    return {
        "calls": len(entries),
        "total_cost_usd": round(sum(e.get("cost_usd", 0) for e in entries), 6),
        "total_input_tokens": sum(e.get("input_tokens", 0) for e in entries),
        "total_output_tokens": sum(e.get("output_tokens", 0) for e in entries),
        "by_model": by_model,
    }


def cmd_metrics_show(today_only: bool = False, model_filter: Optional[str] = None):
    entries = load_log(today_only=today_only, model_filter=model_filter)
    s = summarise(entries)
    if not s.get("calls"):
        print("No metrics recorded yet. API calls are logged automatically after each use.")
        return
    label = "Today's" if today_only else "All-time"
    if model_filter:
        label += f" [{model_filter}]"
    print(f"\n\033[94m{label} Usage\033[0m")
    print(f"  Total calls:    {s['calls']}")
    print(f"  Total cost:     ${s['total_cost_usd']:.4f}")
    print(f"  Input tokens:   {s['total_input_tokens']:,}")
    print(f"  Output tokens:  {s['total_output_tokens']:,}")
    if s.get("by_model"):
        print("\n  \033[1mBy model:\033[0m")
        for model, ms in sorted(s["by_model"].items()):
            print(f"    {model:<40} {ms['calls']} calls  "
                  f"${ms['cost_usd']:.4f}  avg {ms['avg_latency_seconds']}s")
    print()


def cmd_metrics_clear():
    if LOG_PATH.exists():
        LOG_PATH.unlink()
    print("Metrics log cleared.")


def cmd_metrics_export(output_path: str, today_only: bool = False):
    entries = load_log(today_only=today_only)
    with open(output_path, "w") as f:
        json.dump({"entries": entries, "summary": summarise(entries)}, f, indent=2)
    print(f"Exported {len(entries)} entries to {output_path}")