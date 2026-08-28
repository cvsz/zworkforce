import pytest
from zeaz_sandbox.streaming import (
    BoundedOutputStreamer,
    OutputChannel,
)


class CollectingSink:
    def __init__(self) -> None:
        self.events: list[tuple[OutputChannel, bytes]] = []

    async def emit(self, channel: OutputChannel, data: bytes) -> None:
        self.events.append((channel, data))

    def content(self, channel: OutputChannel) -> bytes:
        return b"".join(data for actual, data in self.events if actual is channel)


@pytest.mark.asyncio
async def test_streams_channels_and_counts_raw_bytes() -> None:
    sink = CollectingSink()
    streamer = BoundedOutputStreamer(sink, max_bytes=1024)
    assert await streamer.feed(OutputChannel.STDOUT, b"hello")
    assert await streamer.feed(OutputChannel.STDERR, b"warning")
    await streamer.finish()
    assert sink.content(OutputChannel.STDOUT) == b"hello"
    assert sink.content(OutputChannel.STDERR) == b"warning"
    assert streamer.stdout_bytes == 5
    assert streamer.stderr_bytes == 7
    assert not streamer.truncated


@pytest.mark.asyncio
async def test_redacts_secrets_split_across_arbitrary_chunks() -> None:
    sink = CollectingSink()
    streamer = BoundedOutputStreamer(
        sink,
        max_bytes=1024,
        secrets=(b"provider-secret-value", b"short-secret"),
    )
    for chunk in (b"before provider-", b"secret-", b"value after short-", b"secret!"):
        assert await streamer.feed(OutputChannel.STDOUT, chunk)
    await streamer.finish()
    output = sink.content(OutputChannel.STDOUT)
    assert output == b"before [REDACTED] after [REDACTED]!"
    assert b"provider-secret-value" not in output
    assert b"short-secret" not in output


@pytest.mark.asyncio
async def test_channels_cannot_complete_each_others_secret() -> None:
    sink = CollectingSink()
    streamer = BoundedOutputStreamer(
        sink,
        max_bytes=1024,
        secrets=(b"abcdefgh",),
    )
    await streamer.feed(OutputChannel.STDOUT, b"abcd")
    await streamer.feed(OutputChannel.STDERR, b"efgh")
    await streamer.finish()
    assert sink.content(OutputChannel.STDOUT) == b"abcd"
    assert sink.content(OutputChannel.STDERR) == b"efgh"


@pytest.mark.asyncio
async def test_shared_output_limit_truncates_and_stops_accepting() -> None:
    sink = CollectingSink()
    streamer = BoundedOutputStreamer(sink, max_bytes=1024)
    assert await streamer.feed(OutputChannel.STDOUT, b"a" * 1000)
    assert not await streamer.feed(OutputChannel.STDERR, b"b" * 100)
    assert not await streamer.feed(OutputChannel.STDOUT, b"ignored")
    await streamer.finish()
    assert streamer.stdout_bytes == 1000
    assert streamer.stderr_bytes == 24
    assert len(sink.content(OutputChannel.STDOUT)) == 1000
    assert len(sink.content(OutputChannel.STDERR)) == 24
    assert streamer.truncated


@pytest.mark.asyncio
async def test_finish_flushes_secret_prefix_without_dropping_bytes() -> None:
    sink = CollectingSink()
    streamer = BoundedOutputStreamer(
        sink,
        max_bytes=1024,
        secrets=(b"complete-secret",),
    )
    await streamer.feed(OutputChannel.STDOUT, b"complete")
    assert sink.content(OutputChannel.STDOUT) == b""
    await streamer.finish()
    assert sink.content(OutputChannel.STDOUT) == b"complete"


def test_redaction_configuration_is_bounded() -> None:
    sink = CollectingSink()
    with pytest.raises(ValueError):
        BoundedOutputStreamer(sink, max_bytes=1024, secrets=(b"abc",))
    with pytest.raises(ValueError):
        BoundedOutputStreamer(
            sink,
            max_bytes=1024,
            secrets=tuple(str(index).encode().ljust(4, b"x") for index in range(129)),
        )
