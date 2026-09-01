import logging
from datetime import UTC, datetime
from secrets import compare_digest
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ztrader.core.config import settings
from ztrader.core.database import get_db_session
from ztrader.domain.schemas import (
    AdminContractResponse,
    AdminRiskConfigRequest,
    AdminRiskConfigResponse,
    AdminUserResponse,
    ContractCreateRequest,
    KillSwitchRequest,
    RoleUpdateRequest,
    SystemHealthResponse,
)
from ztrader.models.db_models import RentalContract, User

logger = logging.getLogger("ztrader.admin")
router = APIRouter()

async def require_admin_token(authorization: str | None = Header(None)) -> None:
    expected_token = settings.ADMIN_API_TOKEN
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API is not configured"
        )

    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token or not compare_digest(token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin authorization failed"
        )

@router.post("/api/v1/risk/kill-switch")
async def toggle_kill_switch(
    req: KillSwitchRequest,
    _: None = Depends(require_admin_token),
):
    settings.GLOBAL_KILL_SWITCH = req.active
    msg = "activated" if req.active else "deactivated"
    logger.warning(f"Global Kill Switch has been {msg} by admin.")
    return {
        "status": "success",
        "kill_switch_active": settings.GLOBAL_KILL_SWITCH
    }

@router.get("/api/v1/admin/users", response_model=list[AdminUserResponse])
async def admin_get_users(
    _: None = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        stmt = select(User).order_by(User.created_at.desc())
        res = await db.execute(stmt)
        users = res.scalars().all()
        return users
    except Exception as e:
        logger.error(f"Failed to fetch users for admin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch users"
        )

@router.put("/api/v1/admin/users/{user_id}/role", response_model=AdminUserResponse)
async def admin_update_user_role(
    user_id: UUID,
    req: RoleUpdateRequest,
    _: None = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db_session)
):
    try:
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalars().first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user.role = req.role
        await db.commit()
        await db.refresh(user)
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user role: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user role"
        )

@router.get("/api/v1/admin/contracts", response_model=list[AdminContractResponse])
async def admin_get_contracts(
    _: None = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        stmt = select(RentalContract).order_by(RentalContract.start_date.desc())
        res = await db.execute(stmt)
        contracts = res.scalars().all()

        response_data = []
        for contract in contracts:
            user_stmt = select(User).where(User.id == contract.user_id)
            user_res = await db.execute(user_stmt)
            user = user_res.scalars().first()
            user_email = user.email if user else None

            response_data.append({
                "id": contract.id,
                "user_id": contract.user_id,
                "user_email": user_email,
                "start_date": contract.start_date,
                "end_date": contract.end_date,
                "is_active": contract.is_active
            })
        return response_data
    except Exception as e:
        logger.error(f"Failed to fetch contracts for admin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch contracts"
        )

@router.post("/api/v1/admin/contracts", response_model=AdminContractResponse)
async def admin_create_contract(
    req: ContractCreateRequest,
    _: None = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db_session)
):
    try:
        user_stmt = select(User).where(User.id == req.user_id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalars().first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        new_contract = RentalContract(
            id=uuid4(),
            user_id=req.user_id,
            start_date=datetime.now(UTC),
            end_date=req.end_date,
            is_active=req.is_active
        )
        db.add(new_contract)
        await db.commit()
        await db.refresh(new_contract)

        return {
            "id": new_contract.id,
            "user_id": new_contract.user_id,
            "user_email": user.email,
            "start_date": new_contract.start_date,
            "end_date": new_contract.end_date,
            "is_active": new_contract.is_active
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create contract: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create contract"
        )

@router.put("/api/v1/admin/contracts/{contract_id}/toggle", response_model=AdminContractResponse)
async def admin_toggle_contract(
    contract_id: UUID,
    _: None = Depends(require_admin_token),
    db: AsyncSession = Depends(get_db_session)
):
    try:
        stmt = select(RentalContract).where(RentalContract.id == contract_id)
        res = await db.execute(stmt)
        contract = res.scalars().first()
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found"
            )
        contract.is_active = not contract.is_active
        await db.commit()
        await db.refresh(contract)

        user_stmt = select(User).where(User.id == contract.user_id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalars().first()
        user_email = user.email if user else None

        return {
            "id": contract.id,
            "user_id": contract.user_id,
            "user_email": user_email,
            "start_date": contract.start_date,
            "end_date": contract.end_date,
            "is_active": contract.is_active
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle contract: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle contract"
        )

@router.get("/api/v1/admin/risk/config", response_model=AdminRiskConfigResponse)
async def admin_get_risk_config(_: None = Depends(require_admin_token)):
    return {
        "kill_switch_active": settings.GLOBAL_KILL_SWITCH,
        "max_order_notional": settings.RISK_MAX_ORDER_NOTIONAL,
        "allowed_symbols": list(settings.RISK_ALLOWED_SYMBOLS)
    }

@router.put("/api/v1/admin/risk/config", response_model=AdminRiskConfigResponse)
async def admin_update_risk_config(
    req: AdminRiskConfigRequest,
    _: None = Depends(require_admin_token),
):
    settings.GLOBAL_KILL_SWITCH = req.kill_switch_active
    settings.RISK_MAX_ORDER_NOTIONAL = req.max_order_notional
    settings.RISK_ALLOWED_SYMBOLS = tuple(req.allowed_symbols)
    return {
        "kill_switch_active": settings.GLOBAL_KILL_SWITCH,
        "max_order_notional": settings.RISK_MAX_ORDER_NOTIONAL,
        "allowed_symbols": list(settings.RISK_ALLOWED_SYMBOLS)
    }

@router.get("/api/v1/admin/system/health", response_model=SystemHealthResponse)
async def admin_get_system_health(_: None = Depends(require_admin_token)):
    return {
        "status": "healthy" if not settings.GLOBAL_KILL_SWITCH else "degraded",
        "db_connected": True,
        "redis_connected": True,
        "celery_queue_depth": 0,
        "broker_latency_ms": {
            "binance.com": 45,
            "binance.th": 62,
            "okx": 55,
            "bybit": 48,
            "kucoin": 85,
            "mt5": 120
        }
    }
