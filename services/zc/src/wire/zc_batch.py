from typing import Any
"""
zc_batch.py — Messages Batch API
AI Model Coder CLI v1.11.1

Process large numbers of requests asynchronously at 50% cost discount.
Ideal for bulk code review, batch documentation, mass refactoring.

New in v1.11.1: 300k output tokens on the Message Batches API (beta
output-300k-2026-03-24), for Opus 4.8/4.7/4.6 and Sonnet 5/4.6 — previously
unavailable in this module, every batch request was capped at each model's
normal synchronous max_output regardless of batch mode's higher ceiling.

CLI flags:
  --batch-file FILE        JSONL file of prompts to process
  --batch-submit           Submit batch and return batch_id
  --batch-status ID        Check status of a batch
  --batch-results ID       Download + display results
  --batch-cancel ID        Cancel a pending batch
  --batch-list             List recent batches
  --batch-generate N       Generate code for N tasks from a prompt template
  --batch-300k-output      Opt into 300k max output tokens per request
                           (beta, eligible models only — see
                           OUTPUT_300K_MODELS)
"""

import json
import os
import time
import uuid
from pathlib import Path

import anthropic
from typing import Optional

BATCH_STORE = Path(os.path.expanduser("~/.ai-coder/batches"))

# 300k output tokens on the Message Batches API. Per platform.zc.com/docs
# (checked 2026-07-02): "On the Message Batches API, zAICoder Opus 4.8, Opus
# 4.7, Opus 4.6, Sonnet 5, and Sonnet 4.6 support up to 300k output tokens by
# using the output-300k-2026-03-24 beta header." Batch-only — the
# synchronous Messages API max_output values are unaffected.
OUTPUT_300K_BETA = "output-300k-2026-03-24"
OUTPUT_300K_MODELS = {
    "zc-opus-4-8", "zc-opus-4-7", "zc-opus-4-6",
    "zc-xxx", "zc-sonnet-4-6",
}
OUTPUT_300K_MAX_TOKENS = 300_000


class BatchCoder:
    """zAICoder Batch API client."""

    def __init__(self, api_key: str, model: str = "zc-xxx",
                 use_300k_output: bool = False):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model  = model
        # Opt-in per-instance rather than per-request: the beta header is
        # sent on the whole batches.create() call, so mixing 300k-output and
        # normal requests in one batch isn't meaningful — pick one per batch.
        self.use_300k_output = use_300k_output
        if use_300k_output and model not in OUTPUT_300K_MODELS:
            print(f"\033[93m⚠ {model} isn't in OUTPUT_300K_MODELS — "
                  f"output-300k-2026-03-24 may not apply; proceeding anyway "
                  f"since the API is the source of truth.\033[0m")
        BATCH_STORE.mkdir(parents=True, exist_ok=True)

    def _create_batch(self, requests: list):
        """Submit requests as a batch, adding the 300k-output beta header
        when opted in via use_300k_output."""
        if self.use_300k_output:
            return self.client.beta.messages.batches.create(
                requests=requests, betas=[OUTPUT_300K_BETA])
        return self.client.messages.batches.create(requests=requests)

    # ── Submit ────────────────────────────────────────────────────────────

    def submit_from_jsonl(self, jsonl_path: str, system: Optional[str] = None) -> str:
        """Read a JSONL file and submit as a batch. Returns batch_id."""
        requests = []
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj   = json.loads(line)
                rid   = obj.get("id") or str(uuid.uuid4())[:8]
                prompt = obj.get("prompt") or obj.get("content") or str(obj)
                msgs  = obj.get("messages") or [{"role": "user", "content": prompt}]
                req: dict[str, Any] = {
                    "custom_id": rid,
                    "params": {
                        "model":      self.model,
                        "max_tokens": obj.get("max_tokens", 4096),
                        "messages":   msgs,
                    }
                }
                if system or obj.get("system"):
                    req["params"]["system"] = system or obj["system"]
                requests.append(req)

        batch = self._create_batch(requests)
        self._save_batch_meta(batch.id, {
            "id":          batch.id,
            "source":      jsonl_path,
            "model":       self.model,
            "count":       len(requests),
            "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        return batch.id

    def submit_prompts(self, prompts: list[str], system: Optional[str] = None,
                       max_tokens: int = 4096) -> str:
        """Submit a list of prompt strings as a batch."""
        requests = []
        for i, prompt in enumerate(prompts):
            req: dict[str, Any] = {
                "custom_id": f"req-{i:04d}",
                "params": {
                    "model":      self.model,
                    "max_tokens": max_tokens,
                    "messages":   [{"role": "user", "content": prompt}],
                }
            }
            if system:
                req["params"]["system"] = system
            requests.append(req)

        batch = self._create_batch(requests)
        self._save_batch_meta(batch.id, {
            "id":          batch.id,
            "source":      "inline",
            "model":       self.model,
            "count":       len(prompts),
            "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        return batch.id

    # ── Status ────────────────────────────────────────────────────────────

    def status(self, batch_id: str) -> dict:
        batch = self.client.messages.batches.retrieve(batch_id)
        return {
            "id":           batch.id,
            "status":       batch.processing_status,
            "request_counts": batch.request_counts.model_dump()
                              if hasattr(batch.request_counts, "model_dump")
                              else vars(batch.request_counts),
            "created_at":   str(batch.created_at),
            "expires_at":   str(batch.expires_at),
        }

    # ── Results ───────────────────────────────────────────────────────────

    def results(self, batch_id: str, save_to: Optional[str] = None) -> list:
        """Stream results once batch is complete. Returns list of result dicts."""
        items = []
        for result in self.client.messages.batches.results(batch_id):
            entry = {
                "custom_id": result.custom_id,
                "type":      result.result.type,
            }
            if result.result.type == "succeeded":
                msg    = result.result.message
                entry["text"] = msg.content[0].text if msg.content else ""
                entry["usage"] = {
                    "input":  msg.usage.input_tokens,
                    "output": msg.usage.output_tokens,
                }
            else:
                entry["error"] = str(result.result.error)
            items.append(entry)

        if save_to:
            Path(save_to).write_text(
                "\n".join(json.dumps(item) for item in items)
            )
        return items

    # ── Cancel / List ─────────────────────────────────────────────────────

    def cancel(self, batch_id: str) -> bool:
        self.client.messages.batches.cancel(batch_id)
        return True

    def list_batches(self, limit: int = 20) -> list:
        batches = self.client.messages.batches.list(limit=limit)
        return [
            {
                "id":     b.id,
                "status": b.processing_status,
                "counts": b.request_counts.model_dump()
                          if hasattr(b.request_counts, "model_dump")
                          else vars(b.request_counts),
                "created": str(b.created_at)[:19],
            }
            for b in batches.data
        ]

    # ── Wait for completion ───────────────────────────────────────────────

    def wait(self, batch_id: str, poll_interval: int = 15,
             max_wait: int = 3600) -> dict:
        """Poll until batch is done or max_wait seconds elapsed."""
        waited = 0
        while waited < max_wait:
            s = self.status(batch_id)
            st = s.get("status", "")
            print(f"\r\033[94mℹ [{batch_id}] {st}  "
                  f"counts={s.get('request_counts',{})}  "
                  f"(waited {waited}s)\033[0m", end="", flush=True)
            if st in ("ended",):
                print()
                return s
            time.sleep(poll_interval)
            waited += poll_interval
        print()
        return self.status(batch_id)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _save_batch_meta(self, batch_id: str, meta: dict):
        (BATCH_STORE / f"{batch_id}.json").write_text(json.dumps(meta, indent=2))


# ── CLI helpers ────────────────────────────────────────────────────────────

def cmd_batch_submit(jsonl_path: str, api_key: str, model: str, system: Optional[str] = None,
                     use_300k_output: bool = False):
    bc = BatchCoder(api_key=api_key, model=model, use_300k_output=use_300k_output)
    print(f"\033[94mℹ Submitting batch from {jsonl_path}…\033[0m")
    bid = bc.submit_from_jsonl(jsonl_path, system=system)
    print(f"\033[92m✓ Batch submitted: {bid}\033[0m")
    print(f"  Check status:   ai-coder --batch-status {bid}")
    print(f"  Get results:    ai-coder --batch-results {bid}")
    return bid


def cmd_batch_status(batch_id: str, api_key: str):
    bc = BatchCoder(api_key=api_key)
    s  = bc.status(batch_id)
    print(f"\n  ID:      {s['id']}")
    print(f"  Status:  {s['status']}")
    print(f"  Counts:  {s['request_counts']}")
    print(f"  Created: {s['created_at'][:19]}")
    print(f"  Expires: {s['expires_at'][:19]}")


def cmd_batch_results(batch_id: str, api_key: str, save_to: Optional[str] = None):
    bc    = BatchCoder(api_key=api_key)
    items = bc.results(batch_id, save_to=save_to)
    ok    = sum(1 for i in items if i.get("type") == "succeeded")
    print(f"\n\033[92m✓ {ok}/{len(items)} succeeded\033[0m\n")
    for item in items:
        status = "✓" if item.get("type") == "succeeded" else "✗"
        print(f"[{status}] {item['custom_id']}")
        if item.get("text"):
            preview = item["text"][:200].replace("\n", " ")
            print(f"    {preview}…" if len(item["text"]) > 200 else f"    {preview}")
        elif item.get("error"):
            print(f"    ERROR: {item['error']}")
    if save_to:
        print(f"\n\033[92m✓ Saved to {save_to}\033[0m")


def cmd_batch_list(api_key: str):
    bc      = BatchCoder(api_key=api_key)
    batches = bc.list_batches()
    if not batches:
        print("No batches found."); return
    print(f"\n{'ID':<30}{'STATUS':<15}{'COUNTS':<25}{'CREATED'}")
    print("─" * 85)
    for b in batches:
        counts = str(b["counts"])
        print(f"{b['id']:<30}{b['status']:<15}{counts[:24]:<25}{b['created']}")


def cmd_batch_cancel(batch_id: str, api_key: str):
    bc = BatchCoder(api_key=api_key)
    bc.cancel(batch_id)
    print(f"\033[92m✓ Batch {batch_id} cancelled.\033[0m")


def cmd_batch_generate(prompt_template: str, n: int, api_key: str, model: str,
                       system: Optional[str] = None, wait: bool = False):
    """Generate N variants of a prompt and batch-submit them."""
    prompts = [f"{prompt_template} (variant {i+1} of {n})" for i in range(n)]
    bc  = BatchCoder(api_key=api_key, model=model)
    bid = bc.submit_prompts(prompts, system=system)
    print(f"\033[92m✓ Batch of {n} submitted: {bid}\033[0m")
    if wait:
        bc.wait(bid)
        items = bc.results(bid)
        for item in items:
            print(f"\n── {item['custom_id']} ──")
            print(item.get("text", item.get("error", "")))