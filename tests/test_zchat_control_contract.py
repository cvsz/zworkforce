from __future__ import annotations

import json
import os
import secrets
import socket
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

CONTROL_SERVER_SOURCE = os.environ.get("ZCHAT_CONTROL_SERVER_SOURCE", "").strip()
if not CONTROL_SERVER_SOURCE:
    pytest.skip(
        "ZCHAT_CONTROL_SERVER_SOURCE is required for the cross-repository contract test",
        allow_module_level=True,
    )

sys.path.insert(0, str(Path(CONTROL_SERVER_SOURCE) / "src"))

import uvicorn
from camfrog_control_server.app import create_app
from camfrog_control_server.config import Settings
from camfrog_control_server.models import Base
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from zworkforce.mcp import MCPError, RemoteMCPClient
from zworkforce.zchat_integration import fetch_capabilities, fetch_resource


def test_zworkforce_clients_match_live_zchat_read_only_contract() -> None:
    token = secrets.token_urlsafe(36)
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url="sqlite+pysqlite://",
        admin_api_token=secrets.token_urlsafe(36),
        jwt_signing_secret=secrets.token_urlsafe(36),
        zworkforce_integration_token=token,
    )
    app = create_app(settings, engine=engine)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", lifespan="on"))
    thread = threading.Thread(
        target=server.run,
        kwargs={"sockets": [listener]},
        daemon=True,
    )
    thread.start()

    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not server.started:
            time.sleep(0.05)
        assert server.started, "ZChat loopback server did not start"

        origin = f"http://127.0.0.1:{port}"
        integration_settings = SimpleNamespace(
            zchat_control_url=origin,
            zchat_integration_token=token,
        )
        capabilities = fetch_capabilities(integration_settings)
        health = fetch_resource(integration_settings, "health")
        assert capabilities["protocol"] == "zchat-zworkforce"
        assert capabilities["protocol_version"] == "1.0"
        assert len(capabilities["features"]) == 9
        assert health == {"status": "healthy", "database": "reachable"}

        client = RemoteMCPClient(
            f"{origin}/api/v1/integrations/zworkforce/v1/mcp",
            token,
            timeout=5,
        )
        discovery = client.discover()
        tools = client.list_tools()["tools"]
        resources = client.list_resources()["resources"]
        capability_result = client.call_tool("zchat.capabilities", {})
        health_result = client.read_resource("zchat://health")

        assert "2026-07-28" in discovery["supportedVersions"]
        assert {tool["name"] for tool in tools} == {
            "zchat.capabilities",
            "zchat.health",
        }
        assert all(tool["annotations"]["readOnlyHint"] for tool in tools)
        assert {resource["uri"] for resource in resources} == {
            "zchat://capabilities",
            "zchat://health",
        }
        assert capability_result["isError"] is False
        assert capability_result["structuredContent"]["protocol_version"] == "1.0"
        assert json.loads(health_result["contents"][0]["text"]) == {
            "status": "healthy",
            "database": "reachable",
        }

        mutation_result = client.call_tool("zchat.submit_command", {})
        assert mutation_result["isError"] is True

        invalid_client = RemoteMCPClient(
            f"{origin}/api/v1/integrations/zworkforce/v1/mcp",
            secrets.token_urlsafe(36),
            timeout=5,
        )
        with pytest.raises(MCPError, match="MCP request failed"):
            invalid_client.discover()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        engine.dispose()
    assert not thread.is_alive(), "ZChat loopback server did not stop"
