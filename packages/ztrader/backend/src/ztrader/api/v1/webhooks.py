import json
import logging
import os

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ztrader.core.database import get_db_session
from ztrader.domain.schemas import TradingViewAlertPayload, TradingViewAlertResponse
from ztrader.models.db_models import TradingViewAlert

logger = logging.getLogger("ztrader.webhooks")
router = APIRouter()

import hmac

@router.post("/api/v1/tradingview/webhook")
async def tradingview_webhook(
    alert: TradingViewAlertPayload,
    x_webhook_secret: str | None = Header(None),
    db: AsyncSession = Depends(get_db_session)
):
    expected_secret = os.environ.get("TRADINGVIEW_WEBHOOK_SECRET")
    provided_secret = x_webhook_secret or alert.secret

    if expected_secret:
        if not provided_secret or not hmac.compare_digest(provided_secret, expected_secret):
            logger.warning("Unauthenticated TradingView webhook alert received")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid webhook secret token"
            )

    action_upper = alert.action.upper()
    if action_upper not in ["BUY", "SELL", "CLOSE"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: {action_upper}. Must be BUY, SELL, or CLOSE"
        )

    symbol = alert.resolved_symbol

    try:
        alert_log = TradingViewAlert(
            ticker=symbol,
            exchange=alert.exchange,
            action=action_upper,
            price=alert.price,
            strategy=alert.strategy or "TRADINGVIEW_ALERT",
            interval=alert.interval,
            volume=alert.volume,
            message=alert.message,
            raw_payload=alert.model_dump_json() if hasattr(alert, "model_dump_json") else json.dumps(alert.dict())
        )

        db.add(alert_log)
        await db.commit()
        await db.refresh(alert_log)

        logger.info(f"TradingView Alert stored successfully: {alert_log.id}")
        return {
            "status": "success",
            "accepted": True,
            "alert_id": alert_log.id,
            "symbol": symbol,
            "message": f"TradingView alert received: {action_upper} {symbol}"
        }
    except Exception as e:
        logger.error(f"Failed to record TradingView alert: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record alert: {str(e)}"
        )

@router.get("/api/v1/tradingview/alerts", response_model=list[TradingViewAlertResponse])
async def get_tradingview_alerts(
    limit: int = 50,
    db: AsyncSession = Depends(get_db_session)
):
    try:
        stmt = select(TradingViewAlert).order_by(TradingViewAlert.received_at.desc()).limit(limit)
        res = await db.execute(stmt)
        return res.scalars().all()
    except Exception as e:
        logger.error(f"Failed to fetch TradingView alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed"
        )

@router.get("/api/v1/tradingview/config")
async def get_tradingview_config():
    return {
        "webhook_url": "http://localhost:8000/api/v1/tradingview/webhook",
        "instructions": "Set the Webhook URL in TradingView alert settings and use the provided JSON payload format.",
        "payload_schema": {
            "type": "POST",
            "header": "X-Webhook-Secret",
            "body_format": "JSON",
            "example": {
                "ticker": "{{ticker}}",
                "exchange": "{{exchange}}",
                "action": "BUY",
                "price": 65000.0,
                "strategy": "MA-Crossover-Indicator"
            }
        }
    }
