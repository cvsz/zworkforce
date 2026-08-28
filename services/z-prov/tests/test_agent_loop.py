from __future__ import annotations

import json
from collections.abc import Sequence
from uuid import UUID

import httpx
import pytest
from zeaz_agent import (
    AgentLoop,
    GatewayError,
    GatewayProtocolError,
    JsonlAuditLog,
    ModelOutput,
    RunStatus,
    Session,
    TextBlock,
    TokenUsage,
    ToolCall,
    ToolCallBlock,
    ToolDefinition,
    ToolResult,
    ToolResultBlock,
    Turn,
    ZeazProviderClient,
)


class FakeModelClient:
    def __init__(self, *responses: tuple[TextBlock | ToolCallBlock, ...]) -> None:
        self.responses = list(responses)
        self.requests: list[tuple[tuple[Turn, ...], tuple[ToolDefinition, ...], str, int, UUID]] = []

    async def respond(
        self,
        turns: Sequence[Turn],
        tools: Sequence[ToolDefinition],
        *,
        model: str,
        max_output_tokens: int,
        correlation_id: UUID,
    ) -> ModelOutput:
        self.requests.append((tuple(turns), tuple(tools), model, max_output_tokens, correlation_id))
        return ModelOutput(blocks=self.responses.pop(0), usage=TokenUsage())


@pytest.mark.asyncio
async def test_loop_completes_text_response_without_executing_tools() -> None:
    client = FakeModelClient((TextBlock(text="Hello"),))
    loop = AgentLoop(client)

    result = await loop.start(Session(), (TextBlock(text="Hi"),))

    assert result.status is RunStatus.COMPLETED
    assert result.pending_tool_calls == ()
    assert [turn.role.value for turn in result.session.turns] == ["user", "assistant"]
    assert result.session.revision == 2
    assert client.requests[0][2:4] == ("zeaz-auto", 4096)


@pytest.mark.asyncio
async def test_loop_emits_correlated_metadata_without_content(tmp_path) -> None:
    log = JsonlAuditLog(tmp_path / "audit.jsonl")
    client = FakeModelClient((TextBlock(text="secret response"),))
    loop = AgentLoop(client, audit=log)

    result = await loop.start(Session(), (TextBlock(text="secret prompt"),))

    events = log.verify()
    assert [entry.event.event_type for entry in events] == [
        "turn.user_appended",
        "model.requested",
        "model.completed",
    ]
    assert events[1].event.correlation_id == events[2].event.correlation_id
    raw = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "secret prompt" not in raw
    assert "secret response" not in raw
    assert result.status is RunStatus.COMPLETED


@pytest.mark.asyncio
async def test_loop_pauses_for_tools_then_resumes_with_exact_results() -> None:
    call = ToolCall(id="call_1", name="filesystem.read", arguments={"path": "README.md"})
    client = FakeModelClient(
        (ToolCallBlock(call=call),),
        (TextBlock(text="The title is ZeaZ."),),
    )
    tool = ToolDefinition(name="filesystem.read", parameters={"type": "object"})
    loop = AgentLoop(client)

    paused = await loop.start(Session(), (TextBlock(text="Read it"),), tools=(tool,))

    assert paused.status is RunStatus.REQUIRES_ACTION
    assert paused.pending_tool_calls == (call,)
    assert len(client.requests) == 1

    completed = await loop.resume(
        paused.session,
        (ToolResult(tool_call_id="call_1", output={"title": "ZeaZ"}),),
        tools=(tool,),
    )

    assert completed.status is RunStatus.COMPLETED
    assert [turn.role.value for turn in completed.session.turns] == [
        "user",
        "assistant",
        "tool",
        "assistant",
    ]
    result_block = completed.session.turns[2].content[0]
    assert isinstance(result_block, ToolResultBlock)
    assert len(client.requests) == 2


@pytest.mark.asyncio
async def test_resume_rejects_missing_duplicate_or_unrequested_results() -> None:
    calls = (
        ToolCallBlock(call=ToolCall(id="call_1", name="one")),
        ToolCallBlock(call=ToolCall(id="call_2", name="two")),
    )
    client = FakeModelClient(calls)
    loop = AgentLoop(client)
    paused = await loop.start(Session(), (TextBlock(text="go"),))

    with pytest.raises(ValueError, match="exactly once"):
        await loop.resume(
            paused.session,
            (ToolResult(tool_call_id="call_1", output="only one"),),
        )
    with pytest.raises(ValueError, match="exactly once"):
        await loop.resume(
            paused.session,
            (
                ToolResult(tool_call_id="call_1", output="one"),
                ToolResult(tool_call_id="call_1", output="duplicate"),
            ),
        )
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_user_cannot_inject_tool_protocol_blocks() -> None:
    client = FakeModelClient((TextBlock(text="unused"),))
    loop = AgentLoop(client)

    with pytest.raises(ValueError, match="cannot inject"):
        await loop.start(
            Session(),
            (ToolCallBlock(call=ToolCall(id="call_1", name="dangerous")),),
        )

    assert client.requests == []


@pytest.mark.asyncio
async def test_turn_limit_fails_before_provider_request() -> None:
    session = Session()
    first = Turn(
        session_id=session.id,
        sequence=0,
        role="user",
        content=(TextBlock(text="one"),),
    )
    session = Session(id=session.id, turns=(first,))
    client = FakeModelClient((TextBlock(text="unused"),))
    loop = AgentLoop(client, max_turns=2)

    with pytest.raises(RuntimeError, match="turn limit"):
        await loop.start(session, (TextBlock(text="two"),))

    assert client.requests == []


@pytest.mark.asyncio
async def test_gateway_client_uses_responses_contract_and_parses_tools() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "Working"}],
                    },
                    {
                        "type": "function_call",
                        "call_id": "call_7",
                        "name": "filesystem.read",
                        "arguments": '{"path":"README.md"}',
                    },
                ],
                "usage": {"input_tokens": 12, "output_tokens": 3, "total_tokens": 15},
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = ZeazProviderClient(
            "http://127.0.0.1:8080",
            "gateway-client-key",
            client=http_client,
        )
        session = Session()
        turn = Turn(
            session_id=session.id,
            sequence=0,
            role="user",
            content=(TextBlock(text="read"),),
        )
        output = await client.respond(
            (turn,),
            (ToolDefinition(name="filesystem.read"),),
            model="zeaz-auto",
            max_output_tokens=100,
            correlation_id=turn.correlation_id,
        )

    assert captured["url"] == "http://127.0.0.1:8080/v1/responses"
    assert captured["headers"]["x-api-key"] == "gateway-client-key"
    assert captured["headers"]["x-request-id"] == str(turn.correlation_id)
    assert captured["payload"]["model"] == "zeaz-auto"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["store"] is False
    assert captured["payload"]["input"][0]["content"][0]["type"] == "input_text"
    assert isinstance(output.blocks[0], TextBlock)
    assert isinstance(output.blocks[1], ToolCallBlock)
    assert output.blocks[1].call.arguments == {"path": "README.md"}
    assert output.usage == TokenUsage(input_tokens=12, output_tokens=3)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx.Response(502, json={"error": {"message": "untrusted detail"}}), GatewayError),
        (httpx.Response(200, content=b"not-json"), GatewayProtocolError),
        (httpx.Response(200, json={"output": []}), GatewayProtocolError),
        (
            httpx.Response(
                200,
                json={
                    "output": [{
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "read",
                        "arguments": "[]",
                    }]
                },
            ),
            GatewayProtocolError,
        ),
        (
            httpx.Response(
                200,
                json={
                    "output": [{
                        "type": "message",
                        "content": [{"type": "output_text", "text": "ok"}],
                    }],
                    "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 99},
                },
            ),
            GatewayProtocolError,
        ),
    ],
)
async def test_gateway_client_rejects_untrusted_responses(
    response: httpx.Response,
    error: type[Exception],
) -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response)) as http_client:
        client = ZeazProviderClient("https://gateway.example", "key", client=http_client)
        with pytest.raises(error) as caught:
            await client.respond(
                (),
                (),
                model="zeaz-auto",
                max_output_tokens=10,
                correlation_id=UUID(int=0),
            )
    assert "untrusted detail" not in str(caught.value)


@pytest.mark.asyncio
async def test_gateway_response_byte_limit_is_enforced() -> None:
    response = httpx.Response(
        200,
        json={"output": [{"type": "message", "content": [{"type": "output_text", "text": "x" * 2000}]}]},
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response)) as http_client:
        client = ZeazProviderClient(
            "https://gateway.example",
            "key",
            client=http_client,
            max_response_bytes=1024,
        )
        with pytest.raises(GatewayProtocolError, match="byte limit"):
            await client.respond(
                (),
                (),
                model="zeaz-auto",
                max_output_tokens=10,
                correlation_id=UUID(int=0),
            )


@pytest.mark.parametrize(
    "url",
    [
        "http://gateway.example",
        "https://user:password@gateway.example",
        "https://gateway.example?token=secret",
    ],
)
def test_gateway_url_fails_closed(url: str) -> None:
    with pytest.raises(ValueError):
        ZeazProviderClient(url, "key")
