from __future__ import annotations

from dataclasses import dataclass

from .core import Position, RiskLimits, Side


class RiskRejected(RuntimeError):
    pass


@dataclass(frozen=True)
class Fill:
    side: Side
    shares: float
    price: float
    total_cost: float


class PaperBroker:
    def __init__(self, starting_cash: float, limits: RiskLimits) -> None:
        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.limits = limits
        self.position = Position()
        self.fills: list[Fill] = []

    def buy(self, side: Side, quoted_price: float, order_usd: float) -> Fill:
        if not 0.0 < quoted_price < 1.0:
            raise RiskRejected("price must be between 0 and 1")
        if order_usd <= 0 or order_usd > self.limits.max_order_usd:
            raise RiskRejected("order exceeds configured order limit")
        slippage = quoted_price * self.limits.slippage_bps / 10_000
        price = min(0.999999, quoted_price + slippage)
        fee = order_usd * self.limits.fee_bps / 10_000
        total = order_usd + fee
        if total > self.cash:
            raise RiskRejected("insufficient paper cash")
        if self.position.gross_exposure + total > self.limits.max_market_exposure_usd:
            raise RiskRejected("market exposure limit reached")
        shares = order_usd / price
        projected = dict(self.position.shares)
        projected[side] += shares
        if abs(projected[Side.UP] - projected[Side.DOWN]) > self.limits.max_directional_shares:
            raise RiskRejected("directional residual limit reached")
        self.cash -= total
        self.position.shares[side] += shares
        self.position.cost[side] += total
        fill = Fill(side, shares, price, total)
        self.fills.append(fill)
        return fill

    def settle(self, winner: Side) -> float:
        payout = self.position.shares[winner]
        self.cash += payout
        pnl = self.cash - self.starting_cash
        return pnl

