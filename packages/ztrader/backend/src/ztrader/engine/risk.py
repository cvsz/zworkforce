# apps/ztrader/backend/src/ztrader/engine/risk.py

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Tuple

logger = logging.getLogger("ztrader.risk")

class RiskStatus(StrEnum):
    ALLOW = "allow"
    DENY = "deny"

@dataclass(frozen=True)
class StrategyIntent:
    symbol: str
    side: str # buy, sell
    notional: float
    strategy_id: str
    request_id: str

class RiskEngine:
    def __init__(self, allowed_symbols: Tuple[str, ...], max_order_notional: float, kill_switch: bool):
        self.allowed_symbols = allowed_symbols
        self.max_order_notional = max_order_notional
        self.kill_switch = kill_switch

    def validate(self, intent: StrategyIntent) -> Tuple[RiskStatus, str]:
        if self.kill_switch:
            logger.warning(f"Risk DENY: Global kill switch active. Intent: {intent.request_id}")
            return RiskStatus.DENY, "global_kill_switch_active"

        if intent.symbol not in self.allowed_symbols:
            logger.warning(f"Risk DENY: Symbol {intent.symbol} not in allowlist. Intent: {intent.request_id}")
            return RiskStatus.DENY, "symbol_not_allowed"

        if intent.notional <= 0:
            logger.warning(f"Risk DENY: Invalid notional value {intent.notional}. Intent: {intent.request_id}")
            return RiskStatus.DENY, "invalid_notional"

        if intent.notional > self.max_order_notional:
            logger.warning(f"Risk DENY: Notional {intent.notional} exceeds max {self.max_order_notional}. Intent: {intent.request_id}")
            return RiskStatus.DENY, "max_order_notional_exceeded"

        return RiskStatus.ALLOW, "allowed"
