from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from zkbtrader.models import ExecutionMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    execution_mode: ExecutionMode = ExecutionMode.PAPER
    live_trading_enabled: bool = False
    global_kill_switch: bool = False
    default_stake_currency: str = "USDT"
    default_symbols: str = "BTC/USDT"
    paper_starting_usdt: float = Field(default=1000.0, ge=0)
    paper_starting_btc: float = Field(default=0.0, ge=0)
    exchange_base_url: str = "https://api.kucoin.com"
    exchange_sandbox: bool = False
    exchange_timeout_seconds: float = Field(default=5.0, gt=0)
    exchange_readonly_configured: bool = False
    database_url: str = "postgresql+psycopg://zkbtrader:zkbtrader_dev_password@postgres:5432/zkbtrader"

    def assert_safe_startup(self) -> None:
        if self.execution_mode == ExecutionMode.LIVE and not self.live_trading_enabled:
            raise ValueError("live execution requested but live trading flag is false")
        if self.execution_mode == ExecutionMode.LIVE:
            raise ValueError("live execution is not implemented in this scaffold")

    def redacted(self) -> dict[str, str | float | bool]:
        return {
            "app_env": self.app_env,
            "execution_mode": self.execution_mode.value,
            "live_trading_enabled": self.live_trading_enabled,
            "global_kill_switch": self.global_kill_switch,
            "default_stake_currency": self.default_stake_currency,
            "default_symbols": self.default_symbols,
            "paper_starting_usdt": self.paper_starting_usdt,
            "paper_starting_btc": self.paper_starting_btc,
            "exchange_base_url": self.exchange_base_url,
            "exchange_sandbox": self.exchange_sandbox,
            "exchange_timeout_seconds": self.exchange_timeout_seconds,
            "exchange_readonly_configured": self.exchange_readonly_configured,
            "database_url": "redacted",
        }


def get_settings() -> Settings:
    settings = Settings()
    settings.assert_safe_startup()
    return settings
