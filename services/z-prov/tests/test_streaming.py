from __future__ import annotations

import json

import pytest

from zeaz_provider.streaming import (
    anthropic_to_chat_stream,
    chat_to_anthropic_stream,
    chat_to_responses_stream,
    rewrite_sse_model,
    sse_events,
)


async def _chunks(*values: bytes):
    for value in values:
        yield value


@pytest.mark.asyncio
async def test_sse_parser_handles_fragmented_frames():
    result = [
        item async for item in sse_events(_chunks(
            b"event: ping\nda",
            b"ta: {\"x\":1}\n\ndata: [DONE]\n\n",
        ))
    ]
    assert result == [("ping", '{"x":1}'), ("message", "[DONE]")]


@pytest.mark.asyncio
async def test_anthropic_text_stream_maps_to_chat_order():
    source = _chunks(
        b'event: message_start\ndata: {"type":"message_start","message":{"id":"m1"}}\n\n',
        b'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,'
        b'"delta":{"type":"text_delta","text":"hi"}}\n\n',
        b'event: message_delta\ndata: {"type":"message_delta",'
        b'"delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":1}}\n\n',
        b'event: message_stop\ndata: {"type":"message_stop"}\n\n',
    )
    frames = [item async for item in sse_events(anthropic_to_chat_stream(source, "alias"))]
    payloads = [json.loads(raw) for _, raw in frames if raw != "[DONE]"]
    assert payloads[0]["choices"][0]["delta"] == {"role": "assistant"}
    assert payloads[1]["choices"][0]["delta"] == {"content": "hi"}
    assert payloads[2]["choices"][0]["finish_reason"] == "stop"
    assert frames[-1][1] == "[DONE]"


@pytest.mark.asyncio
async def test_chat_tool_stream_maps_to_anthropic_events():
    source = _chunks(
        b'data: {"id":"c1","choices":[{"delta":{"role":"assistant"},'
        b'"finish_reason":null}]}\n\n',
        b'data: {"id":"c1","choices":[{"delta":{"tool_calls":[{"index":0,"id":"t1",'
        b'"function":{"name":"weather","arguments":"{\\"city\\":"}}]},'
        b'"finish_reason":null}]}\n\n',
        b'data: {"id":"c1","choices":[{"delta":{"tool_calls":[{"index":0,'
        b'"function":{"arguments":"\\"BKK\\"}"}}]},"finish_reason":"tool_calls"}]}\n\n',
        b"data: [DONE]\n\n",
    )
    frames = [item async for item in sse_events(chat_to_anthropic_stream(source, "alias"))]
    names = [event for event, _ in frames]
    assert names[0] == "message_start"
    assert "content_block_start" in names
    assert names[-2:] == ["message_delta", "message_stop"]


@pytest.mark.asyncio
async def test_chat_text_stream_maps_to_responses_events():
    source = _chunks(
        b'data: {"id":"r1","choices":[{"delta":{"content":"hi"},"finish_reason":null}]}\n\n',
        b'data: {"id":"r1","choices":[{"delta":{},"finish_reason":"stop"}],'
        b'"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}\n\n',
        b"data: [DONE]\n\n",
    )
    frames = [item async for item in sse_events(chat_to_responses_stream(source, "alias"))]
    kinds = [json.loads(raw).get("type") for _, raw in frames if raw != "[DONE]"]
    assert kinds == [
        "response.created",
        "response.output_item.added",
        "response.output_text.delta",
        "response.completed",
    ]


@pytest.mark.asyncio
async def test_rewrite_sse_model_hides_provider_model_ids():
    source = _chunks(
        b'data: {"id":"c1","model":"private-model","choices":[]}\n\n',
        b"data: [DONE]\n\n",
    )
    frames = [item async for item in sse_events(rewrite_sse_model(source, "zeaz-alias", "chat"))]
    assert json.loads(frames[0][1])["model"] == "zeaz-alias"
    assert frames[1][1] == "[DONE]"


@pytest.mark.asyncio
async def test_invalid_provider_sse_is_replaced_with_safe_protocol_error():
    source = _chunks(b"data: not-json\n\n")
    frames = [item async for item in sse_events(rewrite_sse_model(source, "alias", "chat"))]
    assert json.loads(frames[0][1]) == {
        "error": {
            "type": "protocol_error",
            "message": "Provider returned invalid SSE data",
        }
    }
