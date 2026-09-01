from __future__ import annotations

from zkbtrader.models import (
    IntentSide,
    PaperOrder,
    PaperPortfolio,
    RiskDecisionStatus,
    StrategyIntent,
)
from zkbtrader.risk import RiskEngine


class PaperExecutionEngine:
    """Deterministic paper-only execution engine.

    This class has no exchange side effects. It exists to validate strategy and risk
    behavior before any future live connector is considered.
    """

    def __init__(self, portfolio: PaperPortfolio | None = None, *, fee_rate: float = 0.001) -> None:
        self.portfolio = portfolio or PaperPortfolio()
        self.fee_rate = fee_rate
        self.orders: list[PaperOrder] = []

    def execute(self, intent: StrategyIntent, *, price: float, risk: RiskEngine) -> PaperOrder:
        decision = risk.validate_intent(intent)
        if decision.status != RiskDecisionStatus.ALLOW:
            raise ValueError(f"risk_denied:{decision.reason_code}")
        if price <= 0:
            raise ValueError("price must be positive")

        if intent.side == IntentSide.ENTER_LONG:
            order = self._enter_long(intent, price)
        elif intent.side == IntentSide.EXIT_LONG:
            order = self._exit_long(intent, price)
        else:  # pragma: no cover - exhaustive guard for future enum expansion
            raise ValueError(f"unsupported side: {intent.side}")

        risk.record_accepted_intent(intent)
        self.orders.append(order)
        return order

    def _enter_long(self, intent: StrategyIntent, price: float) -> PaperOrder:
        fee = intent.notional * self.fee_rate
        total_cost = intent.notional + fee
        if total_cost > self.portfolio.usdt:
            raise ValueError("paper_balance_insufficient")
        base_amount = intent.notional / price
        self.portfolio.usdt -= total_cost
        self.portfolio.btc += base_amount
        return PaperOrder(
            id=f"paper-{len(self.orders) + 1}",
            symbol=intent.symbol,
            side=intent.side,
            notional=intent.notional,
            price=price,
            base_amount=base_amount,
            fee=fee,
            strategy_id=intent.strategy_id,
            request_id=intent.request_id,
        )

    def _exit_long(self, intent: StrategyIntent, price: float) -> PaperOrder:
        base_amount = intent.notional / price
        if base_amount > self.portfolio.btc:
            raise ValueError("paper_position_insufficient")
        fee = intent.notional * self.fee_rate
        self.portfolio.btc -= base_amount
        self.portfolio.usdt += intent.notional - fee
        return PaperOrder(
            id=f"paper-{len(self.orders) + 1}",
            symbol=intent.symbol,
            side=intent.side,
            notional=intent.notional,
            price=price,
            base_amount=base_amount,
            fee=fee,
            strategy_id=intent.strategy_id,
            request_id=intent.request_id,
        )
