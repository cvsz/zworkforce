"""// ZeaZDev [Backend Prometheus Metrics Service] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 2) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from typing import Any, Dict

from prometheus_client import Counter, Gauge, Histogram, Info

# Trading Metrics
trades_total = Counter(
    "trading_trades_total",
    "Total number of trades executed",
    ["bot_id", "strategy", "side", "symbol"],
)

trade_pnl = Histogram(
    "trading_trade_pnl",
    "Profit/Loss per trade",
    ["bot_id", "strategy", "symbol"],
    buckets=(-1000, -100, -10, -1, 0, 1, 10, 100, 1000, 10000),
)

strategy_signals = Counter(
    "trading_strategy_signals_total",
    "Total strategy signals generated",
    ["strategy", "signal_type", "symbol"],
)

# Risk Metrics
risk_checks_total = Counter(
    "risk_checks_total",
    "Total risk checks performed",
    ["result"],  # allowed or rejected
)

circuit_breaker_trips = Counter(
    "risk_circuit_breaker_trips_total", "Number of times circuit breaker was tripped"
)

max_drawdown = Gauge(
    "risk_max_drawdown", "Current maximum drawdown observed", ["bot_id"]
)

current_equity = Gauge("risk_current_equity", "Current equity value", ["bot_id"])

consecutive_losses = Gauge(
    "risk_consecutive_losses", "Current number of consecutive losses", ["bot_id"]
)

# Bot Performance Metrics
bot_status = Gauge(
    "bot_status",
    "Bot running status (1=running, 0=stopped)",
    ["bot_id", "strategy", "symbol"],
)

strategy_execution_time = Histogram(
    "strategy_execution_seconds",
    "Time taken to execute strategy",
    ["strategy"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0),
)

# WebSocket Metrics
websocket_connections = Gauge(
    "websocket_connections_active",
    "Number of active WebSocket connections",
    ["exchange"],
)

websocket_messages = Counter(
    "websocket_messages_total",
    "Total WebSocket messages received",
    ["exchange", "message_type"],
)

websocket_errors = Counter(
    "websocket_errors_total", "Total WebSocket errors", ["exchange", "error_type"]
)

# Exchange API Metrics
exchange_api_calls = Counter(
    "exchange_api_calls_total",
    "Total exchange API calls",
    ["exchange", "endpoint", "status"],
)

exchange_api_latency = Histogram(
    "exchange_api_latency_seconds",
    "Exchange API call latency",
    ["exchange", "endpoint"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

# System Metrics
system_info = Info("abtpro_system", "System information")


class MetricsCollector:
    """Helper class for collecting and recording metrics."""

    @staticmethod
    def record_trade(bot_id: int, strategy: str, side: str, symbol: str, pnl: float):
        """Record a trade execution."""
        trades_total.labels(
            bot_id=str(bot_id), strategy=strategy, side=side, symbol=symbol
        ).inc()

        trade_pnl.labels(bot_id=str(bot_id), strategy=strategy, symbol=symbol).observe(
            pnl
        )

    @staticmethod
    def record_strategy_signal(strategy: str, signal_type: str, symbol: str):
        """Record a strategy signal."""
        strategy_signals.labels(
            strategy=strategy, signal_type=signal_type, symbol=symbol
        ).inc()

    @staticmethod
    def record_risk_check(allowed: bool):
        """Record a risk check result."""
        result = "allowed" if allowed else "rejected"
        risk_checks_total.labels(result=result).inc()

    @staticmethod
    def record_circuit_breaker_trip():
        """Record a circuit breaker trip."""
        circuit_breaker_trips.inc()

    @staticmethod
    def update_risk_metrics(bot_id: int, metrics: Dict[str, Any]):
        """Update risk-related metrics."""
        if "drawdown" in metrics:
            drawdown_data = metrics["drawdown"]
            max_drawdown.labels(bot_id=str(bot_id)).set(
                drawdown_data.get("max_drawdown_observed", 0)
            )
            current_equity.labels(bot_id=str(bot_id)).set(
                drawdown_data.get("current_equity", 0)
            )

        if "circuit_breaker" in metrics:
            cb_data = metrics["circuit_breaker"]
            consecutive_losses.labels(bot_id=str(bot_id)).set(
                cb_data.get("consecutive_losses", 0)
            )

    @staticmethod
    def update_bot_status(bot_id: int, strategy: str, symbol: str, is_running: bool):
        """Update bot status."""
        status_value = 1 if is_running else 0
        bot_status.labels(bot_id=str(bot_id), strategy=strategy, symbol=symbol).set(
            status_value
        )

    @staticmethod
    def time_strategy_execution(strategy: str):
        """Context manager to time strategy execution."""
        return strategy_execution_time.labels(strategy=strategy).time()

    @staticmethod
    def record_websocket_connection(exchange: str, connected: bool):
        """Record WebSocket connection status."""
        value = 1 if connected else 0
        websocket_connections.labels(exchange=exchange).set(value)

    @staticmethod
    def record_websocket_message(exchange: str, message_type: str):
        """Record a WebSocket message."""
        websocket_messages.labels(exchange=exchange, message_type=message_type).inc()

    @staticmethod
    def record_websocket_error(exchange: str, error_type: str):
        """Record a WebSocket error."""
        websocket_errors.labels(exchange=exchange, error_type=error_type).inc()

    @staticmethod
    def record_exchange_api_call(
        exchange: str, endpoint: str, status: str, latency: float
    ):
        """Record an exchange API call."""
        exchange_api_calls.labels(
            exchange=exchange, endpoint=endpoint, status=status
        ).inc()

        exchange_api_latency.labels(exchange=exchange, endpoint=endpoint).observe(
            latency
        )

    @staticmethod
    def set_system_info(version: str, environment: str):
        """Set system information."""
        system_info.info({"version": version, "environment": environment, "phase": "2"})


# Initialize system info
MetricsCollector.set_system_info("1.0.0", "production")
