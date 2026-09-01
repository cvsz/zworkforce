"""
Strategy parameter tuning using reinforcement learning.
"""

from typing import Any, Dict, List, Tuple

import numpy as np

from .environment import TradingEnvironment


class StrategyTuner:
    """RL-based strategy parameter optimization."""

    def __init__(
        self,
        param_space: Dict[str, Dict],
        learning_rate: float = 0.1,
        discount: float = 0.95,
    ):
        """
        Initialize the strategy tuner.

        Args:
            param_space: Dictionary defining parameter search space
            learning_rate: Learning rate for Q-learning
            discount: Discount factor for future rewards
        """
        self.param_space = param_space
        self.lr = learning_rate
        self.gamma = discount
        self.q_table = {}

    def optimize(
        self,
        strategy: str,
        historical_data: List[Dict],
        initial_params: Dict[str, float],
        max_episodes: int = 1000,
        optimization_goal: str = "SHARPE_RATIO",
    ) -> Tuple[Dict[str, float], Dict[str, Any]]:
        """
        Optimize strategy parameters using Q-learning.

        Args:
            strategy: Strategy name
            historical_data: Historical market data
            initial_params: Initial parameter values
            max_episodes: Maximum training episodes
            optimization_goal: Goal to optimize ('SHARPE_RATIO', 'TOTAL_RETURN', etc.)

        Returns:
            Tuple of (optimized_params, performance_metrics)
        """
        env = TradingEnvironment(historical_data, initial_params)

        best_params = initial_params.copy()
        best_reward = -float("inf")

        for episode in range(max_episodes):
            state = env.reset()
            total_reward = 0
            epsilon = max(0.01, 1.0 - episode / max_episodes)  # Epsilon decay

            steps = 0
            max_steps = len(historical_data) - 1

            while steps < max_steps:
                # Choose action (parameter adjustment)
                action = self._get_action(state, epsilon)

                # Take step in environment
                next_state, reward, done, info = env.step(action)

                # Update Q-table
                self._update_q_value(state, action, reward, next_state)

                total_reward += reward
                state = next_state
                steps += 1

                if done:
                    break

            # Track best parameters
            if total_reward > best_reward:
                best_reward = total_reward
                best_params = env.get_current_params()

        # Calculate performance metrics
        performance = self._evaluate_params(
            best_params, historical_data, initial_params
        )

        return best_params, performance

    def _get_action(self, state: str, epsilon: float) -> str:
        """
        Get action using epsilon-greedy policy.

        Args:
            state: Current state
            epsilon: Exploration rate

        Returns:
            Action to take
        """
        if np.random.random() < epsilon:
            # Explore: random parameter adjustment
            return self._random_action()
        else:
            # Exploit: best known action
            return self._best_action(state)

    def _random_action(self) -> str:
        """Generate random parameter adjustment."""
        param = np.random.choice(list(self.param_space.keys()))
        direction = np.random.choice(["increase", "decrease"])
        return f"{param}_{direction}"

    def _best_action(self, state: str) -> str:
        """Get best action for given state."""
        possible_actions = self._get_possible_actions()

        q_values = [
            self.q_table.get((state, action), 0.0) for action in possible_actions
        ]

        if max(q_values) == 0:
            return self._random_action()

        best_action_idx = np.argmax(q_values)
        return possible_actions[best_action_idx]

    def _get_possible_actions(self) -> List[str]:
        """Get list of all possible actions."""
        actions = []
        for param in self.param_space.keys():
            actions.append(f"{param}_increase")
            actions.append(f"{param}_decrease")
        return actions

    def _update_q_value(self, state: str, action: str, reward: float, next_state: str):
        """Update Q-table using Q-learning update rule."""
        current_q = self.q_table.get((state, action), 0.0)

        # Get max Q-value for next state
        possible_actions = self._get_possible_actions()
        max_next_q = max(
            [self.q_table.get((next_state, a), 0.0) for a in possible_actions]
        )

        # Q-learning update
        new_q = current_q + self.lr * (reward + self.gamma * max_next_q - current_q)
        self.q_table[(state, action)] = new_q

    def _evaluate_params(
        self,
        params: Dict[str, float],
        historical_data: List[Dict],
        original_params: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Evaluate parameter performance.

        Args:
            params: Parameters to evaluate
            historical_data: Historical data
            original_params: Original parameters for comparison

        Returns:
            Performance metrics
        """
        # Simulate trading with optimized params
        optimized_returns = self._simulate_strategy(params, historical_data)
        original_returns = self._simulate_strategy(original_params, historical_data)

        # Calculate metrics
        optimized_sharpe = self._calculate_sharpe_ratio(optimized_returns)
        original_sharpe = self._calculate_sharpe_ratio(original_returns)

        optimized_total_return = sum(optimized_returns)
        original_total_return = sum(original_returns)

        optimized_max_dd = self._calculate_max_drawdown(optimized_returns)
        original_max_dd = self._calculate_max_drawdown(original_returns)

        return {
            "before": {
                "sharpeRatio": original_sharpe,
                "totalReturn": original_total_return,
                "maxDrawdown": original_max_dd,
                "winRate": self._calculate_win_rate(original_returns),
            },
            "after": {
                "sharpeRatio": optimized_sharpe,
                "totalReturn": optimized_total_return,
                "maxDrawdown": optimized_max_dd,
                "winRate": self._calculate_win_rate(optimized_returns),
            },
            "improvement": {
                "sharpeRatio": (
                    f"{((optimized_sharpe / original_sharpe - 1) * 100):.1f}%"
                    if original_sharpe != 0
                    else "N/A"
                ),
                "totalReturn": (
                    f"{(optimized_total_return / original_total_return - 1) * 100:.1f}%"
                    if original_total_return != 0
                    else "N/A"
                ),
                "maxDrawdown": (
                    f"{((optimized_max_dd / original_max_dd - 1) * 100):.1f}%"
                    if original_max_dd != 0
                    else "N/A"
                ),
            },
        }

    def _simulate_strategy(
        self, params: Dict[str, float], data: List[Dict]
    ) -> List[float]:
        """Simulate strategy with given parameters."""
        # Simplified simulation - returns random walk for now
        returns = np.random.randn(len(data)) * 0.01
        return returns.tolist()

    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio."""
        if len(returns) == 0:
            return 0.0
        returns_array = np.array(returns)
        return (
            float(np.mean(returns_array) / np.std(returns_array))
            if np.std(returns_array) > 0
            else 0.0
        )

    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown."""
        if len(returns) == 0:
            return 0.0
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = cumulative - running_max
        return float(np.min(drawdown))

    def _calculate_win_rate(self, returns: List[float]) -> float:
        """Calculate win rate."""
        if len(returns) == 0:
            return 0.0
        wins = sum(1 for r in returns if r > 0)
        return wins / len(returns)
