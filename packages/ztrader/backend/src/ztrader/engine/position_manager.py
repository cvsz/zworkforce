from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from ztrader.binance_perp_bot.models import (
    Position,
    PositionIntent,
    RegimeMode,
    Side,
    SignalAction,
    StrategyKind,
    TradeSignal,
)


class AllocationConfigLike(Protocol):
    scalp: float
    swing: float
    position: float


from enum import StrEnum

class RiskRejectionReason(StrEnum):
    MAX_POSITIONS = "max_positions"
    MARGIN_RATIO = "margin_ratio"
    CORRELATION = "correlation"
    CONFLICT = "conflict"
    ALLOCATION = "allocation"


@dataclass(frozen=True)
class PortfolioSnapshot:
    equity_usdt: float
    reserved_usdt: float
    used_margin_usdt: float
    open_positions: tuple[Position, ...]
    strategy_heatmap: dict[StrategyKind, float]
    margin_ratio: float


class PositionManager:
    """Single source of truth for capital, position state, and risk admission.

    The manager intentionally keeps reservation, correlation, conflict, and commit
    checks under one asyncio lock. That makes signal-to-order admission atomic
    across concurrent timeframe workers and prevents double-spending shared USDT
    equity while WebSocket tasks are yielding control.
    """

    def __init__(
        self,
        allocation: AllocationConfigLike,
        max_correlation: float,
        *,
        max_positions: int = 30,
        max_margin_ratio: float = 0.80,
    ) -> None:
        self._allocation = allocation
        self._max_correlation = max_correlation
        self._max_positions = max_positions
        self._max_margin_ratio = max_margin_ratio
        self._equity_usdt = 0.0
        self._reserved_usdt = 0.0
        self._positions: dict[str, Position] = {}
        self._return_history: dict[str, np.ndarray] = {}
        self._lock = asyncio.Lock()
        self._last_rejection: RiskRejectionReason | None = None
        self.logger = logging.getLogger(__name__)

    @property
    def last_rejection(self) -> RiskRejectionReason | None:
        return self._last_rejection

    async def update_equity(self, equity_usdt: float) -> None:
        async with self._lock:
            self._equity_usdt = max(0.0, equity_usdt)

    async def set_return_history(self, symbol: str, returns: np.ndarray) -> None:
        bounded = np.asarray(returns, dtype=float)[-500:]
        async with self._lock:
            self._return_history[symbol] = bounded[np.isfinite(bounded)]

    async def reserve(
        self, signal: TradeSignal, price: float, leverage: int
    ) -> PositionIntent | None:
        if signal.action not in {SignalAction.ENTER_LONG, SignalAction.ENTER_SHORT}:
            return None
        async with self._lock:
            self._last_rejection = None
            if len(self._positions) >= self._max_positions:
                return self._reject_locked(signal, RiskRejectionReason.MAX_POSITIONS)
            if self._has_strategy_conflict_locked(signal):
                return self._reject_locked(signal, RiskRejectionReason.CONFLICT)
            correlation = self._portfolio_correlation_locked(signal.symbol)
            if correlation > self._max_correlation:
                signal.metadata["portfolio_correlation"] = correlation
                return self._reject_locked(signal, RiskRejectionReason.CORRELATION)

            heatmap = self._heatmap_locked()
            allocation_cap = (
                self._equity_usdt
                * self._target_allocation(signal.strategy)
                * heatmap[signal.strategy]
            )
            used = sum(
                p.margin_used
                for p in self._positions.values()
                if p.strategy_kind == signal.strategy
            )
            remaining_equity = self._equity_usdt - self._reserved_usdt
            remaining_margin_capacity = max(
                0.0, self._equity_usdt * self._max_margin_ratio - self.used_margin_usdt
            )
            available = min(
                remaining_equity, allocation_cap - used, remaining_margin_capacity
            )
            notional = min(signal.size_usdt, max(0.0, available))
            if notional <= 0:
                reason = (
                    RiskRejectionReason.MARGIN_RATIO
                    if remaining_margin_capacity <= 0
                    else RiskRejectionReason.ALLOCATION
                )
                return self._reject_locked(signal, reason)
            self._reserved_usdt += notional
            side = Side.BUY if signal.action == SignalAction.ENTER_LONG else Side.SELL
            amount = notional * leverage / price
            signal.metadata.update(
                {
                    "reserved_notional_usdt": notional,
                    "strategy_heatmap": heatmap[signal.strategy],
                    "margin_ratio": self._margin_ratio_locked(),
                }
            )
            return PositionIntent(signal, side, amount, notional, leverage)

    async def commit_open(self, intent: PositionIntent, fill_price: float) -> None:
        side = "LONG" if intent.side == Side.BUY else "SHORT"
        regime = intent.signal.regime
        position = Position(
            strategy_id=intent.signal.strategy.value,
            symbol=intent.signal.symbol,
            side=side,
            size=intent.amount,
            entry_price=fill_price,
            leverage=intent.leverage,
            margin_used=intent.notional_usdt,
            regime_at_open=(
                regime.value if isinstance(regime, RegimeMode) else str(regime)
            ),
            trace_id=intent.signal.trace_id,
        )
        async with self._lock:
            self._reserved_usdt = max(0.0, self._reserved_usdt - intent.notional_usdt)
        opened = await self.open_position(position)
        if not opened:
            self.logger.warning(
                "position_commit_rejected_after_fill",
                extra={
                    "trace_id": intent.signal.trace_id,
                    "symbol": intent.signal.symbol,
                },
            )

    async def open_position(self, position: Position) -> bool:
        """Register an already-filled position in the portfolio ledger.

        Returns ``False`` when the manager is already at capacity. The commit path
        releases the reservation before calling this method, so this check keeps
        direct callers and post-fill commits consistent.
        """
        async with self._lock:
            if len(self._positions) >= self._max_positions:
                return False
            self._positions[position.id] = position
            return True

    async def close_position(self, position_key: str) -> Position | None:
        async with self._lock:
            if position := self._positions.pop(position_key, None):
                return position
            for key, position in tuple(self._positions.items()):
                if position.symbol == position_key:
                    return self._positions.pop(key)
            return None

    async def release(self, intent: PositionIntent) -> None:
        async with self._lock:
            self._reserved_usdt = max(0.0, self._reserved_usdt - intent.notional_usdt)

    async def snapshot(self) -> PortfolioSnapshot:
        async with self._lock:
            return PortfolioSnapshot(
                equity_usdt=self._equity_usdt,
                reserved_usdt=self._reserved_usdt,
                used_margin_usdt=self.used_margin_usdt,
                open_positions=tuple(self._positions.values()),
                strategy_heatmap=self._heatmap_locked(),
                margin_ratio=self._margin_ratio_locked(),
            )

    @property
    def used_margin_usdt(self) -> float:
        return (
            sum(position.margin_used for position in self._positions.values())
            + self._reserved_usdt
        )

    @property
    def current_exposure_usdt(self) -> float:
        return sum(position.margin_used for position in self._positions.values())

    def _reject_locked(
        self, signal: TradeSignal, reason: RiskRejectionReason
    ) -> PositionIntent | None:
        self._last_rejection = reason
        signal.metadata["risk_rejection_reason"] = reason.value
        self.logger.info(
            "risk_rejected",
            extra={
                "trace_id": signal.trace_id,
                "symbol": signal.symbol,
                "strategy": signal.strategy.value,
                "reason": reason.value,
            },
        )
        return None

    def _target_allocation(self, strategy: StrategyKind) -> float:
        return {
            StrategyKind.SCALP: self._allocation.scalp,
            StrategyKind.SWING: self._allocation.swing,
            StrategyKind.POSITION: self._allocation.position,
        }[strategy]

    def _heatmap_locked(self) -> dict[StrategyKind, float]:
        exposure = defaultdict(float)
        for position in self._positions.values():
            kind = position.strategy_kind
            if kind is not None:
                exposure[kind] += position.margin_used
        total = sum(exposure.values()) or 1.0
        return {
            kind: max(
                0.50,
                min(
                    1.25, 1.0 - (exposure[kind] / total - self._target_allocation(kind))
                ),
            )
            for kind in StrategyKind
        }

    def _portfolio_correlation_locked(self, symbol: str) -> float:
        incoming = self._return_history.get(symbol)
        if incoming is None or incoming.size < 20 or not self._positions:
            return 0.0
        correlations = []
        for position in self._positions.values():
            existing = self._return_history.get(position.symbol)
            if existing is None:
                continue
            length = min(incoming.size, existing.size)
            if length < 20:
                continue
            left = incoming[-length:]
            right = existing[-length:]
            mask = np.isfinite(left) & np.isfinite(right)
            if mask.sum() < 20:
                continue
            corr = np.corrcoef(left[mask], right[mask])[0, 1]
            if np.isfinite(corr):
                correlations.append(abs(float(corr)))
        return max(correlations, default=0.0)

    def _has_strategy_conflict_locked(self, signal: TradeSignal) -> bool:
        incoming_side = (
            Side.BUY if signal.action == SignalAction.ENTER_LONG else Side.SELL
        )
        for position in self._positions.values():
            if (
                position.symbol != signal.symbol
                or position.side == self._position_side(incoming_side)
            ):
                continue
            # Long-horizon position trades are authoritative. Shorter-horizon
            # scalp/swing signals must not unwind them by opening the opposite side.
            if (
                position.strategy_kind == StrategyKind.POSITION
                or signal.strategy != StrategyKind.POSITION
            ):
                signal.metadata.update(
                    {
                        "conflicting_strategy": (
                            position.strategy_kind.value
                            if position.strategy_kind
                            else position.strategy_id
                        ),
                        "conflicting_side": position.side.lower(),
                    }
                )
                return True
        return False

    def _margin_ratio_locked(self) -> float:
        if self._equity_usdt <= 0:
            return 0.0
        return self.used_margin_usdt / self._equity_usdt

    @staticmethod
    def _position_side(side: Side) -> str:
        return "LONG" if side == Side.BUY else "SHORT"
