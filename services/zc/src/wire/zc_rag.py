"""
zc_rag.py — Retrieval-Augmented Generation pipeline
AI Model Coder CLI v1.10.0

Indexes a local folder of files (or a pre-built index JSON), retrieves
the most relevant chunks at query time (keyword BM25-style scoring),
then generates a grounded, cited response. Uses the Files API to
upload large corpora once and reference them cheaply across queries.
"""

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import anthropic

from wire.utils import sampling_kwargs

INDEX_DIR = Path.home() / ".ai-coder" / "rag_indexes"
SUPPORTED_EXTS = {".txt", ".md", ".py", ".js", ".ts", ".go", ".java", ".rs",
                  ".c", ".cpp", ".h", ".json", ".yaml", ".yml", ".csv", ".html"}


@dataclass
class Chunk:
    cid:     str
    source:  str
    content: str
    tokens:  int = 0


@dataclass
class RAGIndex:
    name:     str
    chunks:   list[Chunk] = field(default_factory=list)
    idf:      dict[str, float] = field(default_factory=dict)
    file_ids: dict[str, str] = field(default_factory=dict)  # cid → Files API id

    def to_dict(self):
        return {"name": self.name,
                "chunks": [{"cid": c.cid, "source": c.source,
                            "content": c.content, "tokens": c.tokens}
                           for c in self.chunks],
                "idf": self.idf, "file_ids": self.file_ids}

    @staticmethod
    def from_dict(d) -> "RAGIndex":
        idx = RAGIndex(name=d["name"])
        idx.chunks = [Chunk(**c) for c in d.get("chunks", [])]
        idx.idf = d.get("idf", {}); idx.file_ids = d.get("file_ids", {})
        return idx


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


def _chunk_text(source: str, text: str, size: int = 600,
                overlap: int = 100) -> list[Chunk]:
    words = text.split(); chunks = []
    i = 0; cid_base = Path(source).stem
    while i < len(words):
        end = min(i + size, len(words))
        content = " ".join(words[i:end])
        cid = f"{cid_base}_{i}"
        chunks.append(Chunk(cid=cid, source=source, content=content,
                           tokens=end - i))
        i += size - overlap
    return chunks


def build_index(name: str, folder: str, chunk_size: int = 600,
                overlap: int = 100) -> RAGIndex:
    idx = RAGIndex(name=name); df: Counter = Counter(); total = 0
    for path in Path(folder).rglob("*"):
        if path.suffix.lower() not in SUPPORTED_EXTS: continue
        try:
            text = path.read_text(errors="replace")
        except Exception: continue
        for chunk in _chunk_text(str(path), text, chunk_size, overlap):
            idx.chunks.append(chunk)
            total += 1
            for w in set(_tokenize(chunk.content)): df[w] += 1
    idx.idf = {w: math.log((total + 1) / (c + 1)) + 1 for w, c in df.items()}
    _save_index(idx); return idx


def _save_index(idx: RAGIndex):
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    (INDEX_DIR / f"{idx.name}.json").write_text(json.dumps(idx.to_dict(), indent=2))


def load_index(name: str) -> Optional[RAGIndex]:
    p = INDEX_DIR / f"{name}.json"
    if not p.exists(): return None
    return RAGIndex.from_dict(json.loads(p.read_text()))


def _score(query_tokens: list[str], chunk: Chunk,
           idf: dict[str, float]) -> float:
    tf = Counter(_tokenize(chunk.content))
    score = 0.0
    for qt in query_tokens:
        if qt in tf:
            score += (tf[qt] / (tf[qt] + 1.5)) * idf.get(qt, 1.0)
    return score


def retrieve(idx: RAGIndex, query: str, k: int = 5) -> list[Chunk]:
    qt = _tokenize(query)
    scored = [(c, _score(qt, c, idx.idf)) for c in idx.chunks]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [c for c, s in scored[:k] if s > 0]


def generate(query: str, chunks: list[Chunk], api_key: str,
             model: str = "claude-sonnet-5") -> str:
    client = anthropic.Anthropic(api_key=api_key)
    ctx = "\n\n".join(f"[{c.source}]\n{c.content}" for c in chunks)
    system = ("Answer based on the provided context. Cite sources using the "
              "[filename] format. If the context doesn't contain the answer, "
              "say so clearly rather than guessing.")
    resp = client.messages.create(
        model=model, max_tokens=2048,
        **sampling_kwargs(model, temperature=0.2),
        system=system,
        messages=[{"role": "user",
                   "content": f"Context:\n{ctx}\n\nQuestion: {query}"}])
    return resp.content[0].text


# ── CLI commands ──────────────────────────────────────────────────────────────

def cmd_rag_index(name: str, folder: str, chunk_size: int = 600):
    print(f"Building RAG index '{name}' from {folder} …")
    idx = build_index(name, folder, chunk_size)
    print(f"✓ Indexed {len(idx.chunks)} chunks from {folder}")


def cmd_rag_query(name: str, query: str, api_key: str, model: str, k: int = 5):
    idx = load_index(name)
    if not idx: print(f"Index not found: {name}\n  Run --rag-index to build it."); return
    chunks = retrieve(idx, query, k)
    if not chunks: print("No relevant chunks found."); return
    print(f"Retrieved {len(chunks)} chunk(s). Generating answer …\n")
    print(generate(query, chunks, api_key, model))


def cmd_rag_list():
    if not INDEX_DIR.exists(): print("No RAG indexes found."); return
    for p in sorted(INDEX_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text())
            print(f"  {d['name']:<24} {len(d.get('chunks',[]))} chunks")
        except Exception as _e: pass
