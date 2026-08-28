import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from zeaz_sandbox.backend import (
    ContainerExecutionResult,
    ContainerStopReason,
    NetworkAttachment,
    SandboxBackendError,
)
from zeaz_sandbox.schemas import (
    ExecutionState,
    JobRequest,
    JobSpec,
    approve_job,
)
from zeaz_sandbox.service import (
    ActiveExecution,
    SandboxService,
    SandboxServiceError,
    SQLiteSandboxStore,
)
from zeaz_sandbox.streaming import OutputChannel

SESSION_ID = UUID("00000000-0000-0000-0000-000000000001")
CORRELATION_ID = UUID("00000000-0000-0000-0000-000000000002")
PERMISSION_ID = UUID("00000000-0000-0000-0000-000000000003")
NOW = datetime(2026, 7, 26, tzinfo=UTC)
IMAGE = "registry.example/worker@sha256:" + "a" * 64
CONTAINER_ID = "b" * 64


class CollectingSink:
    def __init__(self) -> None:
        self.events: list[tuple[OutputChannel, bytes]] = []

    async def emit(self, channel: OutputChannel, data: bytes) -> None:
        self.events.append((channel, data))


class FakeBackend:
    def __init__(
        self,
        execution: ContainerExecutionResult | None = None,
    ) -> None:
        self.execution = execution or ContainerExecutionResult(
            reason=ContainerStopReason.EXITED,
            exit_code=0,
            stdout_bytes=0,
            stderr_bytes=0,
            output_truncated=False,
        )
        self.probed = False
        self.created = 0
        self.removed: list[str] = []
        self.network_cleanups: list[NetworkAttachment] = []
        self.managed: tuple[str, ...] = ()
        self.fail_create = False
        self.fail_remove = False
        self.fail_network_cleanup = False
        self.started = asyncio.Event()
        self.wait_for_cancel = False

    async def probe(self) -> None:
        self.probed = True

    async def prepare_network(self, job) -> NetworkAttachment:
        del job
        return NetworkAttachment(docker_network="none")

    async def create(self, job, **_) -> str:
        del job
        if self.fail_create:
            raise SandboxBackendError("private runtime detail")
        self.created += 1
        return CONTAINER_ID

    async def execute(
        self,
        container_id,
        streamer,
        *,
        timeout_seconds,
        cancel_event,
    ) -> ContainerExecutionResult:
        del container_id, timeout_seconds
        self.started.set()
        await streamer.feed(
            OutputChannel.STDOUT,
            b"before provider-secret-value after",
        )
        if self.wait_for_cancel:
            await cancel_event.wait()
            await streamer.finish()
            return ContainerExecutionResult(
                reason=ContainerStopReason.CANCELLED,
                stdout_bytes=35,
                stderr_bytes=0,
                output_truncated=False,
            )
        await streamer.finish()
        return self.execution.model_copy(
            update={
                "stdout_bytes": streamer.stdout_bytes,
                "stderr_bytes": streamer.stderr_bytes,
                "output_truncated": streamer.truncated,
            }
        )

    async def remove(self, container_id: str) -> None:
        if self.fail_remove:
            raise SandboxBackendError("remove failed")
        self.removed.append(container_id)

    async def managed_containers(self) -> tuple[str, ...]:
        return self.managed

    async def cleanup_network(self, attachment: NetworkAttachment) -> None:
        if self.fail_network_cleanup:
            raise SandboxBackendError("network cleanup failed")
        self.network_cleanups.append(attachment)


def request(workspace: Path, *, approval_time: datetime = NOW) -> JobRequest:
    spec = JobSpec(
        session_id=SESSION_ID,
        correlation_id=CORRELATION_ID,
        image=IMAGE,
        command=("/usr/bin/true",),
        workspace=workspace,
    )
    return JobRequest(
        spec=spec,
        approval=approve_job(
            spec,
            approved_by="user:test",
            permission_decision_id=PERMISSION_ID,
            now=approval_time,
            lifetime_seconds=60,
        ),
    )


def store(tmp_path: Path) -> SQLiteSandboxStore:
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    return SQLiteSandboxStore(state / "sandbox.sqlite3")


@pytest.mark.asyncio
async def test_success_requires_probe_streams_redacted_output_and_persists_receipt(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    backend = FakeBackend()
    receipt_store = store(tmp_path)
    service = SandboxService(backend, receipt_store)
    with pytest.raises(SandboxServiceError, match="probe"):
        await service.execute(request(workspace), now=NOW)
    await service.start()
    sink = CollectingSink()
    receipt = await service.execute(
        request(workspace),
        sink=sink,
        redaction_secrets=(b"provider-secret-value",),
        now=NOW,
    )
    assert receipt.state is ExecutionState.COMPLETED
    assert receipt.exit_code == 0
    assert receipt.cleanup_complete
    assert receipt.image_digest == "sha256:" + "a" * 64
    assert receipt_store.receipt(receipt.job_id) == receipt
    assert receipt_store.active() == ()
    assert backend.removed == [CONTAINER_ID]
    assert b"".join(data for _, data in sink.events) == b"before [REDACTED] after"


@pytest.mark.asyncio
async def test_expired_approval_is_rejected_with_receipt_before_backend(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    backend = FakeBackend()
    receipt_store = store(tmp_path)
    service = SandboxService(backend, receipt_store)
    await service.start()
    submitted = request(workspace)
    receipt = await service.execute(
        submitted,
        now=NOW + timedelta(seconds=60),
    )
    assert receipt.state is ExecutionState.REJECTED
    assert receipt.failure_code == "approval_invalid"
    assert receipt.started_at is None
    assert backend.created == 0
    assert receipt_store.receipt(submitted.spec.id) == receipt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "execution,state,failure,exit_code",
    (
        (
            ContainerExecutionResult(
                reason=ContainerStopReason.EXITED,
                exit_code=7,
                stdout_bytes=0,
                stderr_bytes=0,
                output_truncated=False,
            ),
            ExecutionState.FAILED,
            "nonzero_exit",
            7,
        ),
        (
            ContainerExecutionResult(
                reason=ContainerStopReason.TIMED_OUT,
                stdout_bytes=0,
                stderr_bytes=0,
                output_truncated=False,
            ),
            ExecutionState.FAILED,
            "timeout",
            None,
        ),
        (
            ContainerExecutionResult(
                reason=ContainerStopReason.OUTPUT_LIMIT,
                stdout_bytes=1024,
                stderr_bytes=0,
                output_truncated=True,
            ),
            ExecutionState.FAILED,
            "output_limit",
            None,
        ),
    ),
)
async def test_runtime_terminal_states_always_generate_receipts(
    tmp_path: Path,
    execution: ContainerExecutionResult,
    state: ExecutionState,
    failure: str,
    exit_code: int | None,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    service = SandboxService(FakeBackend(execution), store(tmp_path))
    await service.start()
    receipt = await service.execute(request(workspace), now=NOW)
    assert receipt.state is state
    assert receipt.failure_code == failure
    assert receipt.exit_code == exit_code


@pytest.mark.asyncio
async def test_live_cancellation_produces_cancelled_receipt(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    backend = FakeBackend()
    backend.wait_for_cancel = True
    receipt_store = store(tmp_path)
    service = SandboxService(backend, receipt_store)
    await service.start()
    submitted = request(workspace)
    task = asyncio.create_task(service.execute(submitted, now=NOW))
    await backend.started.wait()
    assert await service.cancel(submitted.spec.id)
    receipt = await task
    assert receipt.state is ExecutionState.CANCELLED
    assert receipt.failure_code == "cancelled"
    assert receipt_store.receipt(submitted.spec.id) == receipt
    assert not await service.cancel(submitted.spec.id)


@pytest.mark.asyncio
async def test_failed_cleanup_stays_journaled_until_reconciliation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    backend = FakeBackend()
    backend.fail_remove = True
    backend.managed = (CONTAINER_ID,)
    receipt_store = store(tmp_path)
    service = SandboxService(backend, receipt_store)
    await service.start()
    receipt = await service.execute(request(workspace), now=NOW)
    assert receipt.state is ExecutionState.FAILED
    assert receipt.failure_code == "cleanup_failure"
    assert not receipt.cleanup_complete
    assert receipt_store.active()[0].container_id == CONTAINER_ID

    backend.fail_remove = False
    result = await service.reconcile()
    assert result.cleaned == 1
    assert result.failed == 0
    assert receipt_store.active() == ()


@pytest.mark.asyncio
async def test_failed_create_network_lease_is_reconciled_without_container(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    backend = FakeBackend()
    backend.fail_create = True
    backend.fail_network_cleanup = True
    receipt_store = store(tmp_path)
    service = SandboxService(backend, receipt_store)
    await service.start()
    receipt = await service.execute(request(workspace), now=NOW)
    assert receipt.failure_code == "backend_failure"
    assert not receipt.cleanup_complete
    assert receipt_store.active()[0].container_id is None

    backend.fail_network_cleanup = False
    result = await service.reconcile()
    assert result.cleaned == 1
    assert receipt_store.active() == ()


@pytest.mark.asyncio
async def test_caller_task_cancellation_is_cleaned_and_receipted(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    backend = FakeBackend()
    backend.wait_for_cancel = True
    receipt_store = store(tmp_path)
    service = SandboxService(backend, receipt_store)
    await service.start()
    submitted = request(workspace)
    task = asyncio.create_task(service.execute(submitted, now=NOW))
    await backend.started.wait()
    task.cancel()
    receipt = await task
    assert receipt.state is ExecutionState.CANCELLED
    assert receipt.cleanup_complete
    assert receipt_store.receipt(submitted.spec.id) == receipt


@pytest.mark.asyncio
async def test_reconciliation_removes_unjournaled_managed_orphan(tmp_path: Path) -> None:
    backend = FakeBackend()
    backend.managed = (CONTAINER_ID,)
    service = SandboxService(backend, store(tmp_path))
    await service.start()
    result = await service.reconcile()
    assert result.inspected == 1
    assert result.cleaned == 1
    assert backend.removed == [CONTAINER_ID]


def test_store_rejects_symlink_and_nonprivate_parent(tmp_path: Path) -> None:
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    target = private / "target"
    target.write_bytes(b"")
    link = private / "linked"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="private regular"):
        SQLiteSandboxStore(link)

    public = tmp_path / "public"
    public.mkdir(mode=0o755)
    with pytest.raises(ValueError, match="private"):
        SQLiteSandboxStore(public / "state.sqlite3")


def test_store_rejects_malformed_persisted_active_record(tmp_path: Path) -> None:
    receipt_store = store(tmp_path)
    receipt_store.record_active(
        ActiveExecution(
            job_id=SESSION_ID,
            container_id=CONTAINER_ID,
            attachment=NetworkAttachment(docker_network="none"),
        )
    )
    with receipt_store._connect() as connection:
        connection.execute(
            "UPDATE active_executions SET attachment_json = ?",
            (b"not-json",),
        )
        connection.commit()
    with pytest.raises(SandboxServiceError, match="stored active"):
        receipt_store.active()
