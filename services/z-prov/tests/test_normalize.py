from zeaz_provider.normalize import (
    anthropic_to_openai,
    chat_to_responses,
    openai_request_to_anthropic,
    openai_to_anthropic,
    responses_to_chat,
)


def test_anthropic_text_and_tool_conversion():
    payload = {
        "model": "alias",
        "max_tokens": 100,
        "system": "Be concise",
        "messages": [{"role": "user", "content": "hello"}],
        "tools": [{
            "name": "weather",
            "description": "Weather",
            "input_schema": {"type": "object", "properties": {}},
        }],
    }
    result = anthropic_to_openai(payload, "backend-model")
    assert result["model"] == "backend-model"
    assert result["messages"][0] == {"role": "system", "content": "Be concise"}
    assert result["tools"][0]["function"]["name"] == "weather"


def test_openai_tool_response_conversion():
    response = {
        "id": "chat-1",
        "choices": [{
            "message": {
                "content": None,
                "tool_calls": [{
                    "id": "call-1",
                    "function": {"name": "weather", "arguments": '{"city":"BKK"}'},
                }],
            },
            "finish_reason": "tool_calls",
        }],
        "usage": {"prompt_tokens": 2, "completion_tokens": 3},
    }
    result = openai_to_anthropic(response, "alias")
    assert result["stop_reason"] == "tool_use"
    assert result["content"][0]["input"] == {"city": "BKK"}
    assert result["usage"] == {"input_tokens": 2, "output_tokens": 3}


def test_responses_round_trip_shape():
    chat = responses_to_chat({"input": "hello", "max_output_tokens": 99}, "model")
    assert chat["messages"] == [{"role": "user", "content": "hello"}]
    response = chat_to_responses(
        {"choices": [{"message": {"content": "hi"}}], "usage": {}},
        "alias",
    )
    assert response["object"] == "response"
    assert response["output"][0]["content"][0]["text"] == "hi"


def test_openai_request_preserves_developer_tools_results_images_and_schema():
    result = openai_request_to_anthropic({
        "messages": [
            {"role": "developer", "content": "Use JSON"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Inspect"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,AAAA"},
                    },
                ],
            },
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "inspect", "arguments": '{"x":1}'},
                }],
            },
            {"role": "tool", "tool_call_id": "call-1", "content": "done"},
        ],
        "tools": [{
            "type": "function",
            "function": {
                "name": "inspect",
                "description": "Inspect",
                "parameters": {"type": "object"},
            },
        }],
        "tool_choice": "required",
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "answer", "schema": {"type": "object"}},
        },
    }, "claude-model")
    assert result["system"] == "Use JSON"
    assert result["messages"][0]["content"][1]["source"]["media_type"] == "image/png"
    assert result["messages"][1]["content"][0]["input"] == {"x": 1}
    assert result["messages"][2]["content"][0]["type"] == "tool_result"
    assert result["tool_choice"] == {"type": "any"}
    assert result["output_config"]["format"]["schema"] == {"type": "object"}


def test_responses_input_items_map_to_chat_messages():
    result = responses_to_chat({
        "instructions": "Be concise",
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": "hello"}],
            },
            {
                "type": "function_call_output",
                "call_id": "call-1",
                "output": "sunny",
            },
        ],
        "max_output_tokens": 20,
        "tools": [{
            "type": "function",
            "name": "weather",
            "description": "Get weather",
            "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
        }],
    }, "model")
    assert result["messages"][0] == {"role": "developer", "content": "Be concise"}
    assert result["messages"][1]["content"][0] == {"type": "text", "text": "hello"}
    assert result["messages"][2] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": "sunny",
    }
    assert result["tools"] == [{
        "type": "function",
        "function": {
            "name": "weather",
            "description": "Get weather",
            "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
        },
    }]
