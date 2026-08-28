import asyncio
from uuid import UUID

import pytest
from pydantic import ValidationError
from zeaz_agent.hooks import (
    HookContext,
    HookDecision,
    HookDenied,
    HookFailurePolicy,
    HookPhase,
    HookVerdict,
    ToolHook,
    ToolHookRunner,
)
from zeaz_agent.schemas import ToolCall

SESSION_ID = UUID("00000000-0000-0000-0000-000000000001")
CORRELATION_ID = UUID("00000000-0000-0000-0000-000000000002")


def call(arguments=None) -> ToolCall:
    return ToolCall(id="call-1", name="workspace.read", arguments=arguments or {"path": "a"})


@pytest.mark.asyncio
async def test_pre_hooks_run_in_order_over_same_immutable_snapshot() -> None:
    observed: list[tuple[str, bytes, str]] = []

    async def first(context: HookContext) -> HookDecision:
        decoded = context.input_value()
        decoded["path"] = "mutated"
        observed.append(("first", context.input_json, context.input_sha256))
        return HookDecision(verdict=HookVerdict.ALLOW, reason_code="safe")

    async def second(context: HookContext) -> HookDecision:
        observed.append(("second", context.input_json, context.input_sha256))
        assert context.input_value() == {"path": "a"}
        return HookDecision(verdict=HookVerdict.ALLOW, reason_code="safe")

    runner = ToolHookRunner(
        (
            ToolHook(
                name="first",
                phase=HookPhase.PRE_TOOL,
                timeout_seconds=1,
                callback=first,
            ),
            ToolHook(
                name="second",
                phase=HookPhase.PRE_TOOL,
                timeout_seconds=1,
                callback=second,
            ),
        )
    )
    outcomes = await runner.run_pre(
        call(),
        session_id=SESSION_ID,
        correlation_id=CORRELATION_ID,
    )
    assert [outcome.name for outcome in outcomes] == ["first", "second"]
    assert observed[0][1:] == observed[1][1:]


@pytest.mark.asyncio
async def test_explicit_deny_stops_later_hooks() -> None:
    later_called = False

    async def deny(_: HookContext) -> HookDecision:
        return HookDecision(verdict=HookVerdict.DENY, reason_code="blocked_path")

    async def later(_: HookContext) -> HookDecision:
        nonlocal later_called
        later_called = True
        return HookDecision(verdict=HookVerdict.ALLOW)

    runner = ToolHookRunner(
        (
            ToolHook(name="deny", phase=HookPhase.PRE_TOOL, timeout_seconds=1, callback=deny),
            ToolHook(name="later", phase=HookPhase.PRE_TOOL, timeout_seconds=1, callback=later),
        )
    )
    with pytest.raises(HookDenied, match="blocked_path") as raised:
        await runner.run_pre(call(), session_id=SESSION_ID, correlation_id=CORRELATION_ID)
    assert raised.value.outcome.failed is False
    assert later_called is False


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["raise", "invalid", "timeout"])
async def test_fail_closed_hook_errors_deny(failure: str) -> None:
    async def broken(_: HookContext):
        if failure == "raise":
            raise RuntimeError("private detail")
        if failure == "timeout":
            await asyncio.sleep(0.05)
        return "not-a-decision"

    runner = ToolHookRunner(
        (
            ToolHook(
                name="broken",
                phase=HookPhase.PRE_TOOL,
                timeout_seconds=0.01,
                callback=broken,
            ),
        )
    )
    with pytest.raises(HookDenied) as raised:
        await runner.run_pre(call(), session_id=SESSION_ID, correlation_id=CORRELATION_ID)
    assert raised.value.outcome.failed is True
    assert ("private detail" not in str(raised.value))
    assert raised.value.outcome.timed_out is (failure == "timeout")


@pytest.mark.asyncio
async def test_fail_open_is_explicit_and_records_failure() -> None:
    async def broken(_: HookContext) -> HookDecision:
        raise RuntimeError("ignored")

    runner = ToolHookRunner(
        (
            ToolHook(
                name="advisory",
                phase=HookPhase.PRE_TOOL,
                timeout_seconds=1,
                failure_policy=HookFailurePolicy.FAIL_OPEN,
                callback=broken,
            ),
        )
    )
    outcomes = await runner.run_pre(
        call(),
        session_id=SESSION_ID,
        correlation_id=CORRELATION_ID,
    )
    assert outcomes[0].verdict is HookVerdict.ALLOW
    assert outcomes[0].failed is True
    assert outcomes[0].reason_code == "hook_failure"


@pytest.mark.asyncio
async def test_post_hook_receives_output_snapshot_only_after_tool() -> None:
    observed: HookContext | None = None

    async def post(context: HookContext) -> HookDecision:
        nonlocal observed
        observed = context
        return HookDecision(verdict=HookVerdict.ALLOW)

    runner = ToolHookRunner(
        (
            ToolHook(
                name="post",
                phase=HookPhase.POST_TOOL,
                timeout_seconds=1,
                callback=post,
            ),
        )
    )
    assert await runner.run_pre(
        call(),
        session_id=SESSION_ID,
        correlation_id=CORRELATION_ID,
    ) == ()
    outcomes = await runner.run_post(
        call(),
        {"content": "done"},
        session_id=SESSION_ID,
        correlation_id=CORRELATION_ID,
    )
    assert outcomes[0].phase is HookPhase.POST_TOOL
    assert observed is not None
    assert observed.output_value() == {"content": "done"}
    assert observed.output_sha256 is not None


@pytest.mark.asyncio
async def test_snapshot_is_taken_before_hook_can_observe_caller_mutation() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    original = {"nested": {"value": "original"}}

    async def inspect(context: HookContext) -> HookDecision:
        started.set()
        await release.wait()
        assert context.input_value() == {"nested": {"value": "original"}}
        return HookDecision(verdict=HookVerdict.ALLOW)

    runner = ToolHookRunner(
        (ToolHook(name="inspect", phase=HookPhase.PRE_TOOL, timeout_seconds=1, callback=inspect),)
    )
    task = asyncio.create_task(
        runner.run_pre(
            call(original),
            session_id=SESSION_ID,
            correlation_id=CORRELATION_ID,
        )
    )
    await started.wait()
    original["nested"]["value"] = "changed"
    release.set()
    await task


@pytest.mark.asyncio
async def test_cancellation_propagates_instead_of_using_failure_policy() -> None:
    started = asyncio.Event()

    async def waiting(_: HookContext) -> HookDecision:
        started.set()
        await asyncio.Event().wait()
        return HookDecision(verdict=HookVerdict.ALLOW)

    runner = ToolHookRunner(
        (
            ToolHook(
                name="waiting",
                phase=HookPhase.PRE_TOOL,
                timeout_seconds=10,
                failure_policy=HookFailurePolicy.FAIL_OPEN,
                callback=waiting,
            ),
        )
    )
    task = asyncio.create_task(
        runner.run_pre(call(), session_id=SESSION_ID, correlation_id=CORRELATION_ID)
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_hook_configuration_and_snapshot_bounds() -> None:
    async def allow(_: HookContext) -> HookDecision:
        return HookDecision(verdict=HookVerdict.ALLOW)

    duplicate = ToolHook(
        name="same",
        phase=HookPhase.PRE_TOOL,
        timeout_seconds=1,
        callback=allow,
    )
    with pytest.raises(ValueError, match="unique"):
        ToolHookRunner((duplicate, duplicate))
    with pytest.raises(ValidationError):
        ToolHook(name="bad name", phase=HookPhase.PRE_TOOL, timeout_seconds=1, callback=allow)


@pytest.mark.asyncio
async def test_snapshot_size_limit_rejects_before_hook() -> None:
    called = False

    async def hook(_: HookContext) -> HookDecision:
        nonlocal called
        called = True
        return HookDecision(verdict=HookVerdict.ALLOW)

    runner = ToolHookRunner(
        (ToolHook(name="bounded", phase=HookPhase.PRE_TOOL, timeout_seconds=1, callback=hook),),
        max_snapshot_bytes=1024,
    )
    with pytest.raises(ValueError, match="byte limit"):
        await runner.run_pre(
            call({"value": "x" * 2048}),
            session_id=SESSION_ID,
            correlation_id=CORRELATION_ID,
        )
    assert called is False
