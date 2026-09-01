"""// ZeaZDev [Notification Service] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 3) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ztrader.abt.models import NotificationPreference, TelegramLink

from .telegram_service import TelegramService


class NotificationService:
    """Service for sending notifications to users via various channels"""

    def __init__(self):
        self.telegram_service = TelegramService()

    async def send_trade_notification(
        self, db: AsyncSession, user_id: int, trade_data: Dict[str, Any]
    ) -> bool:
        """Send trade execution notification"""
        # Check if user has enabled trade alerts
        result = await db.execute(
            select(NotificationPreference).where(NotificationPreference.userId == user_id)
        )
        prefs = result.scalar_one_or_none()

        if not prefs or not prefs.tradeAlerts:
            return False

        # Get Telegram link
        result = await db.execute(
            select(TelegramLink).where(TelegramLink.userId == user_id)
        )
        telegram_link = result.scalar_one_or_none()

        if not telegram_link:
            return False

        # Format trade notification
        side = trade_data.get("side", "UNKNOWN")
        symbol = trade_data.get("symbol", "UNKNOWN")
        quantity = trade_data.get("quantity", 0)
        price = trade_data.get("price", 0)
        pnl = trade_data.get("pnl", 0)

        emoji = "🟢" if side == "BUY" else "🔴"
        message = f"""{emoji} Trade Executed

Symbol: {symbol}
Side: {side}
Quantity: {quantity}
Price: {price}
PnL: {pnl:.4f} USDT
"""

        return await self.telegram_service.send_message(telegram_link.chatId, message)

    async def send_risk_alert(self, db: AsyncSession, user_id: int, alert_data: Dict[str, Any]) -> bool:
        """Send risk management alert"""
        # Check if user has enabled risk alerts
        result = await db.execute(
            select(NotificationPreference).where(NotificationPreference.userId == user_id)
        )
        prefs = result.scalar_one_or_none()

        if not prefs or not prefs.riskAlerts:
            return False

        # Get Telegram link
        result = await db.execute(
            select(TelegramLink).where(TelegramLink.userId == user_id)
        )
        telegram_link = result.scalar_one_or_none()

        if not telegram_link:
            return False

        # Format risk alert
        alert_type = alert_data.get("type", "RISK_ALERT")
        message_text = alert_data.get("message", "Risk threshold exceeded")

        message = f"""⚠️ {alert_type}

{message_text}

Please review your trading strategy and risk settings.
"""

        return await self.telegram_service.send_message(telegram_link.chatId, message)

    async def send_system_notification(self, db: AsyncSession, user_id: int, message_text: str) -> bool:
        """Send system notification"""
        # Check if user has enabled system alerts
        result = await db.execute(
            select(NotificationPreference).where(NotificationPreference.userId == user_id)
        )
        prefs = result.scalar_one_or_none()

        if not prefs or not prefs.systemAlerts:
            return False

        # Get Telegram link
        result = await db.execute(
            select(TelegramLink).where(TelegramLink.userId == user_id)
        )
        telegram_link = result.scalar_one_or_none()

        if not telegram_link:
            return False

        message = f"""ℹ️ System Notification

{message_text}
"""

        return await self.telegram_service.send_message(telegram_link.chatId, message)

    async def send_daily_summary(
        self, db: AsyncSession, user_id: int, summary_data: Dict[str, Any]
    ) -> bool:
        """Send daily performance summary"""
        # Check if user has enabled daily summaries
        result = await db.execute(
            select(NotificationPreference).where(NotificationPreference.userId == user_id)
        )
        prefs = result.scalar_one_or_none()

        if not prefs or not prefs.dailySummary:
            return False

        # Get Telegram link
        result = await db.execute(
            select(TelegramLink).where(TelegramLink.userId == user_id)
        )
        telegram_link = result.scalar_one_or_none()

        if not telegram_link:
            return False

        # Format daily summary
        total_pnl = summary_data.get("total_pnl", 0)
        trades_count = summary_data.get("trades_count", 0)
        win_rate = summary_data.get("win_rate", 0)

        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        message = f"""📊 Daily Summary

{pnl_emoji} Total PnL: {total_pnl:.4f} USDT
📝 Trades: {trades_count}
✅ Win Rate: {win_rate:.1f}%

Keep up the good work!
"""

        return await self.telegram_service.send_message(telegram_link.chatId, message)
