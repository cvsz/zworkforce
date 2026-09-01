"""TradingAgents data provider integration for ztrader's market module.

Integrates TradingAgents' data sources (Alpha Vantage, FRED, Polymarket,
Reddit, StockTwits) as additional data providers for the ztrader platform.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DataSourceConfig:
    """Configuration for a TradingAgents data source."""
    name: str
    enabled: bool = False
    api_key_env: Optional[str] = None
    description: str = ""


# Data sources available from TradingAgents
AVAILABLE_DATA_SOURCES = {
    "alpha_vantage": DataSourceConfig(
        name="Alpha Vantage",
        api_key_env="ALPHA_VANTAGE_API_KEY",
        description="Stock data, fundamentals, news, and technical indicators",
    ),
    "fred": DataSourceConfig(
        name="FRED (Federal Reserve)",
        api_key_env="FRED_API_KEY",
        description="Macroeconomic data from the Federal Reserve",
    ),
    "polymarket": DataSourceConfig(
        name="Polymarket",
        api_key_env=None,
        description="Prediction markets data (keyless access)",
    ),
    "reddit": DataSourceConfig(
        name="Reddit",
        api_key_env="REDDIT_CLIENT_ID",
        description="Social media sentiment from Reddit (r/wallstreetbets, etc.)",
    ),
    "stocktwits": DataSourceConfig(
        name="StockTwits",
        api_key_env=None,
        description="Social trading platform sentiment data",
    ),
}


def get_available_data_sources() -> dict[str, DataSourceConfig]:
    """Return all available TradingAgents data sources."""
    return dict(AVAILABLE_DATA_SOURCES)


def get_enabled_data_sources() -> dict[str, DataSourceConfig]:
    """Return data sources that have their API keys configured."""
    import os

    enabled = {}
    for name, config in AVAILABLE_DATA_SOURCES.items():
        if config.api_key_env is None:
            # Keyless access (Polymarket, StockTwits) — always available
            enabled[name] = config
        elif os.environ.get(config.api_key_env):
            enabled[name] = config
            enabled[name].enabled = True
    return enabled


def get_data_source_summary() -> list[dict[str, Any]]:
    """Return a summary of all data sources for the frontend."""
    result = []
    for name, config in AVAILABLE_DATA_SOURCES.items():
        result.append({
            "name": config.name,
            "key": name,
            "enabled": config.enabled,
            "has_api_key": config.api_key_env is None or bool(
                __import__("os").environ.get(config.api_key_env or "")
            ),
            "description": config.description,
        })
    return result