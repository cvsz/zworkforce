from __future__ import annotations

import pytest

from zeaz_provider.errors import ErrorKind, ProviderError
from zeaz_provider.resilience import CircuitBreaker, ResilienceExecutor, ResiliencePolicy


@pytest.mark.asyncio
async def test_transient_failure_retries_with_deterministic_jitter():
    delays: list[float] = []
    calls = 0

    async def sleep(delay: float) -> None:
        delays.append(delay)

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ProviderError(
                "temporary",
                503,
                retryable=True,
                circuit_failure=True,
            )
        return "ok"

    executor = ResilienceExecutor(
        ResiliencePolicy(max_attempts=3, base_delay_seconds=1, max_delay_seconds=5),
        sleep=sleep,
        uniform=lambda _low, high: high,
    )

    assert await executor.call(operation) == "ok"
    assert calls == 3
    assert delays == [1, 2]


@pytest.mark.asyncio
async def test_retry_after_is_bounded():
    delays: list[float] = []
    calls = 0

    async def sleep(delay: float) -> None:
        delays.append(delay)

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ProviderError(
                "limited",
                429,
                retryable=True,
                kind=ErrorKind.RATE_LIMIT,
                circuit_failure=True,
                retry_after=999,
            )
        return "ok"

    executor = ResilienceExecutor(
        ResiliencePolicy(max_attempts=2, max_retry_after_seconds=7),
        sleep=sleep,
    )
    assert await executor.call(operation) == "ok"
    assert delays == [7]


@pytest.mark.asyncio
async def test_permanent_failure_does_not_retry_or_open_circuit():
    calls = 0
    breaker = CircuitBreaker(failure_threshold=1)

    async def operation() -> str:
        nonlocal calls
        calls += 1
        raise ProviderError(
            "bad request",
            400,
            kind=ErrorKind.BAD_REQUEST,
            fallback_allowed=False,
            circuit_failure=False,
        )

    executor = ResilienceExecutor(ResiliencePolicy(max_attempts=3), breaker=breaker)
    with pytest.raises(ProviderError):
        await executor.call(operation)
    assert calls == 1
    assert breaker.state == "closed"


@pytest.mark.asyncio
async def test_circuit_opens_and_half_open_success_closes_it():
    now = [0.0]
    breaker = CircuitBreaker(
        failure_threshold=1,
        reset_timeout_seconds=10,
        clock=lambda: now[0],
    )
    executor = ResilienceExecutor(
        ResiliencePolicy(max_attempts=1),
        breaker=breaker,
    )

    async def fail() -> str:
        raise ProviderError("down", 503, retryable=True, circuit_failure=True)

    with pytest.raises(ProviderError):
        await executor.call(fail)
    assert breaker.state == "open"

    with pytest.raises(ProviderError) as blocked:
        await executor.call(fail)
    assert blocked.value.kind == ErrorKind.CIRCUIT_OPEN

    now[0] = 11

    async def recover() -> str:
        return "ok"

    assert await executor.call(recover) == "ok"
    assert breaker.state == "closed"


@pytest.mark.asyncio
async def test_total_deadline_stops_retry_before_sleep():
    now = [0.0]
    slept = False

    async def sleep(_delay: float) -> None:
        nonlocal slept
        slept = True

    async def operation() -> str:
        now[0] = 0.9
        raise ProviderError("temporary", 503, retryable=True, circuit_failure=True)

    executor = ResilienceExecutor(
        ResiliencePolicy(
            max_attempts=3,
            base_delay_seconds=1,
            total_timeout_seconds=1,
        ),
        sleep=sleep,
        uniform=lambda _low, high: high,
        clock=lambda: now[0],
    )
    with pytest.raises(ProviderError) as error:
        await executor.call(operation)
    assert error.value.kind == ErrorKind.TIMEOUT
    assert not slept
