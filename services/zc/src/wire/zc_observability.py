"""
zc_observability.py — Observability: structured request/response
logging, latency histograms, and AI-powered error trend analysis.
AI Model Coder CLI v1.10.0
"""

import json
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional

import anthropic

OBS_DIR  = Path.home() / ".ai-coder" / "observability"
LOG_FILE = OBS_DIR / "requests.jsonl"


# ── Structured logging ────────────────────────────────────────────────────────

def _log(record: dict[str, Any]):
    OBS_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def _read_logs(hours: int = 24) -> list[dict]:
    if not LOG_FILE.exists(): return []
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    records = []
    with open(LOG_FILE) as f:
        for line in f:
            try:
                r = json.loads(line)
                if r.get("ts", "") >= cutoff: records.append(r)
            except Exception as _e: pass
    return records


def record_request(model: str, prompt: str, response: str,
                   latency_ms: int, in_tokens: int, out_tokens: int,
                   error: Optional[str] = None, tags: Optional[list[str]] = None):
    _log({"req_id": str(uuid.uuid4())[:8], "ts": datetime.now().isoformat(),
          "model": model, "prompt_preview": prompt[:120],
          "response_preview": response[:120] if response else "",
          "latency_ms": latency_ms, "in_tokens": in_tokens,
          "out_tokens": out_tokens, "error": error, "tags": tags or []})


# ── Decorator for auto-instrumentation ───────────────────────────────────────

def observe(model: str = "unknown", tags: Optional[list[str]] = None):
    """Decorator: wrap any function that (a) takes prompt as first arg and
    (b) returns a string response, logging latency + token estimate."""
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            prompt = args[0] if args else kwargs.get("prompt", "")
            t0 = time.time()
            error = None
            result = ""
            try:
                result = fn(*args, **kwargs)
                return result
            except Exception as e:
                error = str(e); raise
            finally:
                ms = int((time.time() - t0) * 1000)
                est_in  = max(1, len(str(prompt)) // 4)
                est_out = max(1, len(str(result)) // 4)
                record_request(model, str(prompt), str(result), ms,
                               est_in, est_out, error=error, tags=tags)
        return wrapper
    return decorator


# ── Analytics ─────────────────────────────────────────────────────────────────

def _histogram(values: list[float], buckets: int = 6) -> str:
    if not values: return "(no data)"
    lo, hi = min(values), max(values)
    if hi == lo: return f"all values = {lo:.0f}"
    width = (hi - lo) / buckets
    counts = [0] * buckets
    for v in values:
        idx = min(int((v - lo) / width), buckets - 1)
        counts[idx] += 1
    lines = []
    for i, c in enumerate(counts):
        label = f"{lo + i*width:.0f}–{lo + (i+1)*width:.0f}"
        bar   = "█" * max(1, int(c / max(counts) * 20)) if c else ""
        lines.append(f"  {label:>12}ms  {bar} {c}")
    return "\n".join(lines)


def latency_report(hours: int = 24):
    records = _read_logs(hours)
    if not records: print(f"No requests in the last {hours}h."); return
    lats = [r["latency_ms"] for r in records if "latency_ms" in r]
    by_model: dict[str, list[float]] = defaultdict(list)
    for r in records: by_model[r.get("model","?")].append(r.get("latency_ms",0))
    errors = [r for r in records if r.get("error")]

    print(f"Requests (last {hours}h): {len(records)}  errors: {len(errors)}")
    print(f"Latency — p50={sorted(lats)[len(lats)//2]:.0f}ms  "
          f"p95={sorted(lats)[int(len(lats)*0.95)]:.0f}ms  "
          f"avg={sum(lats)/len(lats):.0f}ms\n")
    print("Latency histogram (ms):")
    print(_histogram(lats))
    print("\nBy model:")
    for m, ls in sorted(by_model.items()):
        avg = sum(ls)/len(ls)
        print(f"  {m:<40} {len(ls):>4} calls  avg={avg:.0f}ms")


def error_analysis(api_key: str, model: str, hours: int = 24):
    records = _read_logs(hours)
    errors  = [r for r in records if r.get("error")]
    if not errors: print("No errors in logs."); return
    summary = "\n".join(f"- {e['ts'][:16]} [{e['model']}] {e['error']}" for e in errors[-20:])
    client  = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model, max_tokens=512, temperature=0,
        system="You are an SRE. Analyse these API error logs and identify patterns + fixes.",
        messages=[{"role": "user", "content": summary}])
    print(resp.content[0].text)  # type: ignore


# ── CLI commands ──────────────────────────────────────────────────────────────

def cmd_obs_latency(hours: int = 24):   latency_report(hours)
def cmd_obs_errors(api_key: str, model: str, hours: int = 24):
    error_analysis(api_key, model, hours)
def cmd_obs_clear():
    if LOG_FILE.exists(): LOG_FILE.unlink(); print("✓ Observability log cleared.")
    else: print("No log to clear.")
def cmd_obs_tail(n: int = 20):
    recs = _read_logs(hours=999999)[-n:]
    if not recs: print("No records."); return
    for r in recs:
        err = f" ERROR: {r['error']}" if r.get("error") else ""
        print(f"{r['ts'][:19]}  {r['model']:<35}  {r.get('latency_ms',0):>5}ms{err}")