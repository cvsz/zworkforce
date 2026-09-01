from __future__ import annotations

from pydantic import Field, PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="BOT_", extra="ignore"
    )

    binance_api_key: SecretStr = Field(..., description="Binance Futures API key")
    binance_api_secret: SecretStr = Field(..., description="Binance Futures API secret")
    symbols: list[str] = Field(
        default_factory=lambda: ["BTC/USDT:USDT", "ETH/USDT:USDT"]
    )
    fixed_notional_usdt: float = Field(default=100.0, gt=0)
    max_correlation: float = Field(default=0.65, gt=0, lt=1)
    max_positions: int = Field(default=30, ge=1, le=200)
    max_margin_ratio: float = Field(default=0.80, gt=0, le=1)
    websocket_timeout_seconds: float = Field(default=30.0, gt=0)
    heartbeat_interval_seconds: float = Field(default=15.0, gt=0)
    max_reconnect_backoff_seconds: float = Field(default=60.0, gt=1)
    max_candles_per_stream: int = Field(default=500, ge=50, le=5_000)
    internal_port: int = Field(
        default=22022,
        description="Spaceship Standard port for internal comms or SSH tunnels",
    )
    leverage: int = Field(default=3, ge=1, le=20)
    database_url: PostgresDsn = Field(
        default="postgresql://postgres:postgres@postgres:5432/abtp"
    )
    ml_model_path: str = Field(default="/models/xgb_trade_gate.json")
    dry_run: bool = True


class AllocationConfig(BaseSettings):
    scalp: float = Field(default=0.20, ge=0, le=1)
    swing: float = Field(default=0.30, ge=0, le=1)
    position: float = Field(default=0.50, ge=0, le=1)

    @model_validator(mode="after")
    def validate_total_allocation(self) -> "AllocationConfig":
        total = self.scalp + self.swing + self.position
        if abs(total - 1.0) > 1e-6:
            raise ValueError("strategy allocations must sum to 1.0")
        return self
