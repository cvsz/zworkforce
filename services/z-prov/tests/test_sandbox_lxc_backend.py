import sys
from pathlib import Path
from uuid import UUID

import pytest
from zeaz_sandbox.backend import CommandResult, NetworkAttachment, SandboxBackendError
from zeaz_sandbox.lxc_backend import RootlessLxcBackend
from zeaz_sandbox.schemas import (
    EgressDestination,
    JobSpec,
    NetworkMode,
    SandboxLimits,
    SandboxPolicy,
)
from zeaz_sandbox.streaming import BoundedOutputStreamer, OutputChannel

IMAGE = "registry.example/worker@sha256:" + "a" * 64


class FakeRunner:
    def __init__(self, results: list[CommandResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, ...]] = []

    async def run(self, argv, **_) -> CommandResult:
        self.calls.append(tuple(argv))
        return self.results.pop(0)


def result(stdout: bytes = b"", returncode: int = 0) -> CommandResult:
    return CommandResult(returncode=returncode, stdout=stdout, stderr=b"")


def job(workspace: Path, **changes) -> JobSpec:
    values = {
        "session_id": UUID("00000000-0000-0000-0000-000000000001"),
        "correlation_id": UUID("00000000-0000-0000-0000-000000000002"),
        "image": IMAGE,
        "command": ("/usr/bin/python3", "-c", "print('hello')"),
        "workspace": workspace,
        "policy": SandboxPolicy(
            apparmor_profile="lxc-container-default-cgns",
            limits=SandboxLimits(
                cpu_cores=0.5,
                memory_bytes=67_108_864,
                process_count=32,
                file_bytes=1_048_576,
                temporary_bytes=8_388_608,
            )
        ),
    }
    values.update(changes)
    return JobSpec(**values)


def backend(
    tmp_path: Path,
    runner: FakeRunner,
) -> RootlessLxcBackend:
    rootfs = tmp_path / "rootfs"
    rootfs.mkdir(mode=0o755)
    commands = {
        name: Path(sys.executable).resolve()
        for name in ("start", "stop", "attach", "info")
    }
    return RootlessLxcBackend(
        state_root=tmp_path / "state",
        image_roots={IMAGE: rootfs},
        runner=runner,
        command_paths=commands,
    )


@pytest.mark.asyncio
async def test_lxc_create_writes_bounded_isolation_config(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    runner = FakeRunner(
        [
            result(b"6.0.6\n"),
            result(),
            result(b"RUNNING\n"),
            result(b"lxc-container-default-cgns (enforce)\n"),
            result(b"Name:\ttest\nCapEff:\t0000000000000000\n"),
            result(b"32\n"),
            result(b"67108864\n"),
        ]
    )
    runtime = backend(tmp_path, runner)
    await runtime.probe()
    name = await runtime.create(
        job(workspace),
        container_name="zeaz-job-safe",
        attachment=NetworkAttachment(docker_network="none"),
    )
    assert name == "zeaz-job-safe"
    config = (tmp_path / "state" / name / "config").read_text()
    assert "lxc.net.0.type = empty" in config
    assert "lxc.apparmor.profile = lxc-container-default-cgns" in config
    assert "lxc.cap.keep = none" in config
    assert "lxc.cgroup2.pids.max = 32" in config
    assert "lxc.cgroup2.memory.max = 67108864" in config
    assert "lxc.cgroup2.cpu.max = 50000 100000" in config
    assert f"lxc.mount.entry = {workspace} workspace none bind,create=dir,ro" in config
    assert "size=8388608" in config
    assert "/bin/sh -c" not in config


@pytest.mark.asyncio
async def test_lxc_rejects_confinement_downgrade_and_cleans_definition(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    runner = FakeRunner(
        [
            result(b"6.0.6\n"),
            result(),
            result(b"RUNNING\n"),
            result(b"unconfined\n"),
            result(b"Name:\ttest\nCapEff:\t0000000000000000\n"),
            result(b"32\n"),
            result(b"67108864\n"),
            result(b"RUNNING\n"),
            result(),
            result(b"STOPPED\n"),
        ]
    )
    runtime = backend(tmp_path, runner)
    await runtime.probe()
    with pytest.raises(SandboxBackendError, match="required isolation"):
        await runtime.create(
            job(workspace),
            container_name="zeaz-job-downgraded",
            attachment=NetworkAttachment(docker_network="none"),
        )
    assert not (tmp_path / "state" / "zeaz-job-downgraded").exists()
    assert any("lxc-stop" in call or "--kill" in call for call in runner.calls)


@pytest.mark.asyncio
async def test_lxc_allows_only_network_disabled_jobs(tmp_path: Path) -> None:
    runner = FakeRunner([])
    runtime = backend(tmp_path, runner)
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    assert (await runtime.prepare_network(job(workspace))).docker_network == "none"
    policy = SandboxPolicy(
        network_mode=NetworkMode.ALLOW_LIST,
        allowed_destinations=(
            EgressDestination(host="api.example.com", ports=(443,)),
        ),
    )
    with pytest.raises(SandboxBackendError, match="network-disabled"):
        await runtime.prepare_network(job(workspace, policy=policy))


def test_lxc_rejects_untrusted_rootfs_and_state_permissions(tmp_path: Path) -> None:
    rootfs = tmp_path / "rootfs"
    rootfs.mkdir()
    rootfs.chmod(0o755)
    rootfs.chmod(0o777)
    commands = {
        name: Path(sys.executable).resolve()
        for name in ("start", "stop", "attach", "info")
    }
    with pytest.raises(ValueError, match="rootfs"):
        RootlessLxcBackend(
            state_root=tmp_path / "state",
            image_roots={IMAGE: rootfs},
            command_paths=commands,
        )


class CollectingSink:
    def __init__(self) -> None:
        self.events: list[tuple[OutputChannel, bytes]] = []

    async def emit(self, channel: OutputChannel, data: bytes) -> None:
        self.events.append((channel, data))


@pytest.mark.asyncio
async def test_lxc_execute_uses_exact_argv_with_clean_environment(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "fake-lxc-attach"
    executable.write_text(
        "#!/usr/bin/python3\n"
        "import os,sys\n"
        "index=sys.argv.index('--')\n"
        "os.execv(sys.argv[index+1],sys.argv[index+1:])\n"
    )
    executable.chmod(0o700)
    rootfs = tmp_path / "rootfs"
    rootfs.mkdir()
    rootfs.chmod(0o755)
    commands = {
        name: executable
        for name in ("start", "stop", "attach", "info")
    }
    runtime = RootlessLxcBackend(
        state_root=tmp_path / "state",
        image_roots={IMAGE: rootfs},
        runner=FakeRunner([]),
        command_paths=commands,
    )
    runtime._probed = True
    runtime._commands["zeaz-job-execute"] = (
        str(Path(sys.executable).resolve()),
        "-c",
        "import os;print(os.getenv('HOME'));print('ok')",
    )
    sink = CollectingSink()
    streamer = BoundedOutputStreamer(sink, max_bytes=4096)
    execution = await runtime.execute(
        "zeaz-job-execute",
        streamer,
        timeout_seconds=5,
    )
    assert execution.exit_code == 0
    assert b"ok" in b"".join(data for _, data in sink.events)
