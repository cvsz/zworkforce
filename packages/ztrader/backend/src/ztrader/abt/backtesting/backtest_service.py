"""// ZeaZDev [Backtest Service] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 4) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ztrader.abt.models import BacktestRun, PaperTradingSession

logger = logging.getLogger(__name__)


class BacktestService:
    """Service for running backtests and paper trading sessions"""

    def __init__(self):
        self._initialized = True

    async def create_backtest(
        self,
        db: AsyncSession,
        user_id: int,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float = 10000.0,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new backtest run"""
        backtest = BacktestRun(
            userId=user_id,
            strategyName=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            startDate=start_date,
            endDate=end_date,
            initialCapital=initial_capital,
            status="PENDING",
            results=json.dumps({"parameters": parameters or {}}),
        )
        db.add(backtest)
        await db.flush()

        return {
            "backtest_id": backtest.id,
            "status": backtest.status,
            "created_at": backtest.createdAt.isoformat(),
        }

    async def run_backtest(self, db: AsyncSession, backtest_id: int) -> Dict[str, Any]:
        """
        Execute a backtest (simplified version)
        In production, this would run in a Celery task
        """
        result = await db.execute(select(BacktestRun).where(BacktestRun.id == backtest_id))
        backtest = result.scalar_one_or_none()

        if not backtest:
            raise ValueError(f"Backtest {backtest_id} not found")

        backtest.status = "RUNNING"
        await db.flush()

        results = self._generate_mock_backtest_results(
            backtest.initialCapital, backtest.symbol
        )

        backtest.status = "COMPLETED"
        backtest.results = json.dumps(results)
        backtest.completedAt = datetime.utcnow()
        await db.flush()

        return {
            "backtest_id": backtest_id,
            "status": "COMPLETED",
            "results": results,
        }

    def _generate_mock_backtest_results(
        self, initial_capital: float, symbol: str
    ) -> Dict[str, Any]:
        """Generate mock backtest results for demonstration"""
        # Simulate some trades
        num_trades = np.random.randint(50, 200)
        win_rate = np.random.uniform(0.45, 0.65)

        winning_trades = int(num_trades * win_rate)
        losing_trades = num_trades - winning_trades

        # Calculate final capital (simple simulation)
        avg_win = initial_capital * 0.02  # 2% avg win
        avg_loss = initial_capital * 0.015  # 1.5% avg loss

        total_profit = (winning_trades * avg_win) - (losing_trades * avg_loss)
        final_capital = initial_capital + total_profit

        total_return = ((final_capital - initial_capital) / initial_capital) * 100

        # Calculate max drawdown (mock)
        max_drawdown = np.random.uniform(5, 25)

        # Calculate Sharpe ratio (mock)
        sharpe_ratio = np.random.uniform(0.5, 2.5)

        # Profit factor
        gross_profit = winning_trades * avg_win
        gross_loss = losing_trades * avg_loss
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        return {
            "initial_capital": initial_capital,
            "final_capital": round(final_capital, 2),
            "total_return": round(total_return, 2),
            "total_trades": num_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate * 100, 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "profit_factor": round(profit_factor, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
        }

    async def get_backtest_results(self, db: AsyncSession, backtest_id: int) -> Dict[str, Any]:
        """Get backtest results"""
        result = await db.execute(select(BacktestRun).where(BacktestRun.id == backtest_id))
        backtest = result.scalar_one_or_none()

        if not backtest:
            raise ValueError(f"Backtest {backtest_id} not found")

        results = json.loads(backtest.results) if backtest.results else {}

        return {
            "backtest_id": backtest.id,
            "strategy_name": backtest.strategyName,
            "symbol": backtest.symbol,
            "timeframe": backtest.timeframe,
            "start_date": backtest.startDate.isoformat(),
            "end_date": backtest.endDate.isoformat(),
            "status": backtest.status,
            "created_at": backtest.createdAt.isoformat(),
            "completed_at": (
                backtest.completedAt.isoformat() if backtest.completedAt else None
            ),
            "results": results,
        }

    async def list_user_backtests(
        self, db: AsyncSession, user_id: int, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List all backtests for a user"""
        result = await db.execute(
            select(BacktestRun)
            .where(BacktestRun.userId == user_id)
            .order_by(BacktestRun.createdAt.desc())
            .limit(limit)
        )
        backtests = result.scalars().all()

        return [
            {
                "backtest_id": bt.id,
                "strategy_name": bt.strategyName,
                "symbol": bt.symbol,
                "timeframe": bt.timeframe,
                "status": bt.status,
                "created_at": bt.createdAt.isoformat(),
            }
            for bt in backtests
        ]

    async def delete_backtest(self, db: AsyncSession, backtest_id: int, user_id: int) -> Dict[str, Any]:
        """Delete a backtest"""
        result = await db.execute(
            select(BacktestRun).where(BacktestRun.id == backtest_id, BacktestRun.userId == user_id)
        )
        backtest = result.scalar_one_or_none()

        if not backtest:
            raise ValueError("Backtest not found or does not belong to user")

        await db.execute(delete(BacktestRun).where(BacktestRun.id == backtest_id))

        return {"success": True, "backtest_id": backtest_id}

    # Paper Trading Methods

    async def start_paper_trading(
        self,
        db: AsyncSession,
        user_id: int,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        virtual_balance: float = 10000.0,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Start a paper trading session"""
        session = PaperTradingSession(
            userId=user_id,
            strategyName=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            virtualBalance=virtual_balance,
            currentBalance=virtual_balance,
            status="ACTIVE",
        )
        db.add(session)
        await db.flush()

        return {
            "session_id": session.id,
            "strategy_name": strategy_name,
            "symbol": symbol,
            "virtual_balance": virtual_balance,
            "status": session.status,
            "started_at": session.startedAt.isoformat(),
        }

    async def stop_paper_trading(self, db: AsyncSession, session_id: int, user_id: int) -> Dict[str, Any]:
        """Stop a paper trading session"""
        result = await db.execute(
            select(PaperTradingSession).where(
                PaperTradingSession.id == session_id,
                PaperTradingSession.userId == user_id,
            )
        )
        session = result.scalar_one_or_none()

        if not session:
            raise ValueError(
                "Paper trading session not found or does not belong to user"
            )

        session.status = "STOPPED"
        session.stoppedAt = datetime.utcnow()
        await db.flush()

        pnl = (
            session.currentBalance or session.virtualBalance
        ) - session.virtualBalance
        return_pct = (pnl / session.virtualBalance) * 100

        return {
            "session_id": session_id,
            "status": "STOPPED",
            "initial_balance": session.virtualBalance,
            "final_balance": session.currentBalance
            or session.virtualBalance,
            "pnl": round(pnl, 2),
            "return_pct": round(return_pct, 2),
            "stopped_at": (
                session.stoppedAt.isoformat()
                if session.stoppedAt
                else None
            ),
        }

    async def get_paper_trading_status(self, db: AsyncSession, session_id: int) -> Dict[str, Any]:
        """Get status of a paper trading session"""
        result = await db.execute(
            select(PaperTradingSession).where(PaperTradingSession.id == session_id)
        )
        session = result.scalar_one_or_none()

        if not session:
            raise ValueError(f"Paper trading session {session_id} not found")

        pnl = (
            session.currentBalance or session.virtualBalance
        ) - session.virtualBalance
        return_pct = (pnl / session.virtualBalance) * 100

        return {
            "session_id": session.id,
            "strategy_name": session.strategyName,
            "symbol": session.symbol,
            "timeframe": session.timeframe,
            "status": session.status,
            "initial_balance": session.virtualBalance,
            "current_balance": session.currentBalance or session.virtualBalance,
            "pnl": round(pnl, 2),
            "return_pct": round(return_pct, 2),
            "started_at": session.startedAt.isoformat(),
            "stopped_at": (
                session.stoppedAt.isoformat() if session.stoppedAt else None
            ),
        }

    async def list_paper_trading_sessions(
        self, db: AsyncSession, user_id: int, active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """List paper trading sessions for a user"""
        stmt = select(PaperTradingSession).where(PaperTradingSession.userId == user_id)
        if active_only:
            stmt = stmt.where(PaperTradingSession.status == "ACTIVE")
        stmt = stmt.order_by(PaperTradingSession.startedAt.desc())

        result = await db.execute(stmt)
        sessions = result.scalars().all()

        return [
            {
                "session_id": s.id,
                "strategy_name": s.strategyName,
                "symbol": s.symbol,
                "status": s.status,
                "virtual_balance": s.virtualBalance,
                "current_balance": s.currentBalance or s.virtualBalance,
                "started_at": s.startedAt.isoformat(),
            }
            for s in sessions
        ]
