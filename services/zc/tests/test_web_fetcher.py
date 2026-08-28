from __future__ import annotations

import email.message
import io
import socket
import urllib.error
import urllib.request

import pytest

from wire.web_fetcher import SafeWebFetcher, UnsafeWebFetchError, WebFetchLimitError


def _resolver_for(address: str):
    def resolve(host: str, port: int, *, type: int):
        assert host
        assert port
        assert type == socket.SOCK_STREAM
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (address, port))]

    return resolve


class _Response(io.BytesIO):
    def __init__(
        self,
        body: bytes,
        *,
        url: str = "https://example.com/article",
        content_type: str = "text/plain; charset=utf-8",
    ) -> None:
        super().__init__(body)
        self._url = url
        self.read_sizes: list[int] = []
        self.headers = email.message.Message()
        self.headers["Content-Type"] = content_type

    def geturl(self) -> str:
        return self._url

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        return super().read(size)


class _Opener:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.requests: list[urllib.request.Request] = []

    def open(self, request: urllib.request.Request, *, timeout: float):
        self.requests.append(request)
        outcome = next(self.outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _redirect(url: str, location: str) -> urllib.error.HTTPError:
    headers = email.message.Message()
    headers["Location"] = location
    return urllib.error.HTTPError(url, 302, "Found", headers, io.BytesIO())


@pytest.mark.parametrize(
    "url,address",
    [
        ("http://127.0.0.1/admin", "127.0.0.1"),
        ("http://169.254.169.254/latest/meta-data", "169.254.169.254"),
        ("http://example.test/private", "10.0.0.8"),
        ("http://[::1]/", "::1"),
        ("http://[::ffff:127.0.0.1]/", "::ffff:127.0.0.1"),
    ],
)
def test_rejects_non_public_destinations(url: str, address: str) -> None:
    fetcher = SafeWebFetcher(resolver=_resolver_for(address), opener=_Opener([]))

    with pytest.raises(UnsafeWebFetchError, match="non-public"):
        fetcher.fetch(url)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "https://user:password@example.com/",
        "https://example.com:8443/",
    ],
)
def test_rejects_unsupported_url_shapes(url: str) -> None:
    fetcher = SafeWebFetcher(
        resolver=_resolver_for("93.184.216.34"),
        opener=_Opener([]),
    )

    with pytest.raises(UnsafeWebFetchError):
        fetcher.fetch(url)


def test_revalidates_redirect_targets() -> None:
    opener = _Opener(
        [_redirect("https://example.com/start", "http://127.0.0.1/admin")]
    )

    def resolver(host: str, port: int, *, type: int):
        address = "127.0.0.1" if host == "127.0.0.1" else "93.184.216.34"
        return _resolver_for(address)(host, port, type=type)

    fetcher = SafeWebFetcher(resolver=resolver, opener=opener)

    with pytest.raises(UnsafeWebFetchError, match="non-public"):
        fetcher.fetch("https://example.com/start")

    assert len(opener.requests) == 1


def test_enforces_payload_limit_without_unbounded_read() -> None:
    response = _Response(b"x" * 11)
    fetcher = SafeWebFetcher(
        max_bytes=10,
        resolver=_resolver_for("93.184.216.34"),
        opener=_Opener([response]),
    )

    with pytest.raises(WebFetchLimitError, match="exceeds 10 bytes"):
        fetcher.fetch("https://example.com/article")

    assert response.read_sizes == [11]


def test_rejects_binary_content() -> None:
    fetcher = SafeWebFetcher(
        resolver=_resolver_for("93.184.216.34"),
        opener=_Opener(
            [_Response(b"binary", content_type="application/octet-stream")]
        ),
    )

    with pytest.raises(UnsafeWebFetchError, match="content type"):
        fetcher.fetch("https://example.com/archive")


def test_returns_bounded_decoded_text() -> None:
    fetcher = SafeWebFetcher(
        max_text_chars=4,
        resolver=_resolver_for("93.184.216.34"),
        opener=_Opener([_Response("héllo".encode())]),
    )

    assert fetcher.fetch("https://example.com/article") == "héll"
