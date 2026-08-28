"""Secure request construction for remote MCP connectors."""

from __future__ import annotations

import os
from urllib.parse import urlparse

MCP_CONNECTOR_BETA = "mcp-client-2025-11-20"


class MCPConfigurationError(ValueError):
    """A remote MCP connector violates the platform security policy."""


def build_remote_mcp(
    server_name: str,
    url: str,
    tool_names: list[str],
    token_env: str | None = None,
) -> tuple[list[dict], list[dict], list[str]]:
    """Build an explicitly allowlisted remote-MCP payload.

    Tokens are resolved from an environment variable only and are never
    returned in diagnostics. Tool loading is deferred to bound prompt growth.
    """
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        raise MCPConfigurationError(
            "Remote MCP URL must be a non-loopback HTTPS URL"
        )
    if not server_name or not server_name.replace("_", "").replace("-", "").isalnum():
        raise MCPConfigurationError(
            "MCP server name must contain only letters, numbers, '_' or '-'"
        )

    names = [name.strip() for name in tool_names if name and name.strip()]
    if not names:
        raise MCPConfigurationError(
            "At least one MCP tool must be explicitly allowlisted"
        )

    server: dict[str, str] = {"type": "url", "name": server_name, "url": url}
    if token_env:
        token = os.getenv(token_env)
        if not token:
            raise MCPConfigurationError(
                f"MCP token environment variable '{token_env}' is not set"
            )
        server["authorization_token"] = token

    toolset = {
        "type": "mcp_toolset",
        "mcp_server_name": server_name,
        "default_config": {"enabled": False, "defer_loading": True},
        "configs": {
            name: {"enabled": True, "defer_loading": True} for name in names
        },
    }
    return [server], [toolset], [MCP_CONNECTOR_BETA]
