import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ztrader.core.config import settings
from ztrader.core.database import get_db_session
from ztrader.core.logging_utils import sanitize_log_value
from ztrader.core.security import encryptor
from ztrader.domain.schemas import (
    AuditLogResponse,
    BacktestRequest,
    BacktestResponse,
    BotStartRequest,
    BotStatusResponse,
    KeyRegisterRequest,
    OrderResponse,
)
from ztrader.engine.backtest import BacktestEngine
from ztrader.engine.strategy import (
    MovingAverageCrossoverStrategy,
    PositionStrategy,
    ScalpStrategy,
    SwingStrategy,
)
from ztrader.strategies.tradingagents_strategy import TradingAgentsLLMStrategy
from ztrader.models.db_models import AuditLog as DBAuditLog
from ztrader.models.db_models import ExchangeKey, User
from ztrader.models.db_models import Order as DBOrder

logger = logging.getLogger("ztrader.trading")
router = APIRouter()

ACTIVE_BOTS: dict[str, dict[str, Any]] = {}

@router.post("/api/v1/backtest/run", response_model=BacktestResponse)
async def run_backtest(req: BacktestRequest):
    supported_strategies = ["ma-crossover", "scalp", "swing", "position", "tradingagents"]
    if req.strategy_name not in supported_strategies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported strategy: {req.strategy_name}. Supported: {supported_strategies}"
        )

    try:
        if req.strategy_name == "ma-crossover":
            strategy = MovingAverageCrossoverStrategy(
                symbol=req.symbol,
                fast=req.fast_period,
                slow=req.slow_period,
                notional=req.notional
            )
        elif req.strategy_name == "scalp":
            strategy = ScalpStrategy(symbol=req.symbol, notional=req.notional)
        elif req.strategy_name == "swing":
            strategy = SwingStrategy(symbol=req.symbol, notional=req.notional)
        elif req.strategy_name == "position":
            strategy = PositionStrategy(symbol=req.symbol, notional=req.notional)
        elif req.strategy_name == "tradingagents":
            strategy = TradingAgentsLLMStrategy(
                symbol=req.symbol,
                notional=req.notional,
                llm_provider=settings.TRADINGAGENTS_LLM_PROVIDER,
            )

        engine = BacktestEngine(allowed_symbols=settings.RISK_ALLOWED_SYMBOLS)
        result = engine.run(strategy, req.candles)
        return {
            "strategy_id": result.strategy_id,
            "candles_seen": result.candles_seen,
            "orders_created": result.orders_created,
            "ending_usdt": result.ending_usdt,
            "ending_btc": result.ending_btc
        }
    except Exception as e:
        logger.error(f"Backtest execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backtest failed: {str(e)}"
        )

@router.get("/api/v1/orders", response_model=list[OrderResponse])
async def get_orders(limit: int = 50, db: AsyncSession = Depends(get_db_session)):
    try:
        stmt = select(DBOrder).order_by(DBOrder.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        orders = result.scalars().all()
        return orders
    except Exception as e:
        logger.error(f"Failed to query orders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed"
        )

@router.get("/api/v1/audit/logs", response_model=list[AuditLogResponse])
async def get_audit_logs(limit: int = 50, db: AsyncSession = Depends(get_db_session)):
    try:
        stmt = select(DBAuditLog).order_by(DBAuditLog.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        logs = result.scalars().all()
        return logs
    except Exception as e:
        logger.error(f"Failed to query audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed"
        )

@router.post("/api/v1/bot/start", response_model=BotStatusResponse)
async def start_bot(req: BotStartRequest):
    if settings.GLOBAL_KILL_SWITCH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System is currently in a safe state (Global Kill Switch active). Trading prohibited."
        )

    bot_id = f"bot-{req.strategy_name}-{req.symbol.replace('/', '-')}"

    if bot_id in ACTIVE_BOTS and ACTIVE_BOTS[bot_id]["active"]:
        return {
            "bot_id": bot_id,
            "strategy_name": req.strategy_name,
            "symbol": req.symbol,
            "active": True,
            "execution_mode": settings.EXECUTION_MODE
        }

    ACTIVE_BOTS[bot_id] = {
        "strategy_name": req.strategy_name,
        "symbol": req.symbol,
        "active": True,
        "params": req.model_dump() if hasattr(req, "model_dump") else req.dict()
    }

    logger.info(
        "Bot %s started in mode %s",
        sanitize_log_value(bot_id),
        sanitize_log_value(settings.EXECUTION_MODE),
    )
    return {
        "bot_id": bot_id,
        "strategy_name": req.strategy_name,
        "symbol": req.symbol,
        "active": True,
        "execution_mode": settings.EXECUTION_MODE
    }

@router.post("/api/v1/bot/stop")
async def stop_bot(bot_id: str):
    if bot_id not in ACTIVE_BOTS or not ACTIVE_BOTS[bot_id]["active"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active bot {bot_id} not found"
        )

    ACTIVE_BOTS[bot_id]["active"] = False
    logger.info("Bot %s stopped", sanitize_log_value(bot_id))
    return {"status": "stopped", "bot_id": bot_id}

@router.get("/api/v1/bot/status", response_model=list[BotStatusResponse])
async def get_bot_status():
    res = []
    for bot_id, info in ACTIVE_BOTS.items():
        res.append({
            "bot_id": bot_id,
            "strategy_name": info["strategy_name"],
            "symbol": info["symbol"],
            "active": info["active"],
            "execution_mode": settings.EXECUTION_MODE
        })
    return res

@router.post("/api/v1/keys")
async def register_keys(req: KeyRegisterRequest, db: AsyncSession = Depends(get_db_session)):
    try:
        user_stmt = select(User).limit(1)
        user_res = await db.execute(user_stmt)
        user = user_res.scalars().first()
        if not user:
            user = User(email="test-operator@zeaz.dev", name="Test Operator", role="operator")
            db.add(user)
            await db.commit()
            await db.refresh(user)

        encrypted_key = encryptor.encrypt(req.api_key)
        encrypted_secret = encryptor.encrypt(req.api_secret)

        key_stmt = select(ExchangeKey).where(
            ExchangeKey.user_id == user.id,
            ExchangeKey.exchange == req.exchange
        )
        key_res = await db.execute(key_stmt)
        existing_key = key_res.scalars().first()

        if existing_key:
            existing_key.encrypted_key = encrypted_key
            existing_key.encrypted_secret = encrypted_secret
            existing_key.passphrase = req.passphrase
        else:
            new_key = ExchangeKey(
                user_id=user.id,
                exchange=req.exchange,
                encrypted_key=encrypted_key,
                encrypted_secret=encrypted_secret,
                passphrase=req.passphrase
            )
            db.add(new_key)

        await db.commit()
        return {"status": "success", "message": "Keys saved securely (AES-256 encrypted)"}
    except Exception as e:
        logger.error(f"Failed to register API keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Key registration failed: {str(e)}"
        )
