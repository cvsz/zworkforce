import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

import pytest
from zeaz_sandbox.backend import (
    CommandResult,
    ContainerStopReason,
    NetworkAttachment,
    RootlessDockerBackend,
    SandboxBackendError,
    SubprocessCommandRunner,
)
from zeaz_sandbox.schemas import (
    EgressDestination,
    JobSpec,
    NetworkMode,
    SandboxLimits,
    SandboxPolicy,
    WorkspaceAccess,
)
from zeaz_sandbox.streaming import BoundedOutputStreamer, OutputChannel

SESSION_ID = UUID("00000000-0000-0000-0000-000000000001")
CORRELATION_ID = UUID("00000000-0000-0000-0000-000000000002")
IMAGE = "registry.example/worker@sha256:" + "a" * 64


class FakeRunner:
    def __init__(self, results: list[CommandResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, ...]] = []

    async def run(self, argv, **_) -> CommandResult:
        self.calls.append(tuple(argv))
        return self.results.pop(0)


class FakeEgress:
    def __init__(self) -> None:
        self.prepared: JobSpec | None = None
        self.cleaned: NetworkAttachment | None = None

    async def prepare(self, job: JobSpec) -> NetworkAttachment:
        self.prepared = job
        return NetworkAttachment(
            docker_network="zeaz-egress-job",
            proxy_url="socks5h://egress-proxy:1080",
            cleanup_token="token",
        )

    async def cleanup(self, attachment: NetworkAttachment) -> None:
        self.cleaned = attachment


class CollectingSink:
    def __init__(self) -> None:
        self.events: list[tuple[OutputChannel, bytes]] = []

    async def emit(self, channel: OutputChannel, data: bytes) -> None:
        self.events.append((channel, data))


def job(workspace: Path, **changes) -> JobSpec:
    values = {
        "session_id": SESSION_ID,
        "correlation_id": CORRELATION_ID,
        "image": IMAGE,
        "command": ("/usr/bin/python3", "-c", "print('hello')"),
        "workspace": workspace,
    }
    values.update(changes)
    return JobSpec(**values)


def result(stdout=b"", stderr=b"", returncode=0) -> CommandResult:
    return CommandResult(returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "options",
    (
        ["name=apparmor", "name=seccomp,profile=builtin"],
        ["name=rootless", "name=seccomp,profile=builtin"],
        ["name=rootless", "name=apparmor"],
        None,
    ),
)
async def test_probe_requires_rootless_seccomp_and_apparmor(options) -> None:
    stdout = b"not-json" if options is None else json.dumps(options).encode()
    backend = RootlessDockerBackend(runner=FakeRunner([result(stdout=stdout)]))
    with pytest.raises(SandboxBackendError, match="rootless|invalid"):
        await backend.probe()


@pytest.mark.asyncio
async def test_probe_accepts_complete_rootless_runtime() -> None:
    runner = FakeRunner(
        [
            result(
                stdout=json.dumps(
                    [
                        "name=rootless",
                        "name=apparmor",
                        "name=seccomp,profile=builtin",
                    ]
                ).encode()
            )
        ]
    )
    backend = RootlessDockerBackend(runner=runner)
    await backend.probe()
    assert runner.calls == [
        (
            "/usr/bin/docker",
            "info",
            "--format",
            "{{json .SecurityOptions}}",
        )
    ]


@pytest.mark.asyncio
async def test_default_network_is_none_and_allowlist_needs_controller(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    backend = RootlessDockerBackend(runner=FakeRunner([]))
    assert (await backend.prepare_network(job(workspace))).docker_network == "none"
    allow_policy = SandboxPolicy(
        network_mode=NetworkMode.ALLOW_LIST,
        allowed_destinations=(EgressDestination(host="api.example.com", ports=(443,)),),
    )
    with pytest.raises(SandboxBackendError, match="egress controller"):
        await backend.prepare_network(job(workspace, policy=allow_policy))

    controller = FakeEgress()
    backend = RootlessDockerBackend(runner=FakeRunner([]), egress_controller=controller)
    attachment = await backend.prepare_network(job(workspace, policy=allow_policy))
    assert attachment.docker_network == "zeaz-egress-job"
    assert controller.prepared is not None


@pytest.mark.asyncio
async def test_image_digest_and_implicit_volume_are_verified() -> None:
    security = result(
        stdout=json.dumps(
            ["name=rootless", "name=apparmor", "name=seccomp,profile=builtin"]
        ).encode()
    )
    for metadata, match in (
        (json.dumps(["different@sha256:" + "a" * 64]) + "|null", "approved digest"),
        (json.dumps([IMAGE]) + '|{"/data":{}}', "implicit volumes"),
    ):
        backend = RootlessDockerBackend(
            runner=FakeRunner([security, result(stdout=metadata.encode())])
        )
        await backend.probe()
        with pytest.raises(SandboxBackendError, match=match):
            await backend.verify_image(IMAGE)


@pytest.mark.asyncio
async def test_create_argv_applies_all_isolation_and_resource_limits(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    limits = SandboxLimits(
        timeout_seconds=15,
        cpu_cores=1.5,
        memory_bytes=134_217_728,
        process_count=12,
        file_bytes=1_048_576,
        temporary_bytes=2_097_152,
        output_bytes=4096,
    )
    requested = job(workspace, policy=SandboxPolicy(limits=limits))
    runner = FakeRunner(
        [
            result(
                stdout=json.dumps(
                    ["name=rootless", "name=apparmor", "name=seccomp,profile=builtin"]
                ).encode()
            )
        ]
    )
    backend = RootlessDockerBackend(runner=runner)
    await backend.probe()
    argv = backend.create_argv(
        requested,
        container_name="zeaz-job-abc123",
        attachment=NetworkAttachment(docker_network="none"),
    )
    joined = "\n".join(argv)
    assert argv[:2] == ("/usr/bin/docker", "create")
    assert argv[-4:] == ("/usr/bin/python3", IMAGE, "-c", "print('hello')")
    assert "--entrypoint" in argv
    assert "--read-only" in argv
    assert ("--cap-drop", "ALL") == argv[argv.index("--cap-drop") : argv.index("--cap-drop") + 2]
    assert "no-new-privileges=true" in argv
    assert "seccomp=builtin" in argv
    assert "apparmor=docker-default" in argv
    assert "--pids-limit\n12" in joined
    assert "--cpus\n1.5" in joined
    assert "--memory\n134217728" in joined
    assert "--memory-swap\n134217728" in joined
    assert "fsize=1048576:1048576" in argv
    assert "size=2097152" in joined
    assert f"type=bind,src={workspace},dst=/workspace,readonly" in argv
    assert argv.count("--mount") == 1
    assert "PROVIDER_API_KEY" not in joined
    assert "/bin/sh" not in argv


@pytest.mark.asyncio
async def test_read_write_workspace_and_proxy_are_explicit(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    policy = SandboxPolicy(
        workspace_access=WorkspaceAccess.READ_WRITE,
        network_mode=NetworkMode.ALLOW_LIST,
        allowed_destinations=(EgressDestination(host="api.example.com", ports=(443,)),),
    )
    backend = RootlessDockerBackend(
        runner=FakeRunner(
            [
                result(
                    stdout=json.dumps(
                        ["name=rootless", "name=apparmor", "name=seccomp,profile=builtin"]
                    ).encode()
                )
            ]
        )
    )
    await backend.probe()
    argv = backend.create_argv(
        job(workspace, policy=policy),
        container_name="zeaz-job-rw",
        attachment=NetworkAttachment(
            docker_network="isolated-egress",
            proxy_url="socks5h://proxy:1080",
        ),
    )
    mount = argv[argv.index("--mount") + 1]
    assert mount == f"type=bind,src={workspace},dst=/workspace"
    assert "HTTP_PROXY=socks5h://proxy:1080" in argv
    assert "HTTPS_PROXY=socks5h://proxy:1080" in argv
    assert "ALL_PROXY=socks5h://proxy:1080" in argv


@pytest.mark.asyncio
async def test_create_verifies_local_image_before_container_creation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container_id = b"b" * 64 + b"\n"
    runner = FakeRunner(
        [
            result(
                stdout=json.dumps(
                    ["name=rootless", "name=apparmor", "name=seccomp,profile=builtin"]
                ).encode()
            ),
            result(stdout=(json.dumps([IMAGE]) + "|null\n").encode()),
            result(stdout=container_id),
            result(
                stdout=(
                    json.dumps("docker-default")
                    + "|"
                    + json.dumps(
                        [
                            "no-new-privileges=true",
                            "seccomp=builtin",
                            "apparmor=docker-default",
                        ]
                    )
                ).encode()
            ),
        ]
    )
    backend = RootlessDockerBackend(runner=runner)
    await backend.probe()
    actual = await backend.create(
        job(workspace),
        container_name="zeaz-job-create",
        attachment=NetworkAttachment(docker_network="none"),
    )
    assert actual == "b" * 64
    assert runner.calls[1][1:3] == ("image", "inspect")
    assert runner.calls[2][1] == "create"
    assert runner.calls[3][1] == "inspect"


@pytest.mark.asyncio
async def test_create_removes_container_when_runtime_ignores_apparmor(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container_id = b"c" * 64 + b"\n"
    runner = FakeRunner(
        [
            result(
                stdout=json.dumps(
                    ["name=rootless", "name=apparmor", "name=seccomp,profile=builtin"]
                ).encode()
            ),
            result(stdout=(json.dumps([IMAGE]) + "|null\n").encode()),
            result(stdout=container_id),
            result(
                stdout=(
                    json.dumps("")
                    + "|"
                    + json.dumps(
                        [
                            "no-new-privileges=true",
                            "seccomp=builtin",
                            "apparmor=docker-default",
                        ]
                    )
                ).encode()
            ),
            result(),
        ]
    )
    backend = RootlessDockerBackend(runner=runner)
    await backend.probe()
    with pytest.raises(SandboxBackendError, match="required isolation"):
        await backend.create(
            job(workspace),
            container_name="zeaz-job-unconfined",
            attachment=NetworkAttachment(docker_network="none"),
        )
    assert runner.calls[-1][1:3] == ("rm", "--force")


def test_workspace_root_and_apparmor_profile_are_fail_closed(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(workspace, target_is_directory=True)
    backend = RootlessDockerBackend(runner=FakeRunner([]))
    backend._probed = True
    with pytest.raises(SandboxBackendError, match="real caller-owned"):
        backend.create_argv(
            job(link),
            container_name="zeaz-job-link",
            attachment=NetworkAttachment(docker_network="none"),
        )
    unsupported = SandboxPolicy(apparmor_profile="unapproved")
    with pytest.raises(SandboxBackendError, match="AppArmor"):
        backend.create_argv(
            job(workspace, policy=unsupported),
            container_name="zeaz-job-profile",
            attachment=NetworkAttachment(docker_network="none"),
        )


@pytest.mark.asyncio
async def test_subprocess_runner_bounds_output_and_timeout() -> None:
    runner = SubprocessCommandRunner()
    executable = str(Path(sys.executable).resolve(strict=True))
    with pytest.raises(SandboxBackendError, match="byte limit"):
        await runner.run(
            (executable, "-c", "print('x'*4096)"),
            timeout_seconds=1,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
        )
    with pytest.raises(SandboxBackendError, match="timed out"):
        await runner.run(
            (executable, "-c", "import time;time.sleep(2)"),
            timeout_seconds=0.01,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
        )


def executable_runtime(tmp_path: Path) -> Path:
    runtime = tmp_path / "fake-docker"
    runtime.write_text(
        "#!/usr/bin/python3\n"
        "import sys,time\n"
        "container=sys.argv[-1]\n"
        "if container.startswith('b'):\n"
        " sys.stdout.buffer.write(b'x'*2048);sys.stdout.flush()\n"
        "elif container.startswith('c'):\n"
        " time.sleep(2)\n"
        "else:\n"
        " sys.stdout.buffer.write(b'before secret-value after');sys.stdout.flush()\n"
        " sys.stderr.buffer.write(b'notice');sys.stderr.flush()\n"
    )
    runtime.chmod(0o700)
    return runtime


@pytest.mark.asyncio
async def test_attached_execution_streams_redacted_output(tmp_path: Path) -> None:
    sink = CollectingSink()
    backend = RootlessDockerBackend(
        docker_path=executable_runtime(tmp_path),
        runner=FakeRunner([]),
    )
    backend._probed = True
    streamer = BoundedOutputStreamer(
        sink,
        max_bytes=1024,
        secrets=(b"secret-value",),
    )
    execution = await backend.execute(
        "a" * 64,
        streamer,
        timeout_seconds=2,
    )
    assert execution.reason is ContainerStopReason.EXITED
    assert execution.exit_code == 0
    assert execution.stdout_bytes == len(b"before secret-value after")
    assert b"".join(
        data for channel, data in sink.events if channel is OutputChannel.STDOUT
    ) == b"before [REDACTED] after"
    assert b"".join(
        data for channel, data in sink.events if channel is OutputChannel.STDERR
    ) == b"notice"


@pytest.mark.asyncio
async def test_output_limit_and_cancellation_kill_container(tmp_path: Path) -> None:
    runtime = executable_runtime(tmp_path)
    for container_id, cancel, expected in (
        ("b" * 64, None, ContainerStopReason.OUTPUT_LIMIT),
        ("c" * 64, asyncio.Event(), ContainerStopReason.CANCELLED),
    ):
        if cancel is not None:
            cancel.set()
        runner = FakeRunner([result(stdout=(container_id + "\n").encode())])
        backend = RootlessDockerBackend(docker_path=runtime, runner=runner)
        backend._probed = True
        execution = await backend.execute(
            container_id,
            BoundedOutputStreamer(CollectingSink(), max_bytes=1024),
            timeout_seconds=2,
            cancel_event=cancel,
        )
        assert execution.reason is expected
        assert runner.calls[0][1:3] == ("kill", container_id)
