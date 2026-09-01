from fastapi import APIRouter

from ztrader.core.config import settings
from ztrader.domain.schemas import HealthResponse

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "execution_mode": settings.EXECUTION_MODE,
        "live_trading_enabled": settings.LIVE_TRADING_ENABLED,
        "kill_switch_active": settings.GLOBAL_KILL_SWITCH
    }

@router.get("/ready")
async def ready():
    return {"status": "ready"}
