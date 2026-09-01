"""// ZeaZDev [Backtest API Endpoints] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 4) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ztrader.abt.backtesting.backtest_service import BacktestService
from ztrader.abt.utils.dependencies import get_current_user_id
from ztrader.abt.utils.exceptions import handle_service_error

router = APIRouter()
backtest_service = BacktestService()


class BacktestRequest(BaseModel):
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: str  # ISO format
    end_date: str  # ISO format
    initial_capital: float = 10000.0
    parameters: Optional[Dict[str, Any]] = None


class PaperTradingRequest(BaseModel):
    strategy_name: str
    symbol: str
    timeframe: str
    virtual_balance: float = 10000.0
    parameters: Optional[Dict[str, Any]] = None


class StopPaperTradingRequest(BaseModel):
    session_id: int


@router.post("/run")
async def create_backtest(
    request: BacktestRequest, user_id: int = Depends(get_current_user_id)
):
    """Create and run a backtest"""
    try:
        # Parse dates
        start_date = datetime.fromisoformat(request.start_date.replace("Z", "+00:00"))
        end_date = datetime.fromisoformat(request.end_date.replace("Z", "+00:00"))

        # Create backtest
        backtest = await backtest_service.create_backtest(
            user_id=user_id,
            strategy_name=request.strategy_name,
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=request.initial_capital,
            parameters=request.parameters,
        )

        # Run backtest (in production, this would be queued in Celery)
        result = await backtest_service.run_backtest(backtest["backtest_id"])

        return result
    except Exception as e:
        handle_service_error(e)


@router.get("/runs")
async def list_backtests(user_id: int = Depends(get_current_user_id), limit: int = 50):
    """List all backtest runs"""
    try:
        backtests = await backtest_service.list_user_backtests(user_id, limit)
        return {"backtests": backtests, "count": len(backtests)}
    except Exception as e:
        handle_service_error(e)


@router.get("/runs/{run_id}")
async def get_backtest_results(run_id: int):
    """Get backtest results"""
    try:
        results = await backtest_service.get_backtest_results(run_id)
        return results
    except Exception as e:
        handle_service_error(e)


@router.delete("/runs/{run_id}")
async def delete_backtest(run_id: int, user_id: int = Depends(get_current_user_id)):
    """Delete a backtest run"""
    try:
        result = await backtest_service.delete_backtest(run_id, user_id)
        return result
    except Exception as e:
        handle_service_error(e)


# Paper Trading Endpoints


@router.post("/paper/start")
async def start_paper_trading(
    request: PaperTradingRequest, user_id: int = Depends(get_current_user_id)
):
    """Start a paper trading session"""
    try:
        session = await backtest_service.start_paper_trading(
            user_id=user_id,
            strategy_name=request.strategy_name,
            symbol=request.symbol,
            timeframe=request.timeframe,
            virtual_balance=request.virtual_balance,
            parameters=request.parameters,
        )
        return session
    except Exception as e:
        handle_service_error(e)


@router.post("/paper/stop")
async def stop_paper_trading(
    request: StopPaperTradingRequest, user_id: int = Depends(get_current_user_id)
):
    """Stop a paper trading session"""
    try:
        result = await backtest_service.stop_paper_trading(request.session_id, user_id)
        return result
    except Exception as e:
        handle_service_error(e)


@router.get("/paper/status/{session_id}")
async def get_paper_trading_status(session_id: int):
    """Get paper trading session status"""
    try:
        status = await backtest_service.get_paper_trading_status(session_id)
        return status
    except Exception as e:
        handle_service_error(e)


@router.get("/paper/sessions")
async def list_paper_trading_sessions(
    user_id: int = Depends(get_current_user_id), active_only: bool = False
):
    """List paper trading sessions"""
    try:
        sessions = await backtest_service.list_paper_trading_sessions(
            user_id, active_only
        )
        return {"sessions": sessions, "count": len(sessions)}
    except Exception as e:
        handle_service_error(e)
