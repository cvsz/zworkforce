from __future__ import annotations

import importlib
import importlib.util
import logging
from pathlib import Path
from typing import Any

import numpy as np
from ztrader.abt.binance_perp_bot.indicators import adx, atr, closes, ema, rsi
from ztrader.abt.binance_perp_bot.models import (
    MarketSnapshot,
    RegimeMode,
    SignalAction,
    TradeSignal,
)


class XGBoostTradeGate:
    """XGBoost binary trade/no-trade gate with deterministic cold-start scoring."""

    def __init__(self, model_path: str, threshold: float = 0.55) -> None:
        self.threshold = threshold
        self.model_path = Path(model_path)
        self.logger = logging.getLogger(__name__)
        self.model: Any | None = None
        self._xgboost: Any | None = None

        if not self.model_path.exists():
            self._log_cold_start("xgb_model_missing_using_calibrated_gate")
            return

        if importlib.util.find_spec("xgboost") is None:
            self._log_cold_start("xgb_dependency_missing_using_calibrated_gate")
            return

        self._xgboost = importlib.import_module("xgboost")
        self.model = self._xgboost.Booster()
        self.model.load_model(str(self.model_path))

    def features(self, snapshot: MarketSnapshot, signal: TradeSignal) -> np.ndarray:
        price = closes(snapshot.ohlcv)
        last = price[-1]
        feature_row = np.asarray(
            [
                signal.confidence,
                atr(snapshot.ohlcv) / max(last, 1e-9),
                adx(snapshot.ohlcv),
                rsi(price, 14),
                (ema(price, 12) - ema(price, 26)) / max(last, 1e-9),
                float(signal.action == SignalAction.ENTER_LONG),
                float(signal.regime == RegimeMode.TREND),
                float(signal.regime == RegimeMode.MEAN_REVERSION),
            ],
            dtype=float,
        )
        return feature_row.reshape(1, -1)

    def allow(self, snapshot: MarketSnapshot, signal: TradeSignal) -> bool:
        if self.model is not None and self._xgboost is not None:
            matrix = self._xgboost.DMatrix(self.features(snapshot, signal))
            probability = float(self.model.predict(matrix)[0])
            gate_mode = "xgboost"
        else:
            probability = self._calibrated_probability(snapshot, signal)
            gate_mode = "calibrated_cold_start"
        signal.metadata["ml_gate_mode"] = gate_mode
        signal.metadata["xgb_trade_probability"] = probability
        return probability >= self.threshold

    def _log_cold_start(self, message: str) -> None:
        self.logger.warning(
            message,
            extra={
                "trace_id": "ml-gate",
                "symbol": "system",
                "strategy": "xgboost",
            },
        )

    def _calibrated_probability(
        self, snapshot: MarketSnapshot, signal: TradeSignal
    ) -> float:
        price = closes(snapshot.ohlcv)
        last = price[-1]
        volatility = atr(snapshot.ohlcv) / max(last, 1e-9)
        trend_strength = adx(snapshot.ohlcv) / 100.0
        momentum = rsi(price, 14)
        momentum_quality = 1.0 - min(abs(momentum - 55.0), 45.0) / 45.0
        volatility_penalty = min(volatility / 0.05, 1.0) * 0.20
        regime_bonus = 0.08 if signal.regime != RegimeMode.HIGH_VOLATILITY else -0.12
        score = (
            0.58 * signal.confidence
            + 0.22 * trend_strength
            + 0.20 * momentum_quality
            + regime_bonus
            - volatility_penalty
        )
        return float(max(0.0, min(1.0, score)))
