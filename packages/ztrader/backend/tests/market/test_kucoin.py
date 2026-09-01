from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import httpx
import pytest

from zkbtrader.adapters.kucoin import InvalidMarketDataResponse, KucoinReadOnlyAdapter


@contextmanager
def _adapter_for(
    handler: Callable[[httpx.Request], httpx.Response],
) -> Iterator[KucoinReadOnlyAdapter]:
    transport = httpx.MockTransport(handler)
    with httpx.Client(
        base_url="https://api.kucoin.com", transport=transport, timeout=1.0
    ) as client:
        yield KucoinReadOnlyAdapter(client=client)


def test_list_symbols_normalizes_kucoin_format() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2/symbols"
        return httpx.Response(
            200,
            json={
                "code": "200000",
                "data": [
                    {
                        "symbol": "BTC-USDT",
                        "baseCurrency": "BTC",
                        "quoteCurrency": "USDT",
                        "enableTrading": True,
                    }
                ],
            },
        )

    with _adapter_for(handler) as adapter:
        symbols = adapter.list_symbols()

    assert len(symbols) == 1
    assert symbols[0].symbol == "BTC/USDT"
    assert symbols[0].base_currency == "BTC"
    assert symbols[0].quote_currency == "USDT"
    assert symbols[0].trading_enabled is True


def test_get_ticker_parses_price() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/market/orderbook/level1"
        assert request.url.params["symbol"] == "BTC-USDT"
        return httpx.Response(
            200,
            json={
                "code": "200000",
                "data": {"symbol": "BTC-USDT", "price": "50000.12"},
            },
        )

    with _adapter_for(handler) as adapter:
        ticker = adapter.get_ticker("btc/usdt")

    assert ticker.symbol == "BTC/USDT"
    assert ticker.price == 50000.12


def test_get_candles_parses_rows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/market/candles"
        assert request.url.params["symbol"] == "BTC-USDT"
        assert request.url.params["type"] == "1hour"
        return httpx.Response(
            200,
            json={
                "code": "200000",
                "data": [
                    ["1700000060", "100", "101", "102", "99", "12.3", "1245.0"],
                    ["1700000000", "90", "100", "105", "85", "10", "900"],
                ],
            },
        )

    with _adapter_for(handler) as adapter:
        candles = adapter.get_candles("BTC-USDT", timeframe="1hour", limit=2)

    assert len(candles) == 2
    assert candles[0].timestamp == 1700000000
    assert candles[0].open == 90.0
    assert candles[0].high == 105.0
    assert candles[0].low == 85.0
    assert candles[0].close == 100.0
    assert candles[1].timestamp == 1700000060


def test_get_orderbook_parses_levels() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/market/orderbook/level2_20"
        assert request.url.params["symbol"] == "BTC-USDT"
        return httpx.Response(
            200,
            json={
                "code": "200000",
                "data": {
                    "sequence": "12345",
                    "bids": [["50000", "1.5"], ["49999", "0.75"]],
                    "asks": [["50001", "1.25"], ["50002", "0.5"]],
                },
            },
        )

    with _adapter_for(handler) as adapter:
        snapshot = adapter.get_orderbook("BTC/USDT", depth=2)

    assert snapshot.symbol == "BTC/USDT"
    assert snapshot.depth == 2
    assert snapshot.sequence == 12345
    assert snapshot.bids[0].price == 50000.0
    assert snapshot.bids[0].size == 1.5
    assert snapshot.asks[1].price == 50002.0


def test_get_server_time_parses_public_timestamp() -> None:
    epoch_ms = 1700000000123

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/timestamp"
        return httpx.Response(200, json={"code": "200000", "data": epoch_ms})

    with _adapter_for(handler) as adapter:
        server_time = adapter.get_server_time()

    assert server_time.epoch_ms == epoch_ms
    assert server_time.iso_time == datetime.fromtimestamp(epoch_ms / 1000, tz=UTC).isoformat()


def test_invalid_ticker_payload_raises_safe_adapter_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "200000", "data": {"symbol": "BTC-USDT"}})

    with _adapter_for(handler) as adapter:
        with pytest.raises(InvalidMarketDataResponse):
            adapter.get_ticker("BTC/USDT")
