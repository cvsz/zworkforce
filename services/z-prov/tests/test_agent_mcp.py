import json
import sys
from pathlib import Path

import httpx
import pytest
from zeaz_agent.mcp import (
    MCPPolicyError,
    MCPProtocolError,
    MCPRemoteError,
    StdioTransport,
    StreamableHTTPTransport,
)

ALLOWED_METHODS = ("initialize", "tools/list", "tools/call")


def http_transport(handler, **kwargs) -> StreamableHTTPTransport:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return StreamableHTTPTransport(
        "https://mcp.example.test/service",
        allowed_hosts=("mcp.example.test",),
        allowed_methods=ALLOWED_METHODS,
        client=client,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_https_json_request_is_bounded_and_carries_session() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content)
        return httpx.Response(
            200,
            headers={
                "content-type": "application/json",
                "mcp-session-id": "session-1",
            },
            json={"jsonrpc": "2.0", "id": payload["id"], "result": {"ok": True}},
        )

    transport = http_transport(handler)
    assert await transport.request("initialize", {"client": "zeaz"}) == {"ok": True}
    assert await transport.request("tools/list") == {"ok": True}
    assert requests[0].headers["accept"] == "application/json, text/event-stream"
    assert "mcp-session-id" not in requests[0].headers
    assert requests[1].headers["mcp-session-id"] == "session-1"
    await transport.aclose()
    await transport._client.aclose()


@pytest.mark.asyncio
async def test_https_accepts_matching_response_from_sse() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        request_id = json.loads(request.content)["id"]
        body = (
            'event: message\ndata: {"jsonrpc":"2.0","method":"notifications/progress"}\n\n'
            f'data: {{"jsonrpc":"2.0","id":{request_id},"result":["tool"]}}\n\n'
        )
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream; charset=utf-8"},
            text=body,
        )

    transport = http_transport(handler)
    assert await transport.request("tools/list") == ["tool"]
    await transport._client.aclose()


@pytest.mark.parametrize(
    "endpoint,hosts",
    [
        ("http://mcp.example.test/mcp", ("mcp.example.test",)),
        ("https://evil.example/mcp", ("mcp.example.test",)),
        ("https://user:pass@mcp.example.test/mcp", ("mcp.example.test",)),
        ("https://mcp.example.test/mcp#fragment", ("mcp.example.test",)),
    ],
)
def test_https_endpoint_policy_is_exact(endpoint: str, hosts: tuple[str, ...]) -> None:
    with pytest.raises(MCPPolicyError):
        StreamableHTTPTransport(
            endpoint,
            allowed_hosts=hosts,
            allowed_methods=ALLOWED_METHODS,
        )


@pytest.mark.asyncio
async def test_https_denies_method_before_network() -> None:
    called = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    transport = http_transport(handler)
    with pytest.raises(MCPPolicyError):
        await transport.request("resources/read")
    assert not called
    await transport._client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response,error",
    [
        (
            httpx.Response(302, headers={"location": "https://evil.example/mcp"}),
            MCPPolicyError,
        ),
        (
            httpx.Response(200, headers={"content-type": "text/plain"}, text="hello"),
            MCPProtocolError,
        ),
        (
            httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"jsonrpc": "2.0", "id": 999, "result": None},
            ),
            MCPProtocolError,
        ),
        (
            httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": -32000, "message": "untrusted details"},
                },
            ),
            MCPRemoteError,
        ),
    ],
)
async def test_https_rejects_untrusted_responses(response, error) -> None:
    transport = http_transport(lambda _: response)
    with pytest.raises(error) as raised:
        await transport.request("tools/list")
    assert "untrusted details" not in str(raised.value)
    await transport._client.aclose()


@pytest.mark.asyncio
async def test_https_rejects_excessive_body() -> None:
    response = httpx.Response(
        200,
        headers={"content-type": "application/json"},
        content=b"x" * 1025,
    )
    transport = http_transport(lambda _: response, max_response_bytes=1024)
    with pytest.raises(MCPProtocolError, match="byte limit"):
        await transport.request("tools/list")
    await transport._client.aclose()


@pytest.mark.asyncio
async def test_https_rejects_excessive_or_non_json_request_before_network() -> None:
    called = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    transport = http_transport(handler, max_response_bytes=1024)
    with pytest.raises(MCPProtocolError, match="size"):
        await transport.request("tools/call", {"value": "x" * 2048})
    with pytest.raises(MCPProtocolError, match="valid JSON"):
        await transport.request("tools/call", {"value": object()})  # type: ignore[dict-item]
    assert not called
    await transport._client.aclose()


def stdio_transport(script: str, **kwargs) -> StdioTransport:
    return StdioTransport(
        (str(Path(sys.executable).resolve(strict=True)), "-c", script),
        allowed_methods=ALLOWED_METHODS,
        timeout_seconds=1,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_stdio_round_trip_and_does_not_inherit_environment(monkeypatch) -> None:
    monkeypatch.setenv("PROVIDER_API_KEY", "must-not-cross-boundary")
    script = (
        "import json,os,sys\n"
        "for line in sys.stdin:\n"
        " r=json.loads(line); print(json.dumps({'jsonrpc':'2.0','id':r['id'],"
        "'result':{'secret_present':'PROVIDER_API_KEY' in os.environ}}),flush=True)\n"
    )
    transport = stdio_transport(script)
    assert await transport.request("initialize") == {"secret_present": False}
    await transport.aclose()


@pytest.mark.asyncio
async def test_stdio_denies_method_without_starting_process() -> None:
    transport = stdio_transport("raise SystemExit(99)")
    with pytest.raises(MCPPolicyError):
        await transport.request("prompts/get")
    assert transport._process is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "script,match",
    [
        (
            "import json,sys;r=json.loads(sys.stdin.readline());"
            "print(json.dumps({'jsonrpc':'2.0','id':999,'result':None}),flush=True)",
            "match",
        ),
        (
            "import sys,time;sys.stdin.readline();time.sleep(2)",
            "timed out",
        ),
        (
            "import sys;sys.stdin.readline();print('x'*2048,flush=True)",
            "limit",
        ),
    ],
)
async def test_stdio_rejects_bad_timeout_and_excessive_responses(
    script: str,
    match: str,
) -> None:
    transport = stdio_transport(script, max_message_bytes=1024)
    with pytest.raises(MCPProtocolError, match=match):
        await transport.request("tools/list")
    await transport.aclose()


def test_stdio_requires_absolute_real_executable(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="absolute"):
        StdioTransport(("python",), allowed_methods=ALLOWED_METHODS)
    link = tmp_path / "python"
    link.symlink_to(sys.executable)
    with pytest.raises(ValueError, match="regular file"):
        StdioTransport((str(link),), allowed_methods=ALLOWED_METHODS)
