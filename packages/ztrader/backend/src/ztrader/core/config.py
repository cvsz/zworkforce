# apps/ztrader/backend/src/ztrader/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Tuple

class Settings(BaseSettings):
    # Base Config
    ENVIRONMENT: str = "production"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ztrader"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security (No default values to force configuration via environment)
    ENCRYPTION_KEY: str
    JWT_SECRET: str
    ADMIN_API_TOKEN: Optional[str] = None

    # OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    # Trading Defaults
    EXECUTION_MODE: str = "paper" # paper or live
    LIVE_TRADING_ENABLED: bool = False
    GLOBAL_KILL_SWITCH: bool = True

    # Risk Limits
    RISK_MAX_ORDER_NOTIONAL: float = 100.0
    RISK_ALLOWED_SYMBOLS: Tuple[str, ...] = ("BTC/USDT", "ETH/USDT")

    # TradingAgents Integration
    TRADINGAGENTS_LLM_PROVIDER: str = "openai"
    TRADINGAGENTS_DEEP_THINK_LLM: str = "gpt-5.5"
    TRADINGAGENTS_QUICK_THINK_LLM: str = "gpt-5.4-mini"
    TRADINGAGENTS_OUTPUT_LANGUAGE: str = "English"
    TRADINGAGENTS_MAX_DEBATE_ROUNDS: int = 1
    TRADINGAGENTS_MAX_RISK_ROUNDS: int = 1
    TRADINGAGENTS_CHECKPOINT_ENABLED: bool = False
    TRADINGAGENTS_BENCHMARK_TICKER: Optional[str] = None
    TRADINGAGENTS_TEMPERATURE: Optional[float] = None
    TRADINGAGENTS_GOOGLE_THINKING_LEVEL: Optional[str] = None
    TRADINGAGENTS_OPENAI_REASONING_EFFORT: Optional[str] = None
    TRADINGAGENTS_ANTHROPIC_EFFORT: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
