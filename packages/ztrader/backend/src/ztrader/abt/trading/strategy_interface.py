"""// ZeaZDev [Backend Strategy Interface] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Omega Scaffolding) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type


class Strategy(ABC):
    name: str

    @abstractmethod
    def execute(
        self, ticker_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return dict including potential 'signal': BUY/SELL/HOLD and 'confidence'."""
        pass


class StrategyRegistry:
    _strategies: Dict[str, Type[Strategy]] = {}

    @classmethod
    def register(cls, strategy_cls: Type[Strategy]):
        cls._strategies[strategy_cls.name] = strategy_cls

    @classmethod
    def create(cls, name: str) -> Strategy:
        if name not in cls._strategies:
            raise ValueError(f"Strategy {name} not registered")
        return cls._strategies[name]()

    @classmethod
    def list_names(cls) -> List[str]:
        return sorted(cls._strategies.keys())
