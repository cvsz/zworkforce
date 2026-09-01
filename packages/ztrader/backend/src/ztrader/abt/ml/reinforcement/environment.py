"""
Trading environment for reinforcement learning.
"""

from typing import Any, Dict, Tuple


class TradingEnvironment:
    """Simulated trading environment for RL training."""

    def __init__(self, historical_data: list, initial_params: Dict[str, float]):
        """
        Initialize trading environment.

        Args:
            historical_data: Historical market data
            initial_params: Initial strategy parameters
        """
        self.data = historical_data
        self.initial_params = initial_params.copy()
        self.params = initial_params.copy()
        self.current_step = 0
        self.balance = 10000.0
        self.position = 0.0
        self.initial_balance = 10000.0

    def reset(self) -> str:
        """
        Reset environment to initial state.

        Returns:
            Initial state
        """
        self.params = self.initial_params.copy()
        self.current_step = 0
        self.balance = self.initial_balance
        self.position = 0.0
        return self._get_state()

    def step(self, action: str) -> Tuple[str, float, bool, Dict]:
        """
        Take a step in the environment.

        Args:
            action: Action to take (parameter adjustment)

        Returns:
            Tuple of (next_state, reward, done, info)
        """
        # Apply parameter adjustment
        self._apply_action(action)

        # Simulate trading step
        if self.current_step < len(self.data):
            market_data = self.data[self.current_step]
            reward = self._execute_trading_step(market_data)
        else:
            reward = 0.0

        self.current_step += 1
        done = self.current_step >= len(self.data)

        next_state = self._get_state()
        info = {"balance": self.balance, "position": self.position}

        return next_state, reward, done, info

    def get_current_params(self) -> Dict[str, float]:
        """Get current parameters."""
        return self.params.copy()

    def _get_state(self) -> str:
        """Get current state representation."""
        # Discretize parameters for state representation
        state_parts = []
        for param, value in sorted(self.params.items()):
            discretized = int(value / 5) * 5  # Round to nearest 5
            state_parts.append(f"{param}={discretized}")

        return "|".join(state_parts)

    def _apply_action(self, action: str):
        """Apply parameter adjustment action."""
        if "_" not in action:
            return

        param, direction = action.rsplit("_", 1)

        if param not in self.params:
            return

        # Get parameter constraints from space (if available)
        adjustment = 1.0  # Default adjustment

        if direction == "increase":
            self.params[param] = min(self.params[param] + adjustment, 100.0)
        elif direction == "decrease":
            self.params[param] = max(self.params[param] - adjustment, 0.0)

    def _execute_trading_step(self, market_data: Dict[str, Any]) -> float:
        """
        Execute one trading step and return reward.

        Args:
            market_data: Current market data

        Returns:
            Reward for this step
        """
        # Simplified trading logic - generate signal based on parameters
        signal = self._generate_signal(market_data)

        # Execute trade
        if signal == "BUY" and self.position == 0:
            # Open long position
            price = market_data.get("close", 100.0)
            self.position = self.balance / price
            self.balance = 0
        elif signal == "SELL" and self.position > 0:
            # Close position
            price = market_data.get("close", 100.0)
            self.balance = self.position * price
            self.position = 0

        # Calculate reward (change in portfolio value)
        portfolio_value = self.balance + (
            self.position * market_data.get("close", 100.0)
        )
        reward = (portfolio_value - self.initial_balance) / self.initial_balance

        return reward

    def _generate_signal(self, market_data: Dict[str, Any]) -> str:
        """
        Generate trading signal based on current parameters.

        Args:
            market_data: Current market data

        Returns:
            Trading signal ('BUY', 'SELL', or 'HOLD')
        """
        # Simplified signal generation using RSI-like logic
        rsi = market_data.get("rsi", 50.0)

        oversold = self.params.get("oversoldThreshold", 30.0)
        overbought = self.params.get("overboughtThreshold", 70.0)

        if rsi < oversold:
            return "BUY"
        elif rsi > overbought:
            return "SELL"
        else:
            return "HOLD"
