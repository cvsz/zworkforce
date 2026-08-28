from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from zeaz_agent import (
    JsonlAuditLog,
    SubagentCompletion,
    SubagentLimitError,
    SubagentLimits,
    SubagentManager,
    SubagentStatus,
    TokenUsage,
)


class ImmediateWorker:
    def __init__(self, usage: int = 1, output: str = "done") -> None:
        self.usage = usage
        self.output = output

    async def run(self, request, cancellation):
        cancellation.raise_if_cancelled()
        return SubagentCompletion(
            output=self.output,
            usage=TokenUsage(input_tokens=self.usage),
        )


class BlockingWorker:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.active = 0
        self.maximum_active = 0

    async def run(self, request, cancellation):
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        self.started.set()
        try:
            await self.release.wait()
            cancellation.raise_if_cancelled()
            return SubagentCompletion(usage=TokenUsage(input_tokens=1))
        finally:
            self.active -= 1


class FailingWorker:
    async def run(self, request, cancellation):
        raise RuntimeError("sensitive worker detail")


@pytest.mark.asyncio
async def test_concurrency_is_bounded() -> None:
    worker = BlockingWorker()
    manager = SubagentManager(SubagentLimits(max_concurrent=2))
    session_id = uuid4()
    handles = [
        await manager.spawn(
            session_id=session_id,
            task=f"task {index}",
            token_budget=10,
            worker=worker,
        )
        for index in range(4)
    ]
    await worker.started.wait()
    await asyncio.sleep(0.02)

    assert worker.maximum_active == 2

    worker.release.set()
    results = await asyncio.gather(*(handle.wait() for handle in handles))
    assert all(result.status is SubagentStatus.COMPLETED for result in results)
    assert worker.maximum_active == 2


@pytest.mark.asyncio
async def test_lifetime_count_limit_is_enforced() -> None:
    manager = SubagentManager(SubagentLimits(max_total=2))
    session_id = uuid4()
    for index in range(2):
        handle = await manager.spawn(
            session_id=session_id,
            task=f"task {index}",
            token_budget=1,
            worker=ImmediateWorker(),
        )
        assert (await handle.wait()).status is SubagentStatus.COMPLETED

    with pytest.raises(SubagentLimitError, match="count"):
        await manager.spawn(
            session_id=session_id,
            task="third",
            token_budget=1,
            worker=ImmediateWorker(),
        )


@pytest.mark.asyncio
async def test_budget_is_reserved_before_launch_and_actual_success_usage_is_charged() -> None:
    manager = SubagentManager(
        SubagentLimits(max_tokens_per_agent=100, max_total_tokens=100)
    )
    session_id = uuid4()
    first = await manager.spawn(
        session_id=session_id,
        task="first",
        token_budget=60,
        worker=ImmediateWorker(usage=10),
    )
    await first.wait()

    assert await manager.usage() == (1, 10, 0)

    second = await manager.spawn(
        session_id=session_id,
        task="second",
        token_budget=90,
        worker=ImmediateWorker(usage=5),
    )
    await second.wait()
    assert await manager.usage() == (2, 15, 0)


@pytest.mark.asyncio
async def test_active_reservations_prevent_budget_overcommit() -> None:
    worker = BlockingWorker()
    manager = SubagentManager(
        SubagentLimits(max_tokens_per_agent=100, max_total_tokens=100)
    )
    session_id = uuid4()
    first = await manager.spawn(
        session_id=session_id,
        task="first",
        token_budget=60,
        worker=worker,
    )

    with pytest.raises(SubagentLimitError, match="aggregate"):
        await manager.spawn(
            session_id=session_id,
            task="overcommit",
            token_budget=41,
            worker=ImmediateWorker(),
        )

    worker.release.set()
    await first.wait()


@pytest.mark.asyncio
async def test_depth_is_manager_derived_and_cross_session_parent_is_rejected() -> None:
    worker = BlockingWorker()
    manager = SubagentManager(SubagentLimits(max_concurrent=3, max_depth=2))
    session_id = uuid4()
    parent = await manager.spawn(
        session_id=session_id,
        task="parent",
        token_budget=10,
        worker=worker,
    )
    child = await manager.spawn(
        session_id=session_id,
        parent_id=parent.request.id,
        task="child",
        token_budget=10,
        worker=worker,
    )

    assert parent.request.depth == 1
    assert child.request.depth == 2
    with pytest.raises(SubagentLimitError, match="depth"):
        await manager.spawn(
            session_id=session_id,
            parent_id=child.request.id,
            task="grandchild",
            token_budget=10,
            worker=worker,
        )
    with pytest.raises(SubagentLimitError, match="another session"):
        await manager.spawn(
            session_id=uuid4(),
            parent_id=parent.request.id,
            task="foreign child",
            token_budget=10,
            worker=worker,
        )

    worker.release.set()
    await asyncio.gather(parent.wait(), child.wait())


@pytest.mark.asyncio
async def test_parent_cancellation_propagates_to_descendants() -> None:
    worker = BlockingWorker()
    manager = SubagentManager(SubagentLimits(max_concurrent=3))
    session_id = uuid4()
    parent = await manager.spawn(
        session_id=session_id,
        task="parent",
        token_budget=10,
        worker=worker,
    )
    child = await manager.spawn(
        session_id=session_id,
        parent_id=parent.request.id,
        task="child",
        token_budget=10,
        worker=worker,
    )

    await parent.cancel()
    parent_result, child_result = await asyncio.gather(parent.wait(), child.wait())

    assert parent_result.status is SubagentStatus.CANCELLED
    assert child_result.status is SubagentStatus.CANCELLED
    assert await manager.usage() == (2, 20, 0)


@pytest.mark.asyncio
async def test_timeout_failure_and_excess_usage_are_sanitized_and_charged() -> None:
    limits = SubagentLimits(
        max_total=3,
        max_tokens_per_agent=10,
        max_total_tokens=30,
        timeout_seconds=0.01,
    )
    manager = SubagentManager(limits)
    session_id = uuid4()

    timeout_worker = BlockingWorker()
    timed = await manager.spawn(
        session_id=session_id,
        task="timeout",
        token_budget=10,
        worker=timeout_worker,
    )
    failed = await manager.spawn(
        session_id=session_id,
        task="fail",
        token_budget=10,
        worker=FailingWorker(),
    )
    excessive = await manager.spawn(
        session_id=session_id,
        task="excess",
        token_budget=10,
        worker=ImmediateWorker(usage=11),
    )

    results = await asyncio.gather(timed.wait(), failed.wait(), excessive.wait())

    assert [result.status for result in results] == [
        SubagentStatus.TIMED_OUT,
        SubagentStatus.FAILED,
        SubagentStatus.FAILED,
    ]
    assert results[1].error_code == "worker_failed"
    assert "sensitive" not in results[1].model_dump_json()
    assert results[2].error_code == "token_budget_exceeded"
    assert await manager.usage() == (3, 30, 0)


@pytest.mark.asyncio
async def test_audit_events_do_not_persist_task_or_output(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    manager = SubagentManager(audit=JsonlAuditLog(path))
    handle = await manager.spawn(
        session_id=uuid4(),
        task="secret task text",
        token_budget=10,
        worker=ImmediateWorker(output="secret output text"),
    )
    await handle.wait()

    raw = path.read_text(encoding="utf-8")
    assert "secret task text" not in raw
    assert "secret output text" not in raw
    assert [entry.event.event_type for entry in JsonlAuditLog(path).verify()] == [
        "subagent.spawned",
        "subagent.started",
        "subagent.completed",
    ]
