import asyncio
import ipaddress
import json
from pathlib import Path
from uuid import UUID

import pytest
from zeaz_sandbox.backend import CommandResult, SandboxBackendError
from zeaz_sandbox.egress import DockerProxyEgressController
from zeaz_sandbox.egress_proxy import (
    DestinationPolicy,
    ProxyLimits,
    SocksEgressProxy,
    _safe_resolution,
)
from zeaz_sandbox.schemas import (
    EgressDestination,
    JobSpec,
    NetworkMode,
    SandboxPolicy,
)

SESSION_ID = UUID("00000000-0000-0000-0000-000000000001")
CORRELATION_ID = UUID("00000000-0000-0000-0000-000000000002")
JOB_ID = UUID("00000000-0000-0000-0000-000000000004")
PROXY_IMAGE = "registry.example/zeaz/egress@sha256:" + "e" * 64
PROXY_ID = "f" * 64


class FakeRunner:
    def __init__(self, results: list[CommandResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, ...]] = []

    async def run(self, argv, **_) -> CommandResult:
        self.calls.append(tuple(argv))
        return self.results.pop(0)


class LocalPolicy:
    def __init__(self, port: int) -> None:
        self.port = port

    async def resolve(self, host: str, port: int) -> tuple[str, ...]:
        if host == "echo.example" and port == self.port:
            return ("127.0.0.1",)
        return ()


def result(stdout=b"", returncode=0) -> CommandResult:
    return CommandResult(returncode=returncode, stdout=stdout, stderr=b"")


def job(tmp_path: Path) -> JobSpec:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return JobSpec(
        id=JOB_ID,
        session_id=SESSION_ID,
        correlation_id=CORRELATION_ID,
        image="registry.example/worker@sha256:" + "a" * 64,
        command=("/usr/bin/true",),
        workspace=workspace,
        policy=SandboxPolicy(
            network_mode=NetworkMode.ALLOW_LIST,
            allowed_destinations=(
                EgressDestination(host="api.example.com", ports=(443, 8443)),
            ),
        ),
    )


def test_destination_policy_is_exact_and_bounded() -> None:
    policy = DestinationPolicy(("api.example.com:443", "api.example.com:8443"))
    assert policy.allows("API.EXAMPLE.COM.", 443)
    assert not policy.allows("sub.api.example.com", 443)
    assert not policy.allows("api.example.com", 80)
    for invalid in ("", "host", "host:0", "host:65536", ":443"):
        with pytest.raises(ValueError):
            DestinationPolicy((invalid,))


def test_dns_resolution_policy_blocks_rebinding_and_metadata_ranges() -> None:
    assert not _safe_resolution(
        ipaddress.ip_address("169.254.169.254"),
        explicitly_allowed=None,
    )
    assert not _safe_resolution(
        ipaddress.ip_address("10.0.0.1"),
        explicitly_allowed=None,
    )
    assert _safe_resolution(
        ipaddress.ip_address("10.0.0.1"),
        explicitly_allowed=ipaddress.ip_address("10.0.0.1"),
    )
    assert not _safe_resolution(
        ipaddress.ip_address("127.0.0.1"),
        explicitly_allowed=ipaddress.ip_address("127.0.0.1"),
    )


@pytest.mark.asyncio
async def test_socks_proxy_relays_only_policy_approved_destination() -> None:
    async def echo(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        data = await reader.read(1024)
        writer.write(data.upper())
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    upstream = await asyncio.start_server(echo, "127.0.0.1", 0)
    upstream_port = upstream.sockets[0].getsockname()[1]
    proxy = SocksEgressProxy(
        LocalPolicy(upstream_port),  # type: ignore[arg-type]
        limits=ProxyLimits(idle_timeout_seconds=2),
    )
    server = await asyncio.start_server(proxy.handle, "127.0.0.1", 0)
    proxy_port = server.sockets[0].getsockname()[1]
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", proxy_port)
        writer.write(b"\x05\x01\x00")
        await writer.drain()
        assert await reader.readexactly(2) == b"\x05\x00"
        host = b"echo.example"
        writer.write(
            b"\x05\x01\x00\x03"
            + bytes((len(host),))
            + host
            + upstream_port.to_bytes(2, "big")
        )
        await writer.drain()
        assert (await reader.readexactly(10))[1] == 0
        writer.write(b"hello")
        await writer.drain()
        writer.write_eof()
        assert await reader.readexactly(5) == b"HELLO"
        writer.close()
        await writer.wait_closed()
    finally:
        server.close()
        upstream.close()
        await server.wait_closed()
        await upstream.wait_closed()


@pytest.mark.asyncio
async def test_controller_builds_internal_network_and_hardened_proxy(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(
        [
            result(stdout=json.dumps([PROXY_IMAGE]).encode()),
            result(stdout=b"network-id\n"),
            result(stdout=(PROXY_ID + "\n").encode()),
            result(),
            result(),
            result(),
            result(),
        ]
    )
    controller = DockerProxyEgressController(
        PROXY_IMAGE,
        runner=runner,
        docker_host="unix:///run/user/1000/docker.sock",
    )
    attachment = await controller.prepare(job(tmp_path))
    assert attachment.docker_network == f"zeaz-net-{JOB_ID.hex}"
    assert attachment.proxy_url == "socks5h://egress-proxy:1080"
    network_create = runner.calls[1]
    assert network_create[1:4] == ("network", "create", "--internal")
    proxy_create = runner.calls[2]
    joined = "\n".join(proxy_create)
    assert "--network\nbridge" in joined
    assert "--read-only" in proxy_create
    assert "--cap-drop\nALL" in joined
    assert "no-new-privileges=true" in proxy_create
    assert "seccomp=builtin" in proxy_create
    assert "--allow\napi.example.com:443" in joined
    assert "--allow\napi.example.com:8443" in joined
    assert runner.calls[3][1:5] == (
        "network",
        "connect",
        "--alias",
        "egress-proxy",
    )
    await controller.cleanup(attachment)
    assert runner.calls[-2][1:3] == ("rm", "--force")
    assert runner.calls[-1][1:3] == ("network", "rm")


@pytest.mark.asyncio
async def test_controller_rolls_back_network_when_proxy_creation_fails(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(
        [
            result(stdout=json.dumps([PROXY_IMAGE]).encode()),
            result(),
            result(returncode=1),
            result(),
        ]
    )
    controller = DockerProxyEgressController(
        PROXY_IMAGE,
        runner=runner,
        docker_host="unix:///run/user/1000/docker.sock",
    )
    with pytest.raises(SandboxBackendError, match="proxy creation"):
        await controller.prepare(job(tmp_path))
    assert runner.calls[-1][1:3] == ("network", "rm")
