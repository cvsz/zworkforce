from __future__ import annotations

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from zeaz_agent import (
    MemoryConflict,
    MemoryIntegrityError,
    MemoryNotFound,
    MemoryRecord,
    Session,
    SQLiteMemoryStore,
    SQLiteSessionStore,
)


def record(namespace: str = "user:alice", *, content: str = "Prefers concise answers.") -> MemoryRecord:
    return MemoryRecord(
        namespace=namespace,
        key="response-style",
        kind="preference",
        content=content,
        tags=("style", "response"),
        metadata={"source": "explicit-user-setting"},
    )


def revised(value: MemoryRecord, revision: int, content: str) -> MemoryRecord:
    return MemoryRecord(
        id=value.id,
        namespace=value.namespace,
        key=value.key,
        kind=value.kind,
        content=content,
        tags=value.tags,
        metadata=value.metadata,
        revision=revision,
        created_at=value.created_at,
        updated_at=value.updated_at,
    )


def test_memory_round_trip_and_scoped_search(tmp_path: Path) -> None:
    store = SQLiteMemoryStore(tmp_path / "memory.db")
    alice = record()
    bob = record("user:bob", content="Prefers detailed answers.")
    store.put(alice)
    store.put(bob)

    assert store.get("user:alice", alice.id) == alice
    assert store.search("user:alice", "concise") == (alice,)
    assert store.search("user:alice", "response-style") == (alice,)
    assert store.search("user:alice", "detailed") == ()
    with pytest.raises(MemoryNotFound):
        store.get("user:bob", alice.id)


def test_literal_wildcards_do_not_expand_search_scope(tmp_path: Path) -> None:
    store = SQLiteMemoryStore(tmp_path / "memory.db")
    value = record(content="100% literal_value")
    store.put(value)

    assert store.search(value.namespace, "%") == (value,)
    assert store.search(value.namespace, "_") == (value,)
    assert store.search(value.namespace, "missing%") == ()


def test_optimistic_memory_update_rejects_stale_writer(tmp_path: Path) -> None:
    store = SQLiteMemoryStore(tmp_path / "memory.db")
    original = record()
    store.put(original)
    first = revised(original, 1, "First update")
    stale = revised(original, 2, "Stale update")

    store.put(first, expected_revision=0)

    with pytest.raises(MemoryConflict, match="concurrently"):
        store.put(stale, expected_revision=0)
    assert store.get(original.namespace, original.id) == first


def test_concurrent_memory_compare_and_swap_has_one_winner(tmp_path: Path) -> None:
    path = tmp_path / "memory.db"
    store = SQLiteMemoryStore(path)
    original = record()
    store.put(original)

    def attempt(revision: int) -> str:
        worker = SQLiteMemoryStore(path)
        try:
            worker.put(
                revised(original, revision, f"update {revision}"),
                expected_revision=0,
            )
        except MemoryConflict:
            return "conflict"
        return "saved"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, (1, 2)))

    assert sorted(outcomes) == ["conflict", "saved"]


def test_duplicate_missing_and_nonadvancing_memory_fail(tmp_path: Path) -> None:
    store = SQLiteMemoryStore(tmp_path / "memory.db")
    value = record()
    store.put(value)

    with pytest.raises(MemoryConflict, match="already exists"):
        store.put(value)
    with pytest.raises(ValueError, match="exceed"):
        store.put(value, expected_revision=0)
    with pytest.raises(MemoryNotFound):
        store.get(value.namespace, Session().id)


def test_corrupt_memory_document_or_index_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "memory.db"
    store = SQLiteMemoryStore(path)
    value = record()
    store.put(value)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            UPDATE memories SET content = ?
            WHERE namespace = ? AND memory_id = ?
            """,
            ("different", value.namespace, str(value.id)),
        )

    with pytest.raises(MemoryIntegrityError, match="inconsistent"):
        store.get(value.namespace, value.id)


def test_record_and_query_bounds_fail_closed(tmp_path: Path) -> None:
    store = SQLiteMemoryStore(tmp_path / "memory.db", max_record_bytes=1024)
    with pytest.raises(ValueError, match="size limit"):
        store.put(record(content="x" * 2000))
    with pytest.raises(ValueError, match="between"):
        store.search("user:alice", "")
    with pytest.raises(ValueError, match="limit"):
        store.search("user:alice", "x", limit=101)


def test_memory_and_sessions_can_share_one_local_database(tmp_path: Path) -> None:
    path = tmp_path / "agent.db"
    sessions = SQLiteSessionStore(path)
    memory = SQLiteMemoryStore(path)
    session = Session()
    value = record()
    sessions.create(session)
    memory.put(value)

    assert sessions.load(session.id) == session
    assert memory.get(value.namespace, value.id) == value


def test_symlink_and_insecure_memory_database_are_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.db"
    target.touch(mode=0o600)
    link = tmp_path / "link.db"
    link.symlink_to(target)
    with pytest.raises(MemoryIntegrityError, match="safely"):
        SQLiteMemoryStore(link)

    insecure = tmp_path / "insecure.db"
    insecure.touch(mode=0o644)
    os.chmod(insecure, 0o644)
    with pytest.raises(MemoryIntegrityError, match="owner-only"):
        SQLiteMemoryStore(insecure)
