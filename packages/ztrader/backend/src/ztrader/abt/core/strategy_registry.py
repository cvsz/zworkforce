"""// ZeaZDev [Core Strategy Registry] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from typing import Dict, List, Type

from core.strategy_base import Strategy


class StrategyRegistry:
    """
    Central registry for all trading strategy classes.

    Strategies register themselves by calling:
        StrategyRegistry.register(MyStrategyClass)

    Usage:
        # Register a strategy
        StrategyRegistry.register(MeanReversionStrategy)

        # Create an instance
        strategy = StrategyRegistry.create("MEAN_REVERSION")

        # List all registered strategies
        names = StrategyRegistry.list_names()
    """

    _strategies: Dict[str, Type[Strategy]] = {}

    @classmethod
    def register(cls, strategy_cls: Type[Strategy]) -> None:
        """
        Register a strategy class.

        Args:
            strategy_cls: Strategy class to register (must have 'name' attribute)

        Raises:
            ValueError: If strategy doesn't have a name attribute
        """
        if not hasattr(strategy_cls, "name"):
            raise ValueError(
                f"Strategy class {strategy_cls.__name__} must define a 'name' attribute"
            )

        cls._strategies[strategy_cls.name] = strategy_cls

    @classmethod
    def create(cls, name: str) -> Strategy:
        """
        Create an instance of a registered strategy.

        Args:
            name: Name of the strategy to instantiate

        Returns:
            Instance of the requested strategy

        Raises:
            ValueError: If strategy is not registered
        """
        if name not in cls._strategies:
            raise ValueError(
                f"Strategy '{name}' not registered. Available: {cls.list_names()}"
            )

        return cls._strategies[name]()

    @classmethod
    def list_names(cls) -> List[str]:
        """
        Get list of all registered strategy names.

        Returns:
            Sorted list of strategy names
        """
        return sorted(cls._strategies.keys())

    @classmethod
    def get_class(cls, name: str) -> Type[Strategy]:
        """
        Get the strategy class without instantiating.

        Args:
            name: Name of the strategy

        Returns:
            Strategy class

        Raises:
            ValueError: If strategy is not registered
        """
        if name not in cls._strategies:
            raise ValueError(
                f"Strategy '{name}' not registered. Available: {cls.list_names()}"
            )

        return cls._strategies[name]
