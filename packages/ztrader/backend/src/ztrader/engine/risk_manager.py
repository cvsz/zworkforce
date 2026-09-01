from __future__ import annotations

import logging
from collections import deque
from collections.abc import Iterable, Sequence

import numpy as np

from ztrader.binance_perp_bot.models import Position


class RiskEngine:
    """Pre-trade portfolio gate for correlation and strategy conflict checks."""

    def __init__(
        self, correlation_threshold: float = 0.65, history_window: int = 120
    ) -> None:
        self.threshold = correlation_threshold
        self.history_window = history_window
        self.price_history: dict[str, deque[float]] = {}
        self.logger = logging.getLogger("RiskEngine")

    def set_price_history(self, symbol: str, prices: Sequence[float]) -> None:
        history: deque[float] = deque(maxlen=self.history_window)
        history.extend(float(price) for price in prices[-self.history_window :])
        self.price_history[symbol] = history

    def update_price(self, symbol: str, price: float) -> None:
        self.price_history.setdefault(symbol, deque(maxlen=self.history_window)).append(
            float(price)
        )

    def check_correlation(
        self, new_symbol: str, current_positions: Iterable[Position]
    ) -> bool:
        incoming = self._returns(new_symbol)
        if incoming is None:
            return True

        for position in current_positions:
            existing = self._returns(position.symbol)
            if existing is None:
                continue
            window = min(incoming.size, existing.size)
            if window < 20:
                continue
            corr = np.corrcoef(incoming[-window:], existing[-window:])[0, 1]
            if np.isfinite(corr) and abs(float(corr)) > self.threshold:
                self.logger.warning(
                    "correlation_too_high",
                    extra={
                        "symbol": new_symbol,
                        "existing_symbol": position.symbol,
                        "correlation": float(corr),
                        "trace_id": position.trace_id,
                    },
                )
                return False
        return True

    def resolve_conflict(
        self, new_signal: str, current_positions: Iterable[Position], symbol: str
    ) -> bool:
        normalized_signal = new_signal.upper()
        for position in current_positions:
            if position.symbol != symbol:
                continue
            is_position_strategy = "position" in position.strategy_id.lower()
            is_opposite_side = position.side != normalized_signal
            if is_position_strategy and is_opposite_side:
                self.logger.info(
                    "position_conflict_detected",
                    extra={
                        "symbol": symbol,
                        "existing_side": position.side,
                        "incoming_side": normalized_signal,
                        "trace_id": position.trace_id,
                    },
                )
                return False
        return True

    def _returns(self, symbol: str) -> np.ndarray | None:
        history = self.price_history.get(symbol)
        if history is None or len(history) < 21:
            return None
        prices = np.asarray(history, dtype=float)
        return np.diff(prices) / np.maximum(prices[:-1], 1e-9)
