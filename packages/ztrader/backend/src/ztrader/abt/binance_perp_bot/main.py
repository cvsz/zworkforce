from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from typing import Awaitable, Callable

from ztrader.abt.binance_perp_bot.config import AllocationConfig, BotConfig
from ztrader.abt.binance_perp_bot.db.timescale import TimescaleJournal
from ztrader.abt.binance_perp_bot.execution.engine import ExecutionEngine
from ztrader.abt.binance_perp_bot.execution.exchange import BinancePerpStream
from ztrader.abt.binance_perp_bot.health import HealthServer
from ztrader.abt.binance_perp_bot.ml.gate import XGBoostTradeGate
from ztrader.abt.binance_perp_bot.ml.regime import ADXRegimeDetector
from ztrader.abt.binance_perp_bot.models import MarketSnapshot
from ztrader.abt.binance_perp_bot.risk.position_manager import PositionManager
from ztrader.abt.binance_perp_bot.runtime import BotRuntimeState
from ztrader.abt.binance_perp_bot.strategies.factory import StrategyFactory
from ztrader.abt.binance_perp_bot.utils.logging import configure_json_logging


class SnapshotDispatcher:
    def __init__(self) -> None:
        self.handler: Callable[[MarketSnapshot], Awaitable[None]] | None = None

    async def __call__(self, snapshot: MarketSnapshot) -> None:
        if self.handler is None:
            return
        await self.handler(snapshot)


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)


async def run() -> None:
    configure_json_logging()
    logger = logging.getLogger(__name__)
    config = BotConfig()
    runtime_state = BotRuntimeState()
    health_server = HealthServer(runtime_state, "0.0.0.0", config.internal_port)
    health_server.start()
    dispatcher = SnapshotDispatcher()
    stream = BinancePerpStream(config, dispatcher, runtime_state=runtime_state)
    journal = TimescaleJournal(str(config.database_url))
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)
    try:
        await journal.migrate()
        runtime_state.mark_db_ready()
        engine = ExecutionEngine(
            config=config,
            stream=stream,
            factory=StrategyFactory(),
            position_manager=PositionManager(
                AllocationConfig(),
                config.max_correlation,
                max_positions=config.max_positions,
                max_margin_ratio=config.max_margin_ratio,
            ),
            regime_detector=ADXRegimeDetector(),
            trade_gate=XGBoostTradeGate(config.ml_model_path),
            journal=journal,
        )
        dispatcher.handler = engine.on_snapshot
        tasks = [
            asyncio.create_task(stream.stream_symbol(symbol, timeframe))
            for symbol in config.symbols
            for timeframe in ("1m", "5m", "4h", "1d", "1w")
        ]
        await stop_event.wait()
        logger.info(
            "shutdown_requested",
            extra={"trace_id": "shutdown", "symbol": "system", "strategy": "main"},
        )
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as exc:
        runtime_state.mark_error(exc)
        raise
    finally:
        runtime_state.mark_stopping()
        await stream.close()
        health_server.stop()


if __name__ == "__main__":
    asyncio.run(run())
