"""// ZeaZDev [Portfolio Service] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 4) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import ccxt
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ztrader.abt.models import Account, ExchangeKey, Position, TradeLog, BotRun
from ztrader.core.crypto_service import decrypt_data

logger = logging.getLogger(__name__)


class PortfolioService:
    """Service for aggregating and managing multi-account portfolios"""

    def __init__(self):
        self.exchanges_cache: Dict[int, ccxt.Exchange] = {}

    async def create_account(
        self,
        db: AsyncSession,
        user_id: int,
        exchange_key_id: int,
        label: str,
        group: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new account for portfolio tracking"""
        # Verify exchange key exists and belongs to user
        result = await db.execute(
            select(ExchangeKey).where(
                ExchangeKey.id == exchange_key_id, ExchangeKey.ownerId == user_id
            )
        )
        exchange_key = result.scalar_one_or_none()

        if not exchange_key:
            raise ValueError("Exchange key not found or does not belong to user")

        # Create account
        account = Account(
            userId=user_id,
            exchangeKeyId=exchange_key_id,
            label=label,
            group=group,
            enabled=True,
        )
        db.add(account)
        await db.flush()

        return {
            "id": account.id,
            "label": account.label,
            "exchange": exchange_key.exchange,
            "group": account.group,
            "enabled": account.enabled,
        }

    async def list_accounts(
        self, db: AsyncSession, user_id: int
    ) -> List[Dict[str, Any]]:
        """List all accounts for a user"""
        result = await db.execute(
            select(Account)
            .where(Account.userId == user_id)
            .options(selectinload(Account.exchangeKey))
        )
        accounts = result.scalars().all()

        return [
            {
                "id": acc.id,
                "label": acc.label,
                "exchange": acc.exchangeKey.exchange,
                "group": acc.group,
                "enabled": acc.enabled,
                "created_at": acc.createdAt.isoformat(),
            }
            for acc in accounts
        ]

    async def sync_account_positions(
        self, db: AsyncSession, account_id: int
    ) -> List[Dict[str, Any]]:
        """Sync positions from exchange for a specific account"""
        # Get account with exchange key
        result = await db.execute(
            select(Account)
            .where(Account.id == account_id)
            .options(selectinload(Account.exchangeKey))
        )
        account = result.scalar_one_or_none()

        if not account or not account.enabled:
            return []

        # Get or create exchange instance
        exchange = await self._get_exchange_instance(account.exchangeKey)

        # Fetch positions from exchange
        try:
            balance = await asyncio.to_thread(exchange.fetch_balance)
            positions = []

            for symbol, amount in balance["total"].items():
                if amount > 0:
                    # Try to get current price
                    try:
                        ticker_symbol = f"{symbol}/USDT"
                        ticker = await asyncio.to_thread(
                            exchange.fetch_ticker, ticker_symbol
                        )
                        current_price = ticker["last"]
                    except Exception as e:
                        logger.debug(f"Ticker fetch failed for {symbol}: {e}")
                        current_price = None

                    # Update or create position in database
                    pos_result = await db.execute(
                        select(Position).where(
                            Position.accountId == account_id,
                            Position.symbol == symbol,
                        )
                    )
                    existing = pos_result.scalar_one_or_none()

                    if existing:
                        existing.quantity = amount
                        existing.currentPrice = current_price
                    else:
                        position = Position(
                            accountId=account_id,
                            symbol=symbol,
                            side="LONG",
                            quantity=amount,
                            entryPrice=current_price or 0,
                            currentPrice=current_price,
                        )
                        db.add(position)

                    positions.append(
                        {
                            "symbol": symbol,
                            "quantity": amount,
                            "current_price": current_price,
                        }
                    )

            await db.flush()
            return positions
        except Exception as e:
            logger.error(f"Failed to sync positions for account {account_id}: {e}")
            return []

    async def get_portfolio_summary(
        self, db: AsyncSession, user_id: int
    ) -> Dict[str, Any]:
        """Get aggregated portfolio summary across all accounts"""
        # Get all enabled accounts
        result = await db.execute(
            select(Account)
            .where(Account.userId == user_id, Account.enabled == True)
            .options(selectinload(Account.positions), selectinload(Account.exchangeKey))
        )
        accounts = result.scalars().all()

        # Aggregate positions
        aggregated_positions: Dict[str, Dict[str, Any]] = {}
        total_value_usd = 0.0

        for account in accounts:
            for position in account.positions:
                symbol = position.symbol

                if symbol not in aggregated_positions:
                    aggregated_positions[symbol] = {
                        "symbol": symbol,
                        "total_quantity": 0.0,
                        "accounts": [],
                    }

                aggregated_positions[symbol]["total_quantity"] += position.quantity
                aggregated_positions[symbol]["accounts"].append(
                    {
                        "account_id": account.id,
                        "account_label": account.label,
                        "quantity": position.quantity,
                        "current_price": position.currentPrice,
                    }
                )

                # Add to total value
                if position.currentPrice:
                    total_value_usd += position.quantity * position.currentPrice

        # Get total PnL from trade logs
        txn_result = await db.execute(
            select(TradeLog).join(TradeLog.botRun).where(BotRun.userId == user_id)
        )
        trade_logs = txn_result.scalars().all()
        total_pnl = sum(t.pnl for t in trade_logs)

        return {
            "total_accounts": len(accounts),
            "total_positions": len(aggregated_positions),
            "total_value_usd": round(total_value_usd, 2),
            "total_pnl": round(total_pnl, 4),
            "positions": list(aggregated_positions.values()),
            "last_updated": datetime.utcnow().isoformat(),
        }

    async def get_account_performance(
        self, db: AsyncSession, account_id: int
    ) -> Dict[str, Any]:
        """Get performance metrics for a specific account"""
        # Get account positions
        result = await db.execute(
            select(Position).where(Position.accountId == account_id)
        )
        positions = result.scalars().all()

        # Calculate metrics
        total_positions = len(positions)
        total_pnl = sum(p.pnl for p in positions)

        # Get account value
        account_value = sum(p.quantity * (p.currentPrice or 0) for p in positions)

        return {
            "account_id": account_id,
            "total_positions": total_positions,
            "account_value_usd": round(account_value, 2),
            "total_pnl": round(total_pnl, 4),
            "positions": [
                {
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "entry_price": p.entryPrice,
                    "current_price": p.currentPrice,
                    "pnl": p.pnl,
                }
                for p in positions
            ],
        }

    async def _get_exchange_instance(self, exchange_key) -> ccxt.Exchange:
        """Get or create CCXT exchange instance"""
        if exchange_key.id in self.exchanges_cache:
            return self.exchanges_cache[exchange_key.id]

        # Decrypt keys
        api_key = decrypt_data(exchange_key.encrypted_key, exchange_key.iv_key)
        api_secret = decrypt_data(exchange_key.encrypted_secret, exchange_key.iv_secret)

        # Create exchange instance
        exchange_class = getattr(ccxt, exchange_key.exchange)
        exchange = exchange_class(
            {"apiKey": api_key, "secret": api_secret, "enableRateLimit": True}
        )

        # Cache instance
        self.exchanges_cache[exchange_key.id] = exchange

        return exchange

    async def delete_account(
        self, db: AsyncSession, account_id: int, user_id: int
    ) -> Dict[str, Any]:
        """Delete an account and its positions"""
        # Verify account belongs to user
        result = await db.execute(
            select(Account).where(
                Account.id == account_id, Account.userId == user_id
            )
        )
        account = result.scalar_one_or_none()

        if not account:
            raise ValueError("Account not found or does not belong to user")

        # Delete all positions for this account
        await db.execute(delete(Position).where(Position.accountId == account_id))

        # Delete account
        await db.execute(delete(Account).where(Account.id == account_id))

        return {"success": True, "account_id": account_id}
