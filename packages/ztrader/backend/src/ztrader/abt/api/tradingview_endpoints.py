"""// ZeaZDev [Backend TradingView Endpoints] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import json
import os
from datetime import datetime, timezone
from logging import getLogger
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from ztrader.abt.models import TradingViewAlert as TradingViewAlertRecord
from ztrader.abt.services.exchange_service import ExchangeConnector
from ztrader.abt.utils.database import get_db_connection
from ztrader.core.logging_utils import sanitize_log_value

logger = getLogger(__name__)

router = APIRouter()
prisma: Any = None


class TradingViewAlert(BaseModel):
    """TradingView webhook alert payload"""

    ticker: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    exchange: str = Field(default="binance", description="Exchange name")
    action: str = Field(..., description="BUY, SELL, or CLOSE")
    price: Optional[float] = Field(None, description="Alert trigger price")
    strategy: Optional[str] = Field(None, description="Strategy name from TradingView")
    time: Optional[str] = Field(None, description="Alert timestamp")
    message: Optional[str] = Field(None, description="Custom alert message")
    # Additional fields from TradingView
    interval: Optional[str] = Field(None, description="Timeframe interval")
    volume: Optional[float] = Field(None, description="Volume at alert")
    close: Optional[float] = Field(None, description="Close price")
    open: Optional[float] = Field(None, description="Open price")
    high: Optional[float] = Field(None, description="High price")
    low: Optional[float] = Field(None, description="Low price")


class TradingViewWebhookConfig(BaseModel):
    """Configuration for TradingView webhook"""

    user_id: str
    webhook_secret: str
    auto_trade: bool = Field(default=False, description="Automatically execute trades")
    position_size: Optional[float] = Field(
        None, description="Position size in base currency"
    )
    risk_per_trade: Optional[float] = Field(
        default=1.0, description="Risk percentage per trade"
    )


TradingViewAlertPayload = TradingViewAlert


def _model_dump(alert: TradingViewAlert) -> dict[str, Any]:
    """Return a Pydantic v2-compatible dump with a v1 fallback."""
    if hasattr(alert, "model_dump"):
        return alert.model_dump()
    return alert.dict()


def verify_webhook_secret(
    x_webhook_secret: Optional[str] = Header(None),
) -> str:
    """
    Verify TradingView webhook secret from header.

    Args:
        x_webhook_secret: Secret token from TradingView webhook header

    Returns:
        Validated secret

    Raises:
        HTTPException: If secret is missing or invalid
    """
    if not x_webhook_secret:
        raise HTTPException(
            status_code=401,
            detail=(
                "Missing webhook secret. Configure X-Webhook-Secret header "
                "in TradingView."
            ),
        )

    # In production, validate against stored webhook configs
    expected_secret = os.getenv("TRADINGVIEW_WEBHOOK_SECRET")
    if expected_secret and x_webhook_secret != expected_secret:
        logger.warning("Invalid webhook secret received")
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    return x_webhook_secret


async def _connect_prisma_if_needed() -> None:
    if prisma is None:
        return
    is_connected = getattr(prisma, "is_connected", None)
    connect = getattr(prisma, "connect", None)
    if callable(is_connected) and not is_connected() and callable(connect):
        await connect()


def _format_alert(alert: Any) -> dict[str, Any]:
    received_at = getattr(alert, "receivedAt", None)
    return {
        "id": alert.id,
        "ticker": alert.ticker,
        "exchange": alert.exchange,
        "action": alert.action,
        "price": alert.price,
        "strategy": alert.strategy,
        "interval": alert.interval,
        "message": alert.message,
        "received_at": received_at.isoformat() if received_at else None,
    }


@router.post("/webhook")
async def tradingview_webhook(
    alert: TradingViewAlert, webhook_secret: str = Depends(verify_webhook_secret)
):
    """
    Receive TradingView webhook alerts.

    This endpoint receives alerts from TradingView and can:
    1. Log the alert for audit purposes
    2. Trigger automated trading (if configured)
    3. Send notifications via Telegram

    To configure in TradingView:
    1. Create an alert on your chart
    2. In alert settings, set Webhook URL to:
       https://your-domain.com/tradingview/webhook
    3. Add custom header: X-Webhook-Secret: your-secret-key
    4. Use JSON format in alert message with fields like:
       {"ticker": "{{ticker}}", "action": "{{strategy.order.action}}",
        "price": {{close}}, "time": "{{time}}"}

    Args:
        alert: TradingView alert payload
        webhook_secret: Validated webhook secret

    Returns:
        Success message with alert ID
    """
    try:
        # Normalize action to uppercase
        action = alert.action.upper()
        if action not in ["BUY", "SELL", "CLOSE", "HOLD"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action: {action}. Must be BUY, SELL, CLOSE, or HOLD",
            )

        payload = _model_dump(alert)
        alert_data = {
            "ticker": alert.ticker,
            "exchange": alert.exchange,
            "action": action,
            "price": alert.price,
            "strategy": alert.strategy or "TRADINGVIEW_ALERT",
            "interval": alert.interval,
            "volume": alert.volume,
            "message": alert.message,
            "receivedAt": datetime.now(timezone.utc),
            "rawPayload": json.dumps(payload, default=str),
        }

        if prisma is not None:
            await _connect_prisma_if_needed()
            alert_record = await prisma.tradingviewalert.create(data=alert_data)
            return {
                "status": "success",
                "alert_id": alert_record.id,
                "message": f"Alert received: {action} {alert.ticker}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        async with get_db_connection() as db:
            alert_record = TradingViewAlertRecord(**alert_data)
            db.add(alert_record)
            await db.flush()

            logger.info(
                "TradingView alert received: ticker=%s action=%s",
                sanitize_log_value(alert.ticker),
                sanitize_log_value(action),
                extra={
                    "component": "tradingview",
                    "alert_id": alert_record.id,
                    "ticker": sanitize_log_value(alert.ticker),
                    "action": sanitize_log_value(action),
                },
            )

            auto_trade_enabled = os.getenv(
                "AUTO_TRADE_ENABLED", "false"
            ).lower() in ("true", "1", "yes")
            webhook_config = TradingViewWebhookConfig(
                user_id=str(alert_record.id),
                webhook_secret=webhook_secret,
                auto_trade=auto_trade_enabled,
            )

            if webhook_config.auto_trade:
                try:
                    exchange = await ExchangeConnector.for_exchange(
                        db, alert.exchange
                    )
                    order = exchange.create_order(
                        symbol=alert.ticker,
                        type="market",
                        side=action.lower(),
                        amount=webhook_config.position_size or 1.0,
                    )
                    trade_id = (
                        order.get("id")
                        if isinstance(order, dict)
                        else str(order)
                    )
                    logger.info(
                        "Auto-trade executed: action=%s ticker=%s exchange=%s order=%s",
                        sanitize_log_value(action),
                        sanitize_log_value(alert.ticker),
                        sanitize_log_value(alert.exchange),
                        sanitize_log_value(trade_id),
                        extra={
                            "component": "tradingview",
                            "alert_id": alert_record.id,
                            "ticker": sanitize_log_value(alert.ticker),
                            "action": sanitize_log_value(action),
                            "order_id": sanitize_log_value(trade_id),
                        },
                    )
                except Exception as trade_error:
                    logger.error(
                        "Auto-trade failed for ticker=%s",
                        sanitize_log_value(alert.ticker),
                        extra={
                            "component": "tradingview",
                            "alert_id": alert_record.id,
                            "ticker": sanitize_log_value(alert.ticker),
                            "action": sanitize_log_value(action),
                            "error_type": type(trade_error).__name__,
                        },
                    )

            return {
                "status": "success",
                "alert_id": alert_record.id,
                "message": f"Alert received: {action} {alert.ticker}",
                "timestamp": datetime.utcnow().isoformat(),
            }
    except HTTPException:
        raise
    except Exception as error:
        logger.error(
            "Error processing TradingView alert",
            extra={
                "component": "tradingview",
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to process alert",
        ) from None


@router.get("/alerts")
async def list_tradingview_alerts(
    limit: int = Query(50, ge=1, le=500),
    ticker: Optional[str] = None,
    action: Optional[str] = None,
):
    """
    List recent TradingView alerts.

    Args:
        limit: Maximum number of alerts to return (default 50)
        ticker: Filter by ticker symbol
        action: Filter by action (BUY, SELL, CLOSE)

    Returns:
        List of TradingView alerts
    """
    try:
        if prisma is not None:
            await _connect_prisma_if_needed()
            where: dict[str, Any] = {}
            if ticker:
                where["ticker"] = ticker
            if action:
                where["action"] = action.upper()
            alerts = await prisma.tradingviewalert.find_many(
                where=where or None,
                order={"receivedAt": "desc"},
                take=limit,
            )
            return {
                "alerts": [_format_alert(alert) for alert in alerts],
                "count": len(alerts),
            }

        async with get_db_connection() as db:
            query = select(TradingViewAlertRecord)
            if ticker:
                query = query.where(TradingViewAlertRecord.ticker == ticker)
            if action:
                query = query.where(TradingViewAlertRecord.action == action.upper())
            query = query.order_by(TradingViewAlertRecord.receivedAt.desc()).limit(limit)

            result = await db.execute(query)
            alerts = result.scalars().all()

            return {
                "alerts": [
                    _format_alert(alert)
                    for alert in alerts
                ],
                "count": len(alerts),
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching TradingView alerts: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch alerts: {str(e)}"
        ) from e


@router.get("/config")
async def get_webhook_config():
    """
    Get TradingView webhook configuration instructions.

    Returns:
        Configuration guide and webhook URL
    """
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    webhook_url = f"{base_url}/tradingview/webhook"

    return {
        "webhook_url": webhook_url,
        "setup_instructions": {
            "step_1": "Create an alert in TradingView on your desired chart/indicator",
            "step_2": f"Set Webhook URL to: {webhook_url}",
            "step_3": "Add custom header: X-Webhook-Secret: your-secret-key",
            "step_4": "Configure alert message in JSON format",
            "example_message": {
                "ticker": "{{ticker}}",
                "action": "BUY",
                "price": "{{close}}",
                "time": "{{time}}",
                "interval": "{{interval}}",
                "strategy": "My TradingView Strategy",
            },
            "supported_actions": ["BUY", "SELL", "CLOSE", "HOLD"],
        },
        "environment_variables": {
            "TRADINGVIEW_WEBHOOK_SECRET": (
                "Set this in your .env file for webhook authentication"
            )
        },
    }
