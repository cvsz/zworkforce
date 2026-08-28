from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import pytest
from zeaz_agent import (
    AgentLoop,
    ConservativeTokenCounter,
    ContextCompactor,
    ContextLimitExceeded,
    ModelOutput,
    Session,
    TextBlock,
    TokenBudget,
    TokenBudgetExceeded,
    TokenUsage,
    ToolDefinition,
    Turn,
)


def history(session_id, count: int, text_size: int = 300) -> tuple[Turn, ...]:
    return tuple(
        Turn(
            session_id=session_id,
            sequence=index,
            role="user" if index % 2 == 0 else "assistant",
            content=(TextBlock(text=f"turn-{index} " + "x" * text_size),),
        )
        for index in range(count)
    )


class UsageClient:
    def __init__(self, output: ModelOutput) -> None:
        self.output = output
        self.requests: list[tuple[tuple[Turn, ...], int]] = []

    async def respond(
        self,
        turns: Sequence[Turn],
        tools: Sequence[ToolDefinition],
        *,
        model: str,
        max_output_tokens: int,
        correlation_id: UUID,
    ) -> ModelOutput:
        self.requests.append((tuple(turns), max_output_tokens))
        return self.output


def test_compaction_is_deterministic_bounded_and_keeps_full_history_outside_projection() -> None:
    session = Session()
    turns = history(session.id, 10)
    counter = ConservativeTokenCounter()
    full_size = counter.count(turns, ())
    compactor = ContextCompactor(min_recent_turns=2, max_summary_chars=512)

    first = compactor.compact(turns, (), token_limit=full_size // 2)
    second = compactor.compact(turns, (), token_limit=full_size // 2)

    assert first == second
    assert first.omitted_turns > 0
    assert first.estimated_tokens <= full_size // 2
    assert len(turns) == 10
    assert len(first.turns) < len(turns)
    summary = first.turns[0].content[0]
    assert isinstance(summary, TextBlock)
    assert "Deterministic context summary" in summary.text
    assert "sha256=" in summary.text
    assert first.turns[-2:] == turns[-2:]


def test_compaction_fails_when_recent_turns_alone_do_not_fit() -> None:
    session = Session()
    turns = history(session.id, 2, text_size=2000)

    with pytest.raises(ContextLimitExceeded, match="exceed"):
        ContextCompactor(min_recent_turns=2).compact(turns, (), token_limit=128)


@pytest.mark.asyncio
async def test_loop_projects_context_and_accumulates_reported_usage() -> None:
    base = Session()
    turns = history(base.id, 8, text_size=400)
    session = Session(
        id=base.id,
        turns=turns,
        token_budget=TokenBudget(
            max_context_tokens=4000,
            max_output_tokens=500,
            max_total_tokens=10_000,
        ),
    )
    client = UsageClient(
        ModelOutput(
            blocks=(TextBlock(text="done"),),
            usage=TokenUsage(input_tokens=1200, output_tokens=25),
        )
    )

    result = await AgentLoop(
        client,
        compactor=ContextCompactor(max_summary_chars=512),
    ).start(session, (TextBlock(text="latest"),))

    projected, requested_output = client.requests[0]
    assert len(projected) < len(result.session.turns) - 1
    assert requested_output == 500
    assert result.session.token_usage == TokenUsage(input_tokens=1200, output_tokens=25)
    assert len(result.session.turns) == len(turns) + 2


@pytest.mark.asyncio
async def test_remaining_budget_reduces_requested_output() -> None:
    base = Session()
    session = Session(
        id=base.id,
        token_budget=TokenBudget(
            max_context_tokens=2000,
            max_output_tokens=1000,
            max_total_tokens=3000,
        ),
        token_usage=TokenUsage(input_tokens=1200, output_tokens=800),
    )
    client = UsageClient(
        ModelOutput(
            blocks=(TextBlock(text="small"),),
            usage=TokenUsage(input_tokens=500, output_tokens=10),
        )
    )

    result = await AgentLoop(client, max_output_tokens=1000).start(
        session,
        (TextBlock(text="continue"),),
    )

    assert 0 < client.requests[0][1] < 1000
    assert result.session.token_usage.total_tokens == 2510


@pytest.mark.asyncio
async def test_exhausted_budget_fails_before_provider_request() -> None:
    base = Session()
    session = Session(
        id=base.id,
        token_budget=TokenBudget(max_output_tokens=100, max_total_tokens=1000),
        token_usage=TokenUsage(input_tokens=600, output_tokens=399),
    )
    client = UsageClient(ModelOutput(blocks=(TextBlock(text="unused"),)))

    with pytest.raises(TokenBudgetExceeded, match="exhausted"):
        await AgentLoop(client).start(session, (TextBlock(text="no"),))

    assert client.requests == []


@pytest.mark.asyncio
async def test_excessive_reported_usage_is_rejected() -> None:
    base = Session()
    session = Session(
        id=base.id,
        token_budget=TokenBudget(
            max_context_tokens=2000,
            max_output_tokens=100,
            max_total_tokens=5000,
        ),
    )
    client = UsageClient(
        ModelOutput(
            blocks=(TextBlock(text="bad usage"),),
            usage=TokenUsage(input_tokens=100, output_tokens=101),
        )
    )

    with pytest.raises(TokenBudgetExceeded, match="requested limit"):
        await AgentLoop(client).start(session, (TextBlock(text="go"),))


def test_tool_schema_size_is_included_in_context_budget() -> None:
    session = Session()
    turns = history(session.id, 1, text_size=10)
    huge_tool = ToolDefinition(
        name="large",
        description="x" * 5000,
    )

    with pytest.raises(ContextLimitExceeded):
        ContextCompactor(min_recent_turns=1).compact(
            turns,
            (huge_tool,),
            token_limit=1000,
        )
