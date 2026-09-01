from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx


class MarketDataError(Exception):
    """Base class for safe public market-data adapter errors."""


class MarketDataUnavailable(MarketDataError):
    """Raised when KuCoin public market data is unavailable."""


class InvalidMarketDataResponse(MarketDataError):
    """Raised when KuCoin public market data payloads are malformed."""


@dataclass(frozen=True)
class Ticker:
    symbol: str
    price: float


@dataclass(frozen=True)
class MarketSymbol:
    symbol: str
    base_currency: str
    quote_currency: str
    trading_enabled: bool


@dataclass(frozen=True)
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float


@dataclass(frozen=True)
class OrderBookLevel:
    price: float
    size: float


@dataclass(frozen=True)
class OrderBookSnapshot:
    symbol: str
    depth: int
    sequence: int
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]


@dataclass(frozen=True)
class ServerTime:
    epoch_ms: int
    iso_time: str


class MarketDataClient(Protocol):
    def list_symbols(self) -> list[MarketSymbol]:
        pass

    def get_ticker(self, symbol: str) -> Ticker:
        pass

    def get_candles(self, symbol: str, timeframe: str, limit: int = 100) -> list[Candle]:
        pass

    def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBookSnapshot:
        pass

    def get_server_time(self) -> ServerTime:
        pass


class KucoinReadOnlyAdapter:
    """KuCoin public market-data adapter.

    This client only calls public endpoints and does not support private auth,
    order placement, funding, margin, leverage, or futures execution.
    """

    _ALLOWED_TIMEFRAMES = {
        "1min",
        "3min",
        "5min",
        "15min",
        "30min",
        "1hour",
        "2hour",
        "4hour",
        "6hour",
        "8hour",
        "12hour",
        "1day",
        "1week",
        "1month",
    }

    def __init__(
        self,
        *,
        base_url: str = "https://api.kucoin.com",
        sandbox: bool = False,
        timeout: float = 5.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.sandbox = sandbox
        self._client = client or httpx.Client(base_url=self.base_url, timeout=timeout)

    def list_symbols(self) -> list[MarketSymbol]:
        payload = self._get_json("/api/v2/symbols")
        data = self._require_list(payload.get("data"), "symbols.data")
        symbols: list[MarketSymbol] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            raw_symbol = item.get("symbol")
            if not isinstance(raw_symbol, str):
                continue
            normalized = self._normalize_symbol(raw_symbol)
            base_symbol, quote_symbol = normalized.split("/")

            raw_base = item.get("baseCurrency")
            raw_quote = item.get("quoteCurrency")
            base_currency = raw_base if isinstance(raw_base, str) else base_symbol
            quote_currency = raw_quote if isinstance(raw_quote, str) else quote_symbol
            trading_enabled = self._to_bool(item.get("enableTrading"), default=False)

            symbols.append(
                MarketSymbol(
                    symbol=normalized,
                    base_currency=base_currency,
                    quote_currency=quote_currency,
                    trading_enabled=trading_enabled,
                )
            )
        if not symbols:
            raise InvalidMarketDataResponse("no_symbols_returned")
        return symbols

    def get_ticker(self, symbol: str) -> Ticker:
        normalized_symbol = self._normalize_symbol(symbol)
        payload = self._get_json(
            "/api/v1/market/orderbook/level1",
            params={"symbol": self._to_exchange_symbol(normalized_symbol)},
        )
        data = self._require_dict(payload.get("data"), "ticker.data")
        price = self._to_float(data.get("price"), "ticker.price")
        return Ticker(symbol=normalized_symbol, price=price)

    def get_candles(self, symbol: str, timeframe: str, limit: int = 100) -> list[Candle]:
        if timeframe not in self._ALLOWED_TIMEFRAMES:
            raise ValueError("invalid_timeframe")
        if limit <= 0:
            raise ValueError("limit_must_be_positive")
        if limit > 1500:
            raise ValueError("limit_too_large")

        normalized_symbol = self._normalize_symbol(symbol)
        payload = self._get_json(
            "/api/v1/market/candles",
            params={
                "symbol": self._to_exchange_symbol(normalized_symbol),
                "type": timeframe,
            },
        )
        data = self._require_list(payload.get("data"), "candles.data")

        candles: list[Candle] = []
        for raw_candle in data[:limit]:
            raw_values = self._require_list(raw_candle, "candles.entry")
            if len(raw_values) < 7:
                raise InvalidMarketDataResponse("invalid_candle_shape")
            candles.append(
                Candle(
                    timestamp=self._to_int(raw_values[0], "candles.timestamp"),
                    open=self._to_float(raw_values[1], "candles.open"),
                    close=self._to_float(raw_values[2], "candles.close"),
                    high=self._to_float(raw_values[3], "candles.high"),
                    low=self._to_float(raw_values[4], "candles.low"),
                    volume=self._to_float(raw_values[5], "candles.volume"),
                    turnover=self._to_float(raw_values[6], "candles.turnover"),
                )
            )

        candles.reverse()
        return candles

    def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBookSnapshot:
        if depth <= 0:
            raise ValueError("depth_must_be_positive")
        if depth > 100:
            raise ValueError("depth_too_large")

        normalized_symbol = self._normalize_symbol(symbol)
        endpoint_depth = 20 if depth <= 20 else 100
        payload = self._get_json(
            f"/api/v1/market/orderbook/level2_{endpoint_depth}",
            params={"symbol": self._to_exchange_symbol(normalized_symbol)},
        )
        data = self._require_dict(payload.get("data"), "orderbook.data")
        sequence = self._to_int(data.get("sequence"), "orderbook.sequence")
        bids = self._parse_levels(data.get("bids"), "orderbook.bids", depth=depth)
        asks = self._parse_levels(data.get("asks"), "orderbook.asks", depth=depth)
        return OrderBookSnapshot(
            symbol=normalized_symbol,
            depth=depth,
            sequence=sequence,
            bids=bids,
            asks=asks,
        )

    def get_server_time(self) -> ServerTime:
        payload = self._get_json("/api/v1/timestamp")
        epoch_ms = self._to_int(payload.get("data"), "server_time.data")
        iso_time = datetime.fromtimestamp(epoch_ms / 1000, tz=UTC).isoformat()
        return ServerTime(epoch_ms=epoch_ms, iso_time=iso_time)

    def _parse_levels(self, value: Any, field: str, *, depth: int) -> list[OrderBookLevel]:
        levels = self._require_list(value, field)
        parsed_levels: list[OrderBookLevel] = []
        for level in levels[:depth]:
            raw_level = self._require_list(level, field)
            if len(raw_level) < 2:
                raise InvalidMarketDataResponse(f"invalid_orderbook_level:{field}")
            parsed_levels.append(
                OrderBookLevel(
                    price=self._to_float(raw_level[0], f"{field}.price"),
                    size=self._to_float(raw_level[1], f"{field}.size"),
                )
            )
        return parsed_levels

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self._client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise MarketDataUnavailable("market_data_timeout") from exc
        except httpx.HTTPError as exc:
            raise MarketDataUnavailable("market_data_connection_error") from exc

        status_code = response.status_code
        if status_code >= 500:
            raise MarketDataUnavailable("market_data_upstream_error")

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MarketDataUnavailable("market_data_request_rejected") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise InvalidMarketDataResponse("market_data_non_json_response") from exc

        if not isinstance(payload, dict):
            raise InvalidMarketDataResponse("market_data_non_object_payload")

        code = payload.get("code")
        if code not in (None, "200000", 200000):
            raise MarketDataUnavailable("market_data_upstream_non_success")
        return payload

    def _normalize_symbol(self, symbol: str) -> str:
        normalized = symbol.strip().upper().replace("-", "/")
        parts = normalized.split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError("invalid_symbol")
        return f"{parts[0]}/{parts[1]}"

    def _to_exchange_symbol(self, symbol: str) -> str:
        return symbol.replace("/", "-")

    def _require_list(self, value: Any, field: str) -> list[Any]:
        if isinstance(value, list):
            return value
        raise InvalidMarketDataResponse(f"invalid_field_type:{field}")

    def _require_dict(self, value: Any, field: str) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        raise InvalidMarketDataResponse(f"invalid_field_type:{field}")

    def _to_float(self, value: Any, field: str) -> float:
        if isinstance(value, (float, int)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError as exc:
                raise InvalidMarketDataResponse(f"invalid_float:{field}") from exc
        raise InvalidMarketDataResponse(f"invalid_float:{field}")

    def _to_int(self, value: Any, field: str) -> int:
        if isinstance(value, bool):
            raise InvalidMarketDataResponse(f"invalid_int:{field}")
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError as exc:
                raise InvalidMarketDataResponse(f"invalid_int:{field}") from exc
        raise InvalidMarketDataResponse(f"invalid_int:{field}")

    def _to_bool(self, value: Any, *, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        return default
