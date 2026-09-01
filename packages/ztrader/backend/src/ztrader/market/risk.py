from __future__ import annotations

from dataclasses import dataclass

from zkbtrader.models import RiskDecision, RiskDecisionStatus, StrategyIntent


@dataclass(frozen=True)
class RiskLimits:
    max_order_notional: float = 100.0
    max_trades_per_symbol: int = 5
    allowed_symbols: tuple[str, ...] = ("BTC/USDT",)


class RiskEngine:
    """Fail-closed risk validation for every strategy intent."""

    def __init__(self, limits: RiskLimits | None = None, *, kill_switch: bool = False) -> None:
        self.limits = limits or RiskLimits()
        self.kill_switch = kill_switch
        self._trade_count_by_symbol: dict[str, int] = {}

    def validate_intent(self, intent: StrategyIntent) -> RiskDecision:
        if self.kill_switch:
            return self._deny(intent, "global_kill_switch")
        if intent.symbol not in self.limits.allowed_symbols:
            return self._deny(intent, "symbol_not_allowed")
        if intent.notional <= 0:
            return self._deny(intent, "invalid_notional")
        if intent.notional > self.limits.max_order_notional:
            return self._deny(intent, "max_order_notional_exceeded")
        current_count = self._trade_count_by_symbol.get(intent.symbol, 0)
        if current_count >= self.limits.max_trades_per_symbol:
            return self._deny(intent, "max_trades_per_symbol_exceeded")
        return RiskDecision(
            status=RiskDecisionStatus.ALLOW,
            reason_code="allowed",
            request_id=intent.request_id,
            details={"symbol": intent.symbol, "notional": intent.notional},
        )

    def record_accepted_intent(self, intent: StrategyIntent) -> None:
        current_count = self._trade_count_by_symbol.get(intent.symbol, 0)
        self._trade_count_by_symbol[intent.symbol] = current_count + 1

    @staticmethod
    def _deny(intent: StrategyIntent, reason_code: str) -> RiskDecision:
        return RiskDecision(
            status=RiskDecisionStatus.DENY,
            reason_code=reason_code,
            request_id=intent.request_id,
            details={"symbol": intent.symbol, "notional": intent.notional},
        )
