from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ztrader.engine.strategy import Candle


class HealthResponse(BaseModel):
    status: str
    environment: str
    execution_mode: str
    live_trading_enabled: bool
    kill_switch_active: bool

class BacktestRequest(BaseModel):
    strategy_name: str
    symbol: str
    fast_period: int = 3
    slow_period: int = 5
    notional: float = 25.0
    candles: list[Candle]

class BacktestResponse(BaseModel):
    strategy_id: str
    candles_seen: int
    orders_created: int
    ending_usdt: float
    ending_btc: float

class BotStartRequest(BaseModel):
    strategy_name: str
    symbol: str
    notional: float = 25.0
    fast_period: int = 3
    slow_period: int = 5

class BotStatusResponse(BaseModel):
    bot_id: str
    strategy_name: str
    symbol: str
    active: bool
    execution_mode: str

class KillSwitchRequest(BaseModel):
    active: bool

class OrderResponse(BaseModel):
    id: UUID
    symbol: str
    side: str
    execution_mode: str
    notional: float
    price: float
    base_amount: float
    fee: float
    status: str
    strategy_id: str
    request_id: UUID

class AuditLogResponse(BaseModel):
    id: UUID
    event_type: str
    actor: str
    severity: str
    message: str
    details: Any

class KeyRegisterRequest(BaseModel):
    exchange: str
    api_key: str
    api_secret: str
    passphrase: str | None = None

class TradingViewAlertPayload(BaseModel):
    ticker: str | None = Field(None, description="Trading symbol, e.g. BTCUSDT")
    symbol: str | None = Field(None, description="Trading symbol alias, e.g. BTCUSDT")
    exchange: str = Field(default="binance.com", description="Exchange target name")
    action: str = Field(..., description="BUY, SELL, or CLOSE")
    price: float | None = Field(None, description="Trigger price")
    strategy: str | None = Field(None, description="TradingView Strategy name")
    message: str | None = Field(None, description="Custom message")
    interval: str | None = Field(None, description="Timeframe interval")
    volume: float | None = Field(None, description="Trigger volume")
    secret: str | None = Field(None, description="Webhook secret token")

    @property
    def resolved_symbol(self) -> str:
        return self.ticker or self.symbol or "UNKNOWN"

class TradingViewAlertResponse(BaseModel):
    id: UUID
    ticker: str
    exchange: str
    action: str
    price: float | None
    strategy: str | None
    interval: str | None
    volume: float | None
    message: str | None
    received_at: datetime
    processed: bool

class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str | None = None
    role: str
    created_at: datetime

class RoleUpdateRequest(BaseModel):
    role: Literal["user", "operator", "admin"]

class AdminContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    user_email: str | None = None
    start_date: datetime
    end_date: datetime
    is_active: bool

class ContractCreateRequest(BaseModel):
    user_id: UUID
    end_date: datetime
    is_active: bool = True

class AdminRiskConfigRequest(BaseModel):
    kill_switch_active: bool
    max_order_notional: float
    allowed_symbols: list[str]

class AdminRiskConfigResponse(BaseModel):
    kill_switch_active: bool
    max_order_notional: float
    allowed_symbols: list[str]

class SystemHealthResponse(BaseModel):
    status: str
    db_connected: bool
    redis_connected: bool
    celery_queue_depth: int
    broker_latency_ms: dict[str, int]

