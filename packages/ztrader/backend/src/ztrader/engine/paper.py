# apps/ztrader/backend/src/ztrader/engine/paper.py

from dataclasses import dataclass
from ztrader.engine.risk import RiskEngine, StrategyIntent, RiskStatus

@dataclass
class PaperPortfolio:
    usdt: float = 1000.0
    btc: float = 0.0

@dataclass(frozen=True)
class PaperOrderResult:
    symbol: str
    side: str
    notional: float
    price: float
    base_amount: float
    fee: float
    strategy_id: str
    request_id: str

class PaperExecutionEngine:
    """Deterministic paper-only execution engine with no exchange side effects."""

    def __init__(self, portfolio: PaperPortfolio | None = None, fee_rate: float = 0.001) -> None:
        self.portfolio = portfolio or PaperPortfolio()
        self.fee_rate = fee_rate

    def execute(self, intent: StrategyIntent, price: float, risk: RiskEngine) -> PaperOrderResult:
        # Validate through risk engine
        status, reason = risk.validate(intent)
        if status != RiskStatus.ALLOW:
            raise ValueError(f"risk_denied:{reason}")

        if price <= 0:
            raise ValueError("price must be positive")

        if intent.side == "buy":
            return self._enter_long(intent, price)
        elif intent.side == "sell":
            return self._exit_long(intent, price)
        else:
            raise ValueError(f"unsupported side: {intent.side}")

    def _enter_long(self, intent: StrategyIntent, price: float) -> PaperOrderResult:
        fee = intent.notional * self.fee_rate
        total_cost = intent.notional + fee
        if total_cost > self.portfolio.usdt:
            raise ValueError("paper_balance_insufficient")
        base_amount = intent.notional / price
        self.portfolio.usdt -= total_cost
        self.portfolio.btc += base_amount
        return PaperOrderResult(
            symbol=intent.symbol,
            side=intent.side,
            notional=intent.notional,
            price=price,
            base_amount=base_amount,
            fee=fee,
            strategy_id=intent.strategy_id,
            request_id=intent.request_id,
        )

    def _exit_long(self, intent: StrategyIntent, price: float) -> PaperOrderResult:
        base_amount = intent.notional / price
        if base_amount > self.portfolio.btc:
            raise ValueError("paper_position_insufficient")
        fee = intent.notional * self.fee_rate
        self.portfolio.btc -= base_amount
        self.portfolio.usdt += intent.notional - fee
        return PaperOrderResult(
            symbol=intent.symbol,
            side=intent.side,
            notional=intent.notional,
            price=price,
            base_amount=base_amount,
            fee=fee,
            strategy_id=intent.strategy_id,
            request_id=intent.request_id,
        )
