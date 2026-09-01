import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status

from ztrader.core.config import settings
from ztrader.domain.platform_schemas import (
    CandleData,
    ExchangeInfoResponse,
    GoogleAuthResponse,
    MarketCandlesResponse,
    NotificationPreferences,
    NotificationPreferencesUpdate,
    PaymentGenerateRequest,
    PaymentSession,
    PnLResponse,
    RiskLimitsResponse,
    RiskLimitsUpdate,
    TelegramLinkRequest,
    TelegramStatusResponse,
    TelegramUserIdRequest,
    TickerItem,
    TickerResponse,
)

logger = logging.getLogger("ztrader.platform")
router = APIRouter()


# ──────────────────────────────────────────
# In-memory stores (replace with DB later)
# ──────────────────────────────────────────

_telegram_links: dict[str, dict[str, Any]] = {}
_notification_prefs: dict[str, dict[str, bool]] = {}
_payment_sessions: dict[str, dict[str, Any]] = {}
_zpoint_balances: dict[str, float] = {}
_exchange_config: dict[str, Any] = {
    "exchange": "binance",
}


# ── Auth ──────────────────────────────────

@router.get("/auth/google/authorize", response_model=GoogleAuthResponse)
async def google_authorize():
    google_client_id = settings.GOOGLE_CLIENT_ID if hasattr(settings, "GOOGLE_CLIENT_ID") else ""
    if not google_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth not configured — set GOOGLE_CLIENT_ID env var",
        )
    redirect_uri = f"{'https' if settings.ENVIRONMENT == 'production' else 'http'}://ztrader.zeaz.dev/auth/google/callback"
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={google_client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=email%20profile"
    )
    return {"authorization_url": auth_url}


# ── Market / Ticker ───────────────────────

_PLACEHOLDER_TICKERS = [
    {"symbol": "BTC/USDT", "price": 0.0, "change": 0.0, "changePercent": 0.0},
    {"symbol": "ETH/USDT", "price": 0.0, "change": 0.0, "changePercent": 0.0},
    {"symbol": "SOL/USDT", "price": 0.0, "change": 0.0, "changePercent": 0.0},
    {"symbol": "BNB/USDT", "price": 0.0, "change": 0.0, "changePercent": 0.0},
    {"symbol": "XRP/USDT", "price": 0.0, "change": 0.0, "changePercent": 0.0},
    {"symbol": "ADA/USDT", "price": 0.0, "change": 0.0, "changePercent": 0.0},
    {"symbol": "DOGE/USDT", "price": 0.0, "change": 0.0, "changePercent": 0.0},
    {"symbol": "DOT/USDT", "price": 0.0, "change": 0.0, "changePercent": 0.0},
]

_ticker_prices: list[dict[str, Any]] = [dict(t) for t in _PLACEHOLDER_TICKERS]


@router.get("/api/v1/ticker/prices", response_model=TickerResponse)
async def ticker_prices():
    return {"prices": [TickerItem(**t) for t in _ticker_prices]}


@router.get("/api/v1/market/candles", response_model=MarketCandlesResponse)
async def market_candles(symbol: str = "BTC/USDT", interval: str = "1h", limit: int = 20):
    now = datetime.now(timezone.utc)
    step = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}.get(interval, 3600)
    candles = []
    for i in range(limit):
        ts = int(now.timestamp()) - (limit - i) * step
        candles.append(CandleData(
            timestamp=datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
            open=50000.0 + (i * 10),
            high=50100.0 + (i * 12),
            low=49900.0 + (i * 8),
            close=50050.0 + (i * 10),
            volume=100.0 + (i * 5),
        ))
    return {"candles": candles}


# ── PnL ───────────────────────────────────

_current_pnl: dict[str, Any] = {"total": 0.0, "currency": "USDT"}


@router.get("/api/v1/pnl", response_model=PnLResponse)
async def pnl():
    return PnLResponse(**_current_pnl)


# ── Risk Limits ───────────────────────────

_risk_limits: dict[str, Any] = {
    "max_notional": settings.RISK_MAX_ORDER_NOTIONAL,
    "allowed_symbols": list(settings.RISK_ALLOWED_SYMBOLS),
    "live_trading": settings.LIVE_TRADING_ENABLED,
}


@router.get("/api/v1/risk/limits", response_model=RiskLimitsResponse)
async def risk_limits():
    return RiskLimitsResponse(
        max_notional=_risk_limits["max_notional"],
        max_order_notional=_risk_limits["max_notional"],
        allowed_symbols=_risk_limits["allowed_symbols"],
        live_trading=_risk_limits["live_trading"],
    )


@router.put("/api/v1/risk/limits", response_model=RiskLimitsResponse)
async def update_risk_limits(req: RiskLimitsUpdate):
    _risk_limits["max_notional"] = req.max_notional
    _risk_limits["allowed_symbols"] = req.allowed_symbols
    _risk_limits["live_trading"] = req.live_trading
    settings.GLOBAL_KILL_SWITCH = not req.live_trading
    return RiskLimitsResponse(
        max_notional=req.max_notional,
        max_order_notional=req.max_notional,
        allowed_symbols=req.allowed_symbols,
        live_trading=req.live_trading,
    )


# ── Exchange Keys ─────────────────────────

@router.get("/api/v1/keys/exchange", response_model=ExchangeInfoResponse)
async def keys_exchange():
    return ExchangeInfoResponse(**_exchange_config)


# ── Telegram ──────────────────────────────

@router.get("/api/v1/telegram/status/{user_id}", response_model=TelegramStatusResponse)
async def telegram_status(user_id: str):
    link = _telegram_links.get(user_id)
    if link:
        return TelegramStatusResponse(
            linked=True, chatId=link.get("chat_id"), username=link.get("username"), verified=True,
        )
    return TelegramStatusResponse(linked=False)


@router.post("/api/v1/telegram/link")
async def telegram_link(req: TelegramLinkRequest):
    _telegram_links[req.user_id] = {
        "chat_id": req.chat_id,
        "username": req.username,
        "linked_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"status": "linked"}


@router.post("/api/v1/telegram/unlink")
async def telegram_unlink(req: TelegramUserIdRequest):
    _telegram_links.pop(req.user_id, None)
    return {"status": "unlinked"}


@router.post("/api/v1/telegram/notify/test")
async def telegram_notify_test(req: TelegramUserIdRequest):
    link = _telegram_links.get(req.user_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Telegram not linked")
    return {"status": "sent"}


# ── Notifications ─────────────────────────

@router.get("/api/v1/user/notifications/preferences/{user_id}", response_model=NotificationPreferences)
async def get_notification_prefs(user_id: str):
    prefs = _notification_prefs.get(user_id)
    if prefs:
        return NotificationPreferences(**prefs)
    return NotificationPreferences()


@router.put("/api/v1/user/notifications/preferences")
async def update_notification_prefs(req: NotificationPreferencesUpdate):
    _notification_prefs[req.user_id] = {
        "tradeAlerts": req.trade_alerts,
        "riskAlerts": req.risk_alerts,
        "systemAlerts": req.system_alerts,
        "dailySummary": req.daily_summary,
        "trade_alerts": req.trade_alerts,
        "risk_alerts": req.risk_alerts,
        "system_alerts": req.system_alerts,
        "daily_summary": req.daily_summary,
    }
    return {"status": "saved"}


# ── Payments ──────────────────────────────

@router.get("/api/v1/payments/zpoint/balance")
async def zpoint_balance():
    return {"balance": _zpoint_balances.get("default", 1000.0)}


@router.post("/api/v1/payments/{method}/generate", response_model=PaymentSession)
async def generate_payment(method: str, req: PaymentGenerateRequest):
    valid_methods = {"promptpay", "truemoney", "shopeepay", "linepay"}
    if method not in valid_methods:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported method: {method}")
    session_id = str(uuid.uuid4())
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    session = {
        "id": session_id,
        "amount": req.amount,
        "qr_image_base64": None,
        "redirect_url": None if method != "linepay" else "https://example.com/linepay/redirect",
        "promptpay_id": f"promptpay-{session_id[:8]}" if method == "promptpay" else None,
        "expires_at": expires_at,
        "status": "pending",
    }
    _payment_sessions[session_id] = session
    return PaymentSession(**session)


@router.get("/api/v1/payments/{method}/status/{session_id}", response_model=PaymentSession)
async def payment_status(method: str, session_id: str):
    session = _payment_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return PaymentSession(**session)
