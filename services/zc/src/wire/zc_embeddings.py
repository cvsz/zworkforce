from typing import Any
"""
zc_embeddings.py — Text embeddings
AI Model Coder CLI v1.11.0

This was a complete gap before this pass: no module at all, even though
zc_memory.py's docstring says "swap in embeddings for larger stores"
and never does.

IMPORTANT — this is NOT a zAICoder API endpoint. Per
platform.zc.com/docs/en/build-with-zc/embeddings (checked
2026-07-02): "Anthropic does not offer its own embedding model." Anthropic's
docs recommend Voyage AI (an Anthropic partner) and document the Voyage
Python client and raw HTTP API as the way to get embeddings for use
alongside zAICoder. This module is a thin, dependency-free wrapper around
Voyage's HTTP endpoint (https://api.voyageai.com/v1/embeddings), not a
wrapper around anything Anthropic hosts. It needs its own API key
(VOYAGE_API_KEY), separate from ANTHROPIC_API_KEY.

If you'd rather use a different embeddings provider (OpenAI, a local
sentence-transformers model, etc.), this module isn't required — swap the
provider in zc_rag.py / zc_memory.py's retrieval scoring directly.
It exists so "embeddings" isn't a silent gap, and so RAG/memory retrieval
in this project has a documented upgrade path from keyword/BM25 scoring
to real semantic search.

CLI flags:
  --embed TEXT              Embed a single string, print the vector length
                             and first few values
  --embed-file FILE         Embed each line of FILE, print one vector per line
  --embed-similarity A B    Cosine similarity between two strings' embeddings
  --embed-model MODEL       Voyage model (default: voyage-3.5)
  --embed-input-type TYPE   "query" or "document" (default: document) —
                             Voyage recommends setting this for retrieval,
                             it measurably improves ranking quality
"""

import json
import math
import os
import urllib.error
import urllib.request
from typing import Optional

from wire.exceptions import AICoderError
from wire.resilience import CircuitBreaker, retry, urlopen_json

VOYAGE_ENDPOINT = "https://api.voyageai.com/v1/embeddings"
# Separate breaker from the Anthropic-API modules: Voyage is a distinct
# downstream dependency and an outage there shouldn't look like an
# Anthropic API outage (or vice versa).
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)

# voyage-3.5 is Voyage's current balanced general-purpose model per their
# docs as of this check; voyage-code-3 is the recommended pick specifically
# for code-retrieval workloads (this being a coder CLI, worth calling out).
DEFAULT_MODEL = "voyage-3.5"
CODE_MODEL    = "voyage-code-3"


def _voyage_key(explicit: Optional[str] = None) -> str:
    key = explicit or os.getenv("VOYAGE_API_KEY", "")
    if not key:
        raise RuntimeError(
            "VOYAGE_API_KEY not set. Embeddings use Voyage AI, not the "
            "Anthropic API — Anthropic doesn't host its own embedding "
            "model. Get a key at https://dashboard.voyageai.com and set "
            "VOYAGE_API_KEY (separate from ANTHROPIC_API_KEY)."
        )
    return key


def embed(texts: list[str], model: str = DEFAULT_MODEL,
          input_type: Optional[str] = "document",
          api_key: Optional[str] = None) -> list[list[float]]:
    """Embed a list of strings, return one vector per input. input_type
    should be "document" when embedding things you'll search over, and
    "query" when embedding the search query itself — Voyage optimizes the
    two differently and recommends always setting one or the other for
    retrieval use cases rather than leaving it unset."""
    key = _voyage_key(api_key)
    payload = {"input": texts, "model": model}
    if input_type:
        payload["input_type"] = input_type
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {key}",
    }
    req = urllib.request.Request(
        VOYAGE_ENDPOINT, data=json.dumps(payload).encode(),
        headers=headers, method="POST",
    )
    try:
        data = _call(req)
    except AICoderError as e:
        raise RuntimeError(f"Voyage API error: {e.message}") from e
    return [item["embedding"] for item in data.get("data", [])]


@retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
def _call(req: "urllib.request.Request") -> dict:
    return urlopen_json(req, timeout=60)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Voyage embeddings are normalized to length 1, so dot product equals
    cosine similarity and is cheaper — but this stays a true cosine
    similarity so it's correct even against non-Voyage vectors."""
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class EmbeddingIndex:
    """Minimal in-memory semantic index: embed a corpus once, then rank
    queries against it by cosine similarity. Meant as the "swap in
    embeddings" upgrade zc_memory.py's docstring gestures at — pass its
    .search() results into memory/RAG retrieval instead of (or blended
    with) keyword scoring."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: Optional[str] = None):
        self.model   = model
        self.api_key = api_key
        self._ids:   list[str]         = []
        self._texts: list[str]         = []
        self._vecs:  list[list[float]] = []

    def add(self, ids: list[str], texts: list[str], batch_size: int = 128):
        for i in range(0, len(texts), batch_size):
            batch_ids   = ids[i:i + batch_size]
            batch_texts = texts[i:i + batch_size]
            vecs = embed(batch_texts, model=self.model, input_type="document",
                        api_key=self.api_key)
            self._ids.extend(batch_ids)
            self._texts.extend(batch_texts)
            self._vecs.extend(vecs)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self._vecs:
            return []
        [qvec] = embed([query], model=self.model, input_type="query", api_key=self.api_key)
        scored: list[dict[str, Any]] = [
            {"id": i, "text": t, "score": cosine_similarity(qvec, v)}
            for i, t, v in zip(self._ids, self._texts, self._vecs)
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


# ── CLI entry points ─────────────────────────────────────────────────────────

def cmd_embed(text: str, model: str = DEFAULT_MODEL, input_type: str = "document"):
    print(f"\033[94mℹ Embedding via Voyage AI ({model})\033[0m\n")
    try:
        [vec] = embed([text], model=model, input_type=input_type)
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        return
    print(f"  dimensions: {len(vec)}")
    print(f"  first 8:    {[round(v, 5) for v in vec[:8]]}")
    return vec


def cmd_embed_file(path: str, model: str = DEFAULT_MODEL, input_type: str = "document"):
    with open(path) as f:
        lines = [l.strip() for l in f if l.strip()]
    print(f"\033[94mℹ Embedding {len(lines)} lines from {path} via Voyage AI ({model})\033[0m\n")
    try:
        vecs = embed(lines, model=model, input_type=input_type)
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        return
    for line, vec in zip(lines, vecs):
        print(f"  [{len(vec)}d] {line[:60]}{'...' if len(line) > 60 else ''}")
    return vecs


def cmd_embed_similarity(text_a: str, text_b: str, model: str = DEFAULT_MODEL):
    print(f"\033[94mℹ Cosine similarity via Voyage AI ({model})\033[0m\n")
    try:
        vec_a, vec_b = embed([text_a, text_b], model=model, input_type="document")
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        return
    sim = cosine_similarity(vec_a, vec_b)
    print(f"  \"{text_a[:50]}\"")
    print(f"  \"{text_b[:50]}\"")
    print(f"  similarity: {sim:.4f}")
    return sim