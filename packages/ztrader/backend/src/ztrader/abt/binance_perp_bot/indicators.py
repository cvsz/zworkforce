from __future__ import annotations

import numpy as np


def closes(ohlcv: list[list[float]]) -> np.ndarray:
    return np.asarray([c[4] for c in ohlcv], dtype=float)


def highs(ohlcv: list[list[float]]) -> np.ndarray:
    return np.asarray([c[2] for c in ohlcv], dtype=float)


def lows(ohlcv: list[list[float]]) -> np.ndarray:
    return np.asarray([c[3] for c in ohlcv], dtype=float)


def ema(values: np.ndarray, period: int) -> float:
    if values.size < period:
        return float(values[-1])
    alpha = 2.0 / (period + 1.0)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1 - alpha) * result
    return float(result)


def rsi(values: np.ndarray, period: int = 14) -> float:
    if values.size <= period:
        return 50.0
    delta = np.diff(values)
    gains = np.where(delta > 0, delta, 0.0)[-period:]
    losses = np.where(delta < 0, -delta, 0.0)[-period:]
    avg_loss = losses.mean()
    if avg_loss == 0:
        return 100.0
    rs = gains.mean() / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def atr(ohlcv: list[list[float]], period: int = 14) -> float:
    if len(ohlcv) < 2:
        return 0.0
    high = highs(ohlcv)
    low = lows(ohlcv)
    close = closes(ohlcv)
    previous_close = np.roll(close, 1)
    true_range = np.maximum(
        high - low, np.maximum(abs(high - previous_close), abs(low - previous_close))
    )[1:]
    return float(true_range[-period:].mean())


def adx(ohlcv: list[list[float]], period: int = 14) -> float:
    if len(ohlcv) <= period + 1:
        return 20.0
    high = highs(ohlcv)
    low = lows(ohlcv)
    close = closes(ohlcv)
    plus_dm = np.maximum(high[1:] - high[:-1], 0.0)
    minus_dm = np.maximum(low[:-1] - low[1:], 0.0)
    plus_dm = np.where(plus_dm > minus_dm, plus_dm, 0.0)
    minus_dm = np.where(minus_dm > plus_dm, minus_dm, 0.0)
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])),
    )
    atr_series = np.convolve(tr, np.ones(period) / period, mode="valid")
    plus_di = (
        100
        * np.convolve(plus_dm, np.ones(period) / period, mode="valid")
        / np.maximum(atr_series, 1e-9)
    )
    minus_di = (
        100
        * np.convolve(minus_dm, np.ones(period) / period, mode="valid")
        / np.maximum(atr_series, 1e-9)
    )
    dx = 100 * abs(plus_di - minus_di) / np.maximum(plus_di + minus_di, 1e-9)
    return float(dx[-period:].mean())
