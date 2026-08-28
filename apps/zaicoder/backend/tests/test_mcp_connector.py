import pytest

from zaicoder.mcp_connector import MCPConfigurationError, build_remote_mcp


def test_builds_explicit_deferred_toolset(monkeypatch):
    monkeypatch.setenv("MCP_TOKEN", "secret")
    servers, tools, betas = build_remote_mcp(
        "project-mcp",
        "https://mcp.example.com/sse",
        ["search", "write"],
        "MCP_TOKEN",
    )
    assert servers[0]["authorization_token"] == "secret"
    assert tools[0]["default_config"] == {"enabled": False, "defer_loading": True}
    assert set(tools[0]["configs"]) == {"search", "write"}
    assert betas == ["mcp-client-2025-11-20"]


@pytest.mark.parametrize("url", ["http://mcp.example.com", "https://localhost/sse"])
def test_rejects_unsafe_remote_urls(url):
    with pytest.raises(MCPConfigurationError):
        build_remote_mcp("safe", url, ["read"])


def test_requires_explicit_tool_allowlist():
    with pytest.raises(MCPConfigurationError, match="allowlisted"):
        build_remote_mcp("safe", "https://mcp.example.com", [])


def test_token_env_is_required(monkeypatch):
    monkeypatch.delenv("MISSING", raising=False)
    with pytest.raises(MCPConfigurationError, match="not set"):
        build_remote_mcp("safe", "https://mcp.example.com", ["read"], "MISSING")
