from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from zeaz_agent import (
    AgentLoop,
    DeterministicModelClient,
    DeterministicUUIDFactory,
    ExpectedModelRequest,
    FixedClock,
    ModelOutput,
    ScriptedModelStep,
    ScriptedProviderError,
    Session,
    TextBlock,
    TokenUsage,
    ToolCall,
    ToolCallBlock,
    ToolDefinition,
)


def scripted_steps() -> tuple[ScriptedModelStep, ...]:
    return (
        ScriptedModelStep(
            expected=ExpectedModelRequest(
                model="zeaz-auto",
                roles=("user",),
                tool_names=("filesystem.read",),
                max_output_tokens=4096,
            ),
            output=ModelOutput(
                blocks=(
                    ToolCallBlock(
                        call=ToolCall(
                            id="call_1",
                            name="filesystem.read",
                            arguments={"path": "README.md"},
                        )
                    ),
                ),
                usage=TokenUsage(input_tokens=10, output_tokens=2),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_scripted_provider_records_and_validates_exact_request_contract() -> None:
    client = DeterministicModelClient(scripted_steps())
    loop = AgentLoop(
        client,
        uuid_factory=DeterministicUUIDFactory("request-contract"),
        clock=FixedClock(),
    )
    tool = ToolDefinition(name="filesystem.read", mutating=False)

    result = await loop.start(Session(), (TextBlock(text="Read it"),), tools=(tool,))

    client.assert_exhausted()
    assert result.pending_tool_calls[0].id == "call_1"
    assert len(client.requests) == 1
    assert client.requests[0].context_sha256


@pytest.mark.asyncio
async def test_scripted_fault_is_stable_and_sanitized_by_code() -> None:
    client = DeterministicModelClient(
        (
            ScriptedModelStep(
                error_code="upstream_unavailable",
                expected=ExpectedModelRequest(roles=("user",)),
            ),
        )
    )

    with pytest.raises(ScriptedProviderError) as caught:
        await AgentLoop(client).start(Session(), (TextBlock(text="hello"),))

    assert caught.value.code == "upstream_unavailable"
    client.assert_exhausted()


@pytest.mark.asyncio
async def test_identical_fixture_runs_replay_to_identical_session_state() -> None:
    fixed_time = datetime(2026, 1, 1, tzinfo=UTC)
    initial = Session(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        created_at=fixed_time,
        updated_at=fixed_time,
    )

    async def run_once():
        client = DeterministicModelClient(
            (
                ScriptedModelStep(
                    output=ModelOutput(
                        blocks=(TextBlock(text="same response"),),
                        usage=TokenUsage(input_tokens=5, output_tokens=2),
                    )
                ),
            )
        )
        loop = AgentLoop(
            client,
            uuid_factory=DeterministicUUIDFactory("replay-seed"),
            clock=FixedClock(fixed_time),
        )
        return await loop.start(initial, (TextBlock(text="same input"),))

    first = await run_once()
    second = await run_once()

    assert first == second
    assert first.session.model_dump_json() == second.session.model_dump_json()


@pytest.mark.asyncio
async def test_exhaustion_and_unmet_expectations_fail_loudly() -> None:
    client = DeterministicModelClient(
        (
            ScriptedModelStep(
                expected=ExpectedModelRequest(model="zeaz-local"),
                output=ModelOutput(blocks=(TextBlock(text="unused"),)),
            ),
        )
    )
    with pytest.raises(AssertionError, match="expected model"):
        await AgentLoop(client).start(Session(), (TextBlock(text="hello"),))

    with pytest.raises(AssertionError, match="exhausted"):
        await client.respond(
            (),
            (),
            model="zeaz-auto",
            max_output_tokens=1,
            correlation_id=UUID(int=0),
        )


def test_uuid_and_clock_fixtures_are_reproducible_and_validate_inputs() -> None:
    first = DeterministicUUIDFactory("seed")
    second = DeterministicUUIDFactory("seed")

    assert [first(), first(), first()] == [second(), second(), second()]
    assert FixedClock()() == FixedClock()()
    with pytest.raises(ValueError):
        DeterministicUUIDFactory("")
    with pytest.raises(ValueError):
        FixedClock(datetime(2026, 1, 1))
