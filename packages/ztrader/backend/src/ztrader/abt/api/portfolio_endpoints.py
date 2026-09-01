"""// ZeaZDev [Portfolio API Endpoints] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 4) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ztrader.abt.services.portfolio_service import PortfolioService
from ztrader.abt.utils.dependencies import get_current_user_id
from ztrader.abt.utils.exceptions import handle_service_error

router = APIRouter()
portfolio_service = PortfolioService()


class CreateAccountRequest(BaseModel):
    exchange_key_id: int
    label: str
    group: Optional[str] = None


@router.get("/summary")
async def get_portfolio_summary(user_id: int = Depends(get_current_user_id)):
    """Get aggregated portfolio summary"""
    try:
        summary = await portfolio_service.get_portfolio_summary(user_id)
        return summary
    except Exception as e:
        handle_service_error(e)


@router.get("/accounts")
async def list_accounts(user_id: int = Depends(get_current_user_id)):
    """List all accounts"""
    try:
        accounts = await portfolio_service.list_accounts(user_id)
        return {"accounts": accounts, "count": len(accounts)}
    except Exception as e:
        handle_service_error(e)


@router.post("/accounts")
async def create_account(
    request: CreateAccountRequest, user_id: int = Depends(get_current_user_id)
):
    """Create a new account"""
    try:
        account = await portfolio_service.create_account(
            user_id=user_id,
            exchange_key_id=request.exchange_key_id,
            label=request.label,
            group=request.group,
        )
        return account
    except Exception as e:
        handle_service_error(e)


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, user_id: int = Depends(get_current_user_id)):
    """Delete an account"""
    try:
        result = await portfolio_service.delete_account(account_id, user_id)
        return result
    except Exception as e:
        handle_service_error(e)


@router.post("/accounts/{account_id}/sync")
async def sync_account_positions(account_id: int):
    """Sync positions from exchange"""
    try:
        positions = await portfolio_service.sync_account_positions(account_id)
        return {"positions": positions, "count": len(positions)}
    except Exception as e:
        handle_service_error(e)


@router.get("/accounts/{account_id}/performance")
async def get_account_performance(account_id: int):
    """Get performance metrics for an account"""
    try:
        performance = await portfolio_service.get_account_performance(account_id)
        return performance
    except Exception as e:
        handle_service_error(e)
