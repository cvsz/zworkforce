from pydantic import BaseModel, Field
from typing import Optional


class GoogleAuthResponse(BaseModel):
    authorization_url: str


class TickerItem(BaseModel):
    symbol: str
    price: float
    change: float
    changePercent: float


class TickerResponse(BaseModel):
    prices: list[TickerItem]


class PnLResponse(BaseModel):
    total: float
    currency: str = "USDT"


class RiskLimitsResponse(BaseModel):
    max_notional: float
    max_order_notional: float | None = None
    allowed_symbols: list[str]
    live_trading: bool = False


class RiskLimitsUpdate(BaseModel):
    max_notional: float
    allowed_symbols: list[str]
    live_trading: bool = False


class TelegramStatusResponse(BaseModel):
    linked: bool
    chatId: str | None = None
    username: str | None = None
    verified: bool = False


class TelegramLinkRequest(BaseModel):
    user_id: str
    chat_id: str
    username: str | None = None


class TelegramUserIdRequest(BaseModel):
    user_id: str


class NotificationPreferences(BaseModel):
    tradeAlerts: bool = True
    riskAlerts: bool = True
    systemAlerts: bool = True
    dailySummary: bool = False

    trade_alerts: bool = True
    risk_alerts: bool = True
    system_alerts: bool = True
    daily_summary: bool = False


class NotificationPreferencesUpdate(BaseModel):
    user_id: str
    trade_alerts: bool = True
    risk_alerts: bool = True
    system_alerts: bool = True
    daily_summary: bool = True
    tradeAlerts: bool = True
    riskAlerts: bool = True
    systemAlerts: bool = True
    dailySummary: bool = True


class ExchangeInfoResponse(BaseModel):
    exchange: str


class PaymentGenerateRequest(BaseModel):
    amount: float = Field(gt=0)


class PaymentSession(BaseModel):
    id: str
    amount: float
    qr_image_base64: str | None = None
    redirect_url: str | None = None
    promptpay_id: str | None = None
    expires_at: str
    status: str = "pending"


class CandleData(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketCandlesResponse(BaseModel):
    candles: list[CandleData]
