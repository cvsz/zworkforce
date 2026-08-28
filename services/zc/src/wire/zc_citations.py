"""
zc_citations.py — Citations & RAG
AI Model Coder CLI v1.8.0

Ground zAICoder's answers in source documents with inline citations.
Uses search result content blocks + citations API (GA).

CLI flags:
  --cite DOCS              Answer with citations from document files
  --cite-dir DIR           Cite from all .txt/.md files in a directory
  --cite-web QUERY         Search web and cite sources
  --rag QUERY              RAG mode: answer from your local docs
"""

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from wire.exceptions import AICoderError
from wire.resilience import CircuitBreaker, retry, urlopen_json

ENDPOINT = "https://api.anthropic.com/v1/messages"

# Shared per-process so repeated failures across CitationsCoder instances
# trip the breaker once, same rationale as coder.py's _default_breaker.
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)


class CitationsCoder:
    """zAICoder client with source-grounded citations."""

    def __init__(self, api_key: str, model: str = "zc-xxx",
                 max_tokens: int = 4096):
        self.api_key    = api_key
        self.model      = model
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict, beta: str = "") -> dict:
        headers = {
            "Content-Type":      "application/json",
            "x-api-key":         self.api_key,
            "anthropic-version": "2023-06-01",
        }
        if beta:
            headers["anthropic-beta"] = beta
        req = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        return urlopen_json(req, timeout=120)

    def _post(self, payload: dict, beta: str = "") -> dict:
        # Preserves the pre-existing {"error": ..., "status": ...} contract
        # that cite_documents()/cite_web() below already check for, while
        # retrying transient/rate-limit failures underneath via _call().
        try:
            return self._call(payload, beta)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}

    # ── Document citations ────────────────────────────────────────────────

    def cite_documents(
        self,
        question: str,
        documents: list[dict],   # [{"title": str, "content": str}, ...]
        system: Optional[str] = None,
    ) -> dict:
        """
        Answer a question with inline citations from the provided documents.
        documents: list of {"title": str, "content": str}
        """
        content = []
        for doc in documents:
            content.append({
                "type":   "document",
                "source": {"type": "text", "media_type": "text/plain",
                           "data": doc["content"]},
                "title":     doc.get("title", "Document"),
                "citations": {"enabled": True},
            })
        content.append({"type": "text", "text": question})

        payload = {
            "model":      self.model,
            "max_tokens": self.max_tokens,
            "messages":   [{"role": "user", "content": content}],
        }
        if system:
            payload["system"] = system

        data = self._post(payload)
        if "error" in data:
            return {"answer": f"[ERROR] {data['error']}", "citations": []}

        answer    = ""
        citations = []
        for block in data.get("content", []):
            bt = block.get("type", "")
            if bt == "text":
                answer += block.get("text", "")
            elif bt == "citations":
                for c in block.get("citations", []):
                    citations.append({
                        "text":       c.get("cited_text", ""),
                        "document":   c.get("document_title", ""),
                        "start_char": c.get("start_char_index"),
                        "end_char":   c.get("end_char_index"),
                    })

        return {"answer": answer, "citations": citations,
                "usage": data.get("usage", {})}

    # ── Search-result citations (RAG) ─────────────────────────────────────

    def cite_search_results(
        self,
        question: str,
        results: list[dict],   # [{"title": str, "url": str, "content": str}]
    ) -> dict:
        """
        Use search_result content blocks for proper source attribution.
        beta: search-results-2025-06-09
        """
        content = []
        for r in results:
            content.append({
                "type":    "search_result",
                "title":   r.get("title", ""),
                "url":     r.get("url", ""),
                "content": [{"type": "text", "text": r["content"]}],
            })
        content.append({"type": "text", "text": question})

        payload = {
            "model":      self.model,
            "max_tokens": self.max_tokens,
            "messages":   [{"role": "user", "content": content}],
        }
        data = self._post(payload, beta="search-results-2025-06-09")
        if "error" in data:
            return {"answer": f"[ERROR] {data['error']}", "citations": []}

        answer    = ""
        citations: list[dict] = []
        for block in data.get("content", []):
            bt = block.get("type", "")
            if bt == "text":
                answer += block.get("text", "")

        return {"answer": answer, "citations": citations,
                "usage": data.get("usage", {})}

    # ── File-based RAG ────────────────────────────────────────────────────

    def rag_from_directory(self, question: str, directory: str,
                            glob_pattern: str = "*.md") -> dict:
        """Load local docs from a directory and answer with citations."""
        docs = []
        for p in sorted(Path(directory).glob(glob_pattern)):
            try:
                docs.append({"title": p.name, "content": p.read_text()[:8000]})
            except Exception:
                pass
        if not docs:
            return {"answer": f"No documents found in {directory}", "citations": []}
        return self.cite_documents(question, docs)


# ── CLI entry points ───────────────────────────────────────────────────────

def cmd_cite(question: str, doc_files: list[str], api_key: str, model: str):
    docs = []
    for f in doc_files:
        p = Path(f)
        if p.exists():
            docs.append({"title": p.name, "content": p.read_text()[:8000]})
        else:
            print(f"  [WARN] Not found: {f}")

    if not docs:
        print("[ERROR] No valid documents found.")
        return

    print(f"\033[94mℹ Answering with citations from {len(docs)} document(s)\033[0m\n")
    cc     = CitationsCoder(api_key=api_key, model=model)
    result = cc.cite_documents(question, docs)

    print(result["answer"])
    if result["citations"]:
        print("\n\033[90m── Citations ────────────────────────────\033[0m")
        for i, c in enumerate(result["citations"], 1):
            print(f"\033[90m[{i}] {c['document']}: \"{c['text'][:80]}…\"\033[0m")
    return result


def cmd_rag(question: str, directory: str, api_key: str, model: str,
            pattern: str = "*.md"):
    print(f"\033[94mℹ RAG from {directory} ({pattern})\033[0m\n")
    cc     = CitationsCoder(api_key=api_key, model=model)
    result = cc.rag_from_directory(question, directory, pattern)
    print(result["answer"])
    if result["citations"]:
        print("\n\033[90m── Citations ────────────────────────────\033[0m")
        for i, c in enumerate(result["citations"], 1):
            print(f"\033[90m[{i}] {c['document']}\033[0m")
    return result
