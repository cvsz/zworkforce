import json

import pytest

from zaicoder.gateway_client import GatewayClient, GatewayError


class Response:
    def __init__(self, body: object):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self._body).encode()


def test_posts_openai_compatible_request_with_service_token():
    captured = {}

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode())
        return Response({"choices": [{"message": {"content": "hello"}}]})

    client = GatewayClient("https://gateway.example/v1", "token-1", opener=opener)
    assert client.chat(model="coding", prompt="Hi") == "hello"
    assert captured["url"] == "https://gateway.example/v1/chat/completions"
    assert captured["body"]["messages"] == [{"role": "user", "content": "Hi"}]
    assert captured["headers"]["Authorization"] == "Bearer token-1"


def test_rejects_malformed_gateway_response():
    client = GatewayClient(
        "https://gateway.example/v1",
        "token-1",
        opener=lambda request, timeout: Response({"choices": []}),
    )
    with pytest.raises(GatewayError, match="unsupported response"):
        client.chat(model="coding", prompt="Hi")


def test_rejects_missing_token_and_invalid_inputs():
    with pytest.raises(ValueError, match="token"):
        GatewayClient("https://gateway.example/v1", "")

    client = GatewayClient("https://gateway.example/v1", "token-1")
    with pytest.raises(ValueError, match="Model"):
        client.chat(model="", prompt="Hi")
    with pytest.raises(ValueError, match="Prompt"):
        client.chat(model="coding", prompt="")
