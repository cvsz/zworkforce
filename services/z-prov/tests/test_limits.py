import pytest

from zeaz_provider.limits import (
    RequestConcurrencyLimiter,
    ResponseLimitExceeded,
    bounded_stream,
)


@pytest.mark.asyncio
async def test_concurrency_limiter_rejects_without_waiting_and_recovers():
    limiter = RequestConcurrencyLimiter(1)
    assert await limiter.try_acquire()
    assert not await limiter.try_acquire()
    assert limiter.active == 1
    await limiter.release()
    assert await limiter.try_acquire()
    await limiter.release()
    assert limiter.active == 0


@pytest.mark.asyncio
async def test_concurrency_limiter_rejects_unbalanced_release():
    limiter = RequestConcurrencyLimiter(1)
    with pytest.raises(RuntimeError, match="without acquisition"):
        await limiter.release()


@pytest.mark.asyncio
async def test_bounded_stream_stops_before_oversized_chunk():
    async def source():
        yield b"1234"
        yield b"5678"

    stream = bounded_stream(source(), 6)
    assert await anext(stream) == b"1234"
    with pytest.raises(ResponseLimitExceeded):
        await anext(stream)
