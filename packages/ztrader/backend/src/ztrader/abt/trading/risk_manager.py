"""// ZeaZDev [Backend Risk Manager Enhanced] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 2) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ztrader.abt.models import TradeLog


class MaxDrawdownTracker:
    """Tracks maximum drawdown from peak equity."""

    def __init__(self, max_drawdown_threshold: float = 0.25):
        """
        Args:
            max_drawdown_threshold: Maximum allowed drawdown as fraction
                (e.g., 0.25 = 25%)
        """
        self.max_drawdown_threshold = max_drawdown_threshold
        self.peak_equity = 0.0
        self.current_equity = 0.0
        self.max_drawdown_observed = 0.0

    def update_equity(self, current_equity: float):
        """Update current equity and track peak."""
        self.current_equity = current_equity
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

        # Calculate current drawdown
        if self.peak_equity > 0:
            current_drawdown = (self.peak_equity - current_equity) / self.peak_equity
            self.max_drawdown_observed = max(
                self.max_drawdown_observed, current_drawdown
            )

    def is_drawdown_exceeded(self) -> bool:
        """Check if current drawdown exceeds threshold."""
        if self.peak_equity <= 0:
            return False

        current_drawdown = (self.peak_equity - self.current_equity) / self.peak_equity
        return current_drawdown > self.max_drawdown_threshold

    def get_metrics(self) -> Dict[str, float]:
        """Get current drawdown metrics."""
        current_drawdown = 0.0
        if self.peak_equity > 0:
            current_drawdown = (
                self.peak_equity - self.current_equity
            ) / self.peak_equity

        return {
            "peak_equity": self.peak_equity,
            "current_equity": self.current_equity,
            "current_drawdown": current_drawdown,
            "max_drawdown_observed": self.max_drawdown_observed,
            "threshold": self.max_drawdown_threshold,
        }


class CircuitBreaker:
    """Circuit breaker to halt trading after consecutive losses or rapid trades."""

    def __init__(
        self,
        max_consecutive_losses: int = 5,
        cooldown_minutes: int = 60,
        max_trades_per_hour: int = 20,
    ):
        """
        Args:
            max_consecutive_losses: Maximum number of consecutive losing trades
            cooldown_minutes: Minutes to pause trading after circuit trip
            max_trades_per_hour: Maximum trades allowed per hour
        """
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_minutes = cooldown_minutes
        self.max_trades_per_hour = max_trades_per_hour

        self.consecutive_losses = 0
        self.tripped_until: Optional[datetime] = None
        self.recent_trades: list = []  # List of trade timestamps

    def record_trade_outcome(
        self, is_profitable: bool, timestamp: Optional[datetime] = None
    ):
        """Record a trade outcome."""
        if timestamp is None:
            timestamp = datetime.utcnow()

        self.recent_trades.append(timestamp)

        if is_profitable:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1

            # Trip circuit breaker if too many consecutive losses
            if self.consecutive_losses >= self.max_consecutive_losses:
                self.trip_breaker()

    def trip_breaker(self):
        """Trip the circuit breaker."""
        self.tripped_until = datetime.utcnow() + timedelta(
            minutes=self.cooldown_minutes
        )

    def is_tripped(self) -> bool:
        """Check if circuit breaker is currently tripped."""
        if self.tripped_until is None:
            return False

        if datetime.utcnow() < self.tripped_until:
            return True

        # Reset if cooldown has passed
        self.tripped_until = None
        self.consecutive_losses = 0
        return False

    def check_trade_rate_limit(self) -> bool:
        """Check if trade rate limit is exceeded."""
        cutoff_time = datetime.utcnow() - timedelta(hours=1)

        # Remove old trades
        self.recent_trades = [t for t in self.recent_trades if t > cutoff_time]

        return len(self.recent_trades) >= self.max_trades_per_hour

    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "is_tripped": self.is_tripped(),
            "consecutive_losses": self.consecutive_losses,
            "max_consecutive_losses": self.max_consecutive_losses,
            "tripped_until": (
                self.tripped_until.isoformat() if self.tripped_until else None
            ),
            "trades_last_hour": len(
                [
                    t
                    for t in self.recent_trades
                    if t > datetime.utcnow() - timedelta(hours=1)
                ]
            ),
            "max_trades_per_hour": self.max_trades_per_hour,
        }


class EnhancedRiskManager:
    """Enhanced Risk Manager with Drawdown Tracking and Circuit Breaker."""

    def __init__(
        self,
        max_drawdown: float = 0.25,
        max_position_fraction: float = 0.1,
        max_consecutive_losses: int = 5,
        cooldown_minutes: int = 60,
        max_trades_per_hour: int = 20,
    ):
        self.max_drawdown = max_drawdown
        self.max_position_fraction = max_position_fraction

        self.drawdown_tracker = MaxDrawdownTracker(max_drawdown)
        self.circuit_breaker = CircuitBreaker(
            max_consecutive_losses, cooldown_minutes, max_trades_per_hour
        )

        self.initial_equity = 10000.0  # Default starting equity
        self.current_equity = self.initial_equity

    async def assess(
        self,
        context: Dict[str, Any],
        signal_payload: Dict[str, Any],
        db: Optional[AsyncSession] = None,
        bot_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Assess if trade should be allowed based on risk parameters.

        Returns:
            Dict with 'allowed' (bool) and 'reason' (str)
        """
        if signal_payload.get("signal") == "HOLD":
            return {"allowed": False, "reason": "Signal is HOLD"}

        # Check circuit breaker
        if self.circuit_breaker.is_tripped():
            return {
                "allowed": False,
                "reason": (
                    "Circuit breaker tripped until "
                    f"{self.circuit_breaker.tripped_until}"
                ),
            }

        # Check trade rate limit
        if self.circuit_breaker.check_trade_rate_limit():
            return {
                "allowed": False,
                "reason": (
                    "Trade rate limit exceeded "
                    f"({self.circuit_breaker.max_trades_per_hour}/hour)"
                ),
            }

        # Update equity from database if available
        if db and bot_id:
            await self.update_equity_from_trades(db, bot_id)

        # Check drawdown
        if self.drawdown_tracker.is_drawdown_exceeded():
            return {
                "allowed": False,
                "reason": (
                    "Max drawdown exceeded: "
                    f"{self.drawdown_tracker.get_metrics()['current_drawdown']:.2%}"
                ),
            }

        return {"allowed": True, "reason": "All risk checks passed"}

    async def update_equity_from_trades(self, db: AsyncSession, bot_id: int):
        """Update current equity based on trade logs."""
        result = await db.execute(
            select(TradeLog)
            .where(TradeLog.botRunId == bot_id)
            .order_by(TradeLog.createdAt.desc())
        )
        trades = result.scalars().all()

        total_pnl = sum(trade.pnl for trade in trades)
        self.current_equity = self.initial_equity + total_pnl
        self.drawdown_tracker.update_equity(self.current_equity)

    def record_trade_result(self, pnl: float):
        """Record trade result for circuit breaker."""
        is_profitable = pnl > 0
        self.circuit_breaker.record_trade_outcome(is_profitable)

        # Update equity
        self.current_equity += pnl
        self.drawdown_tracker.update_equity(self.current_equity)

    def get_metrics(self) -> Dict[str, Any]:
        """Get all risk metrics."""
        return {
            "drawdown": self.drawdown_tracker.get_metrics(),
            "circuit_breaker": self.circuit_breaker.get_status(),
            "current_equity": self.current_equity,
            "initial_equity": self.initial_equity,
        }
