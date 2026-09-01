from __future__ import annotations

import logging

import numpy as np
from ztrader.abt.binance_perp_bot.config import BotConfig
from ztrader.abt.binance_perp_bot.db.timescale import TimescaleJournal
from ztrader.abt.binance_perp_bot.execution.exchange import BinancePerpStream
from ztrader.abt.binance_perp_bot.ml.gate import XGBoostTradeGate
from ztrader.abt.binance_perp_bot.ml.regime import ADXRegimeDetector
from ztrader.abt.binance_perp_bot.models import MarketSnapshot
from ztrader.abt.binance_perp_bot.risk.position_manager import PositionManager
from ztrader.abt.binance_perp_bot.strategies.factory import StrategyFactory


class ExecutionEngine:
    def __init__(
        self,
        config: BotConfig,
        stream: BinancePerpStream,
        factory: StrategyFactory,
        position_manager: PositionManager,
        regime_detector: ADXRegimeDetector,
        trade_gate: XGBoostTradeGate,
        journal: TimescaleJournal,
    ) -> None:
        self.config = config
        self.stream = stream
        self.factory = factory
        self.position_manager = position_manager
        self.regime_detector = regime_detector
        self.trade_gate = trade_gate
        self.journal = journal
        self.logger = logging.getLogger(__name__)

    async def on_snapshot(self, snapshot: MarketSnapshot) -> None:
        await self.journal.write_ohlcv(snapshot)
        await self._update_return_history(snapshot)
        equity = await self.stream.fetch_equity_usdt()
        await self.position_manager.update_equity(equity)
        regime = self.regime_detector.detect(snapshot)
        price = float(snapshot.ticker.get("last") or snapshot.ohlcv[-1][4])
        for strategy in self.factory.all():
            if snapshot.timeframe not in strategy.timeframes:
                continue
            signal = strategy.check_signal(snapshot, regime)
            if signal is None:
                continue
            signal.size_usdt = strategy.calculate_size(
                snapshot, equity, self.config.fixed_notional_usdt
            )
            signal.metadata.update(
                {
                    "price": price,
                    "regime_suitability": strategy.get_regime_suitability(regime),
                }
            )
            extra = {
                "trace_id": signal.trace_id,
                "symbol": signal.symbol,
                "strategy": signal.strategy.value,
            }
            if strategy.get_regime_suitability(regime) < 0.50:
                await self.journal.write_signal(
                    signal, "regime_rejected", signal.metadata
                )
                self.logger.info("signal_regime_rejected", extra=extra)
                continue
            if not self.trade_gate.allow(snapshot, signal):
                await self.journal.write_signal(signal, "ml_rejected", signal.metadata)
                self.logger.info("signal_ml_rejected", extra=extra)
                continue
            intent = await self.position_manager.reserve(
                signal, price, self.config.leverage
            )
            if intent is None:
                await self.journal.write_signal(
                    signal, "risk_rejected", signal.metadata
                )
                self.logger.info("signal_risk_rejected", extra=extra)
                continue
            try:
                order = await self.stream.execute(intent)
                fill = float(order.get("average") or price)
                await self.position_manager.commit_open(intent, fill)
                await self.journal.write_signal(
                    signal, "executed", {**signal.metadata, "order": order}
                )
                self.logger.info("signal_executed", extra=extra)
            except Exception:
                await self.position_manager.release(intent)
                await self.journal.write_signal(
                    signal, "execution_failed", signal.metadata
                )
                self.logger.exception("signal_execution_failed", extra=extra)

    async def _update_return_history(self, snapshot: MarketSnapshot) -> None:
        closes = np.asarray([candle[4] for candle in snapshot.ohlcv], dtype=float)
        if closes.size < 21:
            return
        returns = np.diff(closes) / np.maximum(closes[:-1], 1e-9)
        await self.position_manager.set_return_history(snapshot.symbol, returns[-120:])
