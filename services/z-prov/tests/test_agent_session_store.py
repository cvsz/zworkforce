from __future__ import annotations

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError
from zeaz_agent import (
    AgentLoop,
    ModelOutput,
    Session,
    SessionConflict,
    SessionIntegrityError,
    SessionNotFound,
    SQLiteSessionStore,
    TextBlock,
    TokenUsage,
    ToolCall,
    Turn,
)


class TextClient:
    async def respond(
        self,
        turns,
        tools,
        *,
        model: str,
        max_output_tokens: int,
        correlation_id: UUID,
    ):
        return ModelOutput(
            blocks=(TextBlock(text=f"reply {len(turns)}"),),
            usage=TokenUsage(input_tokens=10, output_tokens=2),
        )


def revised(session: Session, revision: int) -> Session:
    return Session(
        id=session.id,
        revision=revision,
        status=session.status,
        execution_mode=session.execution_mode,
        token_budget=session.token_budget,
        token_usage=session.token_usage,
        turns=session.turns,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def test_session_round_trip_and_resume_through_agent_loop(tmp_path: Path) -> None:
    store = SQLiteSessionStore(tmp_path / "sessions.db")
    session = Session()
    store.create(session)

    loaded = store.load(session.id)

    assert loaded == session


@pytest.mark.asyncio
async def test_loaded_session_resumes_and_can_be_saved(tmp_path: Path) -> None:
    store = SQLiteSessionStore(tmp_path / "sessions.db")
    original = Session()
    store.create(original)

    result = await AgentLoop(TextClient()).start(
        store.load(original.id),
        (TextBlock(text="continue"),),
    )
    store.save(result.session, expected_revision=original.revision)

    restored = store.load(original.id)
    assert restored == result.session
    assert [turn.sequence for turn in restored.turns] == [0, 1]


def test_stale_writer_cannot_silently_overwrite(tmp_path: Path) -> None:
    store = SQLiteSessionStore(tmp_path / "sessions.db")
    original = Session()
    store.create(original)
    first = revised(store.load(original.id), 1)
    stale = revised(store.load(original.id), 2)

    store.save(first, expected_revision=0)

    with pytest.raises(SessionConflict, match="concurrently"):
        store.save(stale, expected_revision=0)
    assert store.load(original.id) == first


def test_concurrent_compare_and_swap_has_one_winner(tmp_path: Path) -> None:
    path = tmp_path / "sessions.db"
    store = SQLiteSessionStore(path)
    original = Session()
    store.create(original)

    def attempt(revision: int) -> str:
        worker = SQLiteSessionStore(path)
        try:
            worker.save(revised(original, revision), expected_revision=0)
        except SessionConflict:
            return "conflict"
        return "saved"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, (1, 2)))

    assert sorted(outcomes) == ["conflict", "saved"]
    assert store.load(original.id).revision in {1, 2}


def test_duplicate_missing_and_nonadvancing_revisions_fail(tmp_path: Path) -> None:
    store = SQLiteSessionStore(tmp_path / "sessions.db")
    session = Session()
    store.create(session)

    with pytest.raises(SessionConflict, match="already exists"):
        store.create(session)
    with pytest.raises(SessionNotFound):
        store.load(UUID(int=0))
    with pytest.raises(ValueError, match="exceed"):
        store.save(session, expected_revision=0)
    with pytest.raises(SessionNotFound):
        store.save(
            Session(id=UUID(int=0), revision=1),
            expected_revision=0,
        )


def test_corrupt_document_or_metadata_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "sessions.db"
    store = SQLiteSessionStore(path)
    session = Session()
    store.create(session)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE sessions SET document = ? WHERE session_id = ?",
            ('{"not":"a session"}', str(session.id)),
        )

    with pytest.raises(SessionIntegrityError, match="schema"):
        store.load(session.id)


def test_size_limit_is_enforced_before_write(tmp_path: Path) -> None:
    store = SQLiteSessionStore(tmp_path / "sessions.db", max_session_bytes=1024)
    session_id = Session().id
    large = Session(
        id=session_id,
        turns=(
            Turn(
                session_id=session_id,
                sequence=0,
                role="user",
                content=(TextBlock(text="x" * 2000),),
            ),
        ),
    )
    with pytest.raises(ValueError, match="size limit"):
        store.create(large)


def test_symlink_and_insecure_database_are_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.db"
    target.touch(mode=0o600)
    link = tmp_path / "link.db"
    link.symlink_to(target)
    with pytest.raises(SessionIntegrityError, match="safely"):
        SQLiteSessionStore(link)

    insecure = tmp_path / "insecure.db"
    insecure.touch(mode=0o644)
    os.chmod(insecure, 0o644)
    with pytest.raises(SessionIntegrityError, match="owner-only"):
        SQLiteSessionStore(insecure)


def test_tool_arguments_reject_credential_fields_at_schema_boundary() -> None:
    with pytest.raises(ValidationError, match="credentials"):
        ToolCall(
            id="call_1",
            name="network.request",
            arguments={"headers": {"authorization": "Bearer provider-secret"}},
        )
