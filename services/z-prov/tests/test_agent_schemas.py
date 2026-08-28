from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from zeaz_agent import (
    Session,
    TextBlock,
    ToolCall,
    ToolCallBlock,
    ToolResult,
    ToolResultBlock,
    Turn,
)


def test_session_round_trip_preserves_discriminated_content() -> None:
    session_id = uuid4()
    requested = Turn(
        session_id=session_id,
        sequence=0,
        role="assistant",
        content=(
            TextBlock(text="Checking the workspace."),
            ToolCallBlock(
                call=ToolCall(
                    id="call_01",
                    name="filesystem.read",
                    arguments={"path": "README.md", "line": 10},
                )
            ),
        ),
    )
    completed = Turn(
        session_id=session_id,
        sequence=1,
        role="tool",
        content=(
            ToolResultBlock(
                result=ToolResult(
                    tool_call_id="call_01",
                    output={"text": "ZeaZ", "truncated": False},
                )
            ),
        ),
    )
    session = Session(id=session_id, revision=2, turns=(requested, completed))

    restored = Session.model_validate_json(session.model_dump_json())

    assert restored == session
    assert isinstance(restored.turns[0].content[1], ToolCallBlock)
    assert isinstance(restored.turns[1].content[0], ToolResultBlock)


def test_models_are_immutable_and_reject_unknown_fields() -> None:
    block = TextBlock(text="hello")

    with pytest.raises(ValidationError):
        block.text = "changed"
    with pytest.raises(ValidationError):
        TextBlock.model_validate({"type": "text", "text": "hello", "provider_key": "secret"})


@pytest.mark.parametrize(
    ("role", "content", "message"),
    [
        (
            "user",
            (ToolCallBlock(call=ToolCall(id="call_1", name="read")),),
            "tool calls are only valid",
        ),
        (
            "assistant",
            (ToolResultBlock(result=ToolResult(tool_call_id="call_1", output="done")),),
            "tool results are only valid",
        ),
        ("tool", (TextBlock(text="done"),), "tool turns must contain"),
    ],
)
def test_turn_role_rejects_invalid_tool_content(role: str, content: tuple, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Turn(session_id=uuid4(), sequence=0, role=role, content=content)


def test_session_rejects_foreign_duplicate_or_unordered_turns() -> None:
    session_id = uuid4()
    foreign = Turn(
        session_id=uuid4(),
        sequence=0,
        role="user",
        content=(TextBlock(text="hello"),),
    )
    with pytest.raises(ValidationError, match="belong"):
        Session(id=session_id, turns=(foreign,))

    first = Turn(
        session_id=session_id,
        sequence=1,
        role="user",
        content=(TextBlock(text="one"),),
    )
    second = Turn(
        session_id=session_id,
        sequence=0,
        role="assistant",
        content=(TextBlock(text="two"),),
    )
    with pytest.raises(ValidationError, match="strictly increasing"):
        Session(id=session_id, turns=(first, second))

    duplicate = first.model_copy(update={"sequence": 2})
    with pytest.raises(ValidationError, match="turn IDs must be unique"):
        Session(id=session_id, turns=(first, duplicate))


def test_naive_or_reversed_timestamps_are_rejected() -> None:
    naive = datetime(2026, 1, 1)
    with pytest.raises(ValidationError, match="UTC offset"):
        Turn(
            session_id=uuid4(),
            sequence=0,
            role="user",
            content=(TextBlock(text="hello"),),
            created_at=naive,
        )

    later = datetime(2026, 1, 2, tzinfo=UTC)
    earlier = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValidationError, match="cannot precede"):
        Session(created_at=later, updated_at=earlier)


def test_schema_is_versioned_and_uses_discriminators() -> None:
    schema = Session.model_json_schema()
    turn_schema = schema["$defs"]["Turn"]
    content = turn_schema["properties"]["content"]
    item_schema = content["items"]

    assert Session().schema_version == "1"
    assert item_schema["discriminator"]["propertyName"] == "type"
    assert set(item_schema["discriminator"]["mapping"]) == {"image", "text", "tool_call", "tool_result"}


def test_bounds_and_identifiers_fail_closed() -> None:
    with pytest.raises(ValidationError):
        TextBlock(text="")
    with pytest.raises(ValidationError):
        ToolCall(id="../escape", name="filesystem.read")
    with pytest.raises(ValidationError):
        ToolCall(id="call_1", name="shell command")
