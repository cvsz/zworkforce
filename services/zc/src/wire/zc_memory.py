"""
zc_memory.py — Persistent cross-session memory
AI Model Coder CLI v1.10.0

Stores facts, preferences, events and tasks in ~/.ai-coder/memory/.
Recall uses keyword + importance scoring; swap in embeddings for
larger stores. Memory is namespaced so multi-user gateway setups
stay isolated.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

MEMORY_DIR = Path.home() / ".ai-coder" / "memory"


class MemType(Enum):
    FACT       = "fact"
    PREFERENCE = "preference"
    EVENT      = "event"
    TASK       = "task"


@dataclass
class MemEntry:
    mid:        str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    content:    str = ""
    mtype:      MemType = MemType.FACT
    tags:       list[str] = field(default_factory=list)
    importance: int = 5      # 1–10; 10 = never auto-deleted
    created:    str = field(default_factory=lambda: datetime.now().isoformat())
    accessed:   Optional[str] = None

    def to_dict(self):
        return {"mid": self.mid, "content": self.content, "mtype": self.mtype.value,
                "tags": self.tags, "importance": self.importance,
                "created": self.created, "accessed": self.accessed}

    @staticmethod
    def from_dict(d) -> "MemEntry":
        e = MemEntry()
        e.mid = d["mid"]; e.content = d["content"]
        e.mtype = MemType(d.get("mtype","fact"))
        e.tags = d.get("tags", []); e.importance = d.get("importance", 5)
        e.created = d.get("created", datetime.now().isoformat())
        e.accessed = d.get("accessed")
        return e


class MemoryStore:
    def __init__(self, ns: str = "default"):
        self.ns = ns
        self.entries: list[MemEntry] = []
        self._load()

    def _path(self) -> Path:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        return MEMORY_DIR / f"{self.ns}.json"

    def _load(self):
        p = self._path()
        if p.exists():
            self.entries = [MemEntry.from_dict(d) for d in json.loads(p.read_text())]

    def save(self):
        self._path().write_text(json.dumps([e.to_dict() for e in self.entries], indent=2))

    def add(self, content: str, mtype: MemType = MemType.FACT,
            tags: Optional[list[str]] = None, importance: int = 5) -> MemEntry:
        e = MemEntry(content=content, mtype=mtype, tags=tags or [], importance=importance)
        self.entries.append(e); self.save(); return e

    def recall(self, query: str, limit: int = 6) -> list[MemEntry]:
        words = set(query.lower().split())
        scored = []
        for e in self.entries:
            overlap = len(words & set(e.content.lower().split()))
            tag_hit = sum(1 for t in e.tags if t.lower() in query.lower())
            score = overlap + tag_hit * 2 + e.importance * 0.1
            if score > 0: scored.append((score, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = [e for _, e in scored[:limit]]
        for e in out:
            e.accessed = datetime.now().isoformat()
        if out: self.save()
        return out

    def forget(self, mid: str) -> bool:
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.mid != mid]
        if len(self.entries) < before:
            self.save(); return True
        return False

    def context_block(self, query: str, limit: int = 5) -> str:
        hits = self.recall(query, limit)
        if not hits: return ""
        lines = ["## Memory Context"]
        for h in hits:
            lines.append(f"- [{h.mtype.value}] {h.content}")
        return "\n".join(lines)

    def stats(self) -> dict[str, Any]:
        by_type = {}
        for t in MemType:
            by_type[t.value] = sum(1 for e in self.entries if e.mtype == t)
        return {"total": len(self.entries), "by_type": by_type, "namespace": self.ns}

    def enforce_retention(self, max_age_days: int = 365, max_entries: int = 2000,
                          protect_above: int = 9) -> dict[str, int]:
        now = datetime.now(); removed_age = 0; removed_cap = 0
        cutoff = now - timedelta(days=max_age_days)
        kept = [e for e in self.entries
                if e.importance >= protect_above
                or datetime.fromisoformat(e.created) >= cutoff]
        removed_age = len(self.entries) - len(kept)
        self.entries = kept
        if len(self.entries) > max_entries:
            [e for e in self.entries if e.importance >= protect_above]
            unprot = sorted([e for e in self.entries if e.importance < protect_above],
                           key=lambda e: e.importance)
            drop = max(0, len(self.entries) - max_entries)
            drop_ids = {e.mid for e in unprot[:drop]}
            removed_cap = len(drop_ids)
            self.entries = [e for e in self.entries if e.mid not in drop_ids]
        self.save()
        return {"removed_age": removed_age, "removed_cap": removed_cap}


# ── CLI commands ──────────────────────────────────────────────────────────────

def cmd_memory_add(content: str, mtype: str = "fact", tags: str = "", importance: int = 5,
                   ns: str = "default"):
    store = MemoryStore(ns)
    entry = store.add(content, MemType(mtype),
                      tags=[t.strip() for t in tags.split(",") if t.strip()],
                      importance=importance)
    print(f"✓ Stored [{entry.mid}] {entry.content}")


def cmd_memory_recall(query: str, ns: str = "default", limit: int = 6):
    store = MemoryStore(ns)
    hits = store.recall(query, limit)
    if not hits:
        print("No matching memories."); return
    print(f"Memories matching '{query}':\n")
    for h in hits:
        print(f"  [{h.mid}] ({h.mtype.value}, importance={h.importance}) {h.content}")
        if h.tags: print(f"         tags: {', '.join(h.tags)}")


def cmd_memory_forget(mid: str, ns: str = "default"):
    store = MemoryStore(ns)
    if store.forget(mid): print(f"✓ Forgot {mid}")
    else: print(f"Not found: {mid}")


def cmd_memory_stats(ns: str = "default"):
    store = MemoryStore(ns)
    s = store.stats()
    print(f"Namespace: {s['namespace']}  |  Total: {s['total']}")
    for t, c in s["by_type"].items():
        print(f"  {t:<15} {c}")


def cmd_memory_retention(ns: str = "default", max_age: int = 365, max_entries: int = 2000):
    store = MemoryStore(ns)
    r = store.enforce_retention(max_age_days=max_age, max_entries=max_entries)
    print(f"✓ Retention applied — removed {r['removed_age']} by age, "
          f"{r['removed_cap']} by cap. {len(store.entries)} remain.")
