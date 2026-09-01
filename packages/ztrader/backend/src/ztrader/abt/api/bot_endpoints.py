"""// ZeaZDev [Backend API Bot Endpoints] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Omega Scaffolding) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from ztrader.abt.models import BotRun
from ztrader.abt.utils.database import get_db_connection
from ztrader.abt.utils.exceptions import raise_bad_request, raise_not_found
from ztrader.abt.worker.tasks import run_bot_loop

router = APIRouter()


class StartBotInput(BaseModel):
    strategy: str
    symbol: str
    timeframe: str


class StopBotInput(BaseModel):
    bot_id: int


@router.post("/start")
async def start_bot(data: StartBotInput):
    async with get_db_connection() as db:
        bot_run = BotRun(
            userId=1,
            strategy=data.strategy,
            symbol=data.symbol,
            timeframe=data.timeframe,
            status="RUNNING",
        )
        db.add(bot_run)
        await db.flush()
        task = run_bot_loop.delay(bot_run.id)
        return {
            "status": "BOT_STARTED",
            "bot_id": bot_run.id,
            "celery_task_id": task.id,
        }


@router.post("/stop")
async def stop_bot(payload: StopBotInput):
    async with get_db_connection() as db:
        result = await db.execute(select(BotRun).where(BotRun.id == payload.bot_id))
        bot = result.scalar_one_or_none()
        if not bot:
            raise_not_found("Bot not found")
        if bot.status != "RUNNING":
            raise_bad_request("Bot not running")
        bot.status = "STOPPED"
        bot.stoppedAt = datetime.utcnow()
        await db.flush()
        return {"status": "BOT_STOPPED", "bot_id": payload.bot_id}
