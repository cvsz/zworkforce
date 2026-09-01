"""// ZeaZDev [Telegram Service] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 3) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import os
import secrets
from typing import Any, Dict, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot
from telegram.error import TelegramError

from ztrader.abt.models import TelegramLink


class TelegramService:
    """Telegram bot service for notifications and account linking"""

    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.bot = Bot(token=self.bot_token) if self.bot_token else None

    async def send_message(self, chat_id: str, text: str) -> bool:
        """Send a message to a Telegram chat"""
        if not self.bot:
            print("Telegram bot not configured")
            return False

        try:
            await self.bot.send_message(chat_id=chat_id, text=text)
            return True
        except TelegramError as e:
            print(f"Failed to send Telegram message: {e}")
            return False

    async def verify_chat(self, chat_id: str) -> bool:
        """Verify that a chat ID is valid"""
        if not self.bot:
            return False

        try:
            chat = await self.bot.get_chat(chat_id=chat_id)
            return chat is not None
        except TelegramError:
            return False

    async def link_telegram_account(
        self, db: AsyncSession, user_id: int, chat_id: str, username: Optional[str] = None
    ) -> Dict[str, Any]:
        """Link a Telegram account to a user"""
        try:
            # Check if chat is already linked
            result = await db.execute(
                select(TelegramLink).where(TelegramLink.chatId == chat_id)
            )
            existing_link = result.scalar_one_or_none()

            if existing_link and existing_link.userId != user_id:
                return {
                    "success": False,
                    "error": "Chat ID already linked to another user",
                }

            # Create or update link
            result = await db.execute(
                select(TelegramLink).where(TelegramLink.userId == user_id)
            )
            link = result.scalar_one_or_none()

            if link:
                link.chatId = chat_id
                link.username = username
                link.verified = True
            else:
                link = TelegramLink(
                    userId=user_id,
                    chatId=chat_id,
                    username=username,
                    verified=True,
                )
                db.add(link)

            await db.flush()

            # Send confirmation message
            await self.send_message(
                chat_id,
                "✅ Your Telegram account has been successfully linked to ABTPro!",
            )

            return {"success": True, "link": link}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def unlink_telegram_account(self, db: AsyncSession, user_id: int) -> Dict[str, Any]:
        """Unlink a Telegram account from a user"""
        try:
            result = await db.execute(
                select(TelegramLink).where(TelegramLink.userId == user_id)
            )
            link = result.scalar_one_or_none()

            if not link:
                return {"success": False, "error": "No Telegram account linked"}

            # Send goodbye message
            await self.send_message(
                link.chatId, "👋 Your Telegram account has been unlinked from ABTPro."
            )

            # Delete link
            await db.execute(
                delete(TelegramLink).where(TelegramLink.userId == user_id)
            )
            await db.flush()

            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_telegram_link_status(self, db: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
        """Get Telegram link status for a user"""
        result = await db.execute(
            select(TelegramLink).where(TelegramLink.userId == user_id)
        )
        link = result.scalar_one_or_none()

        if link:
            return {
                "linked": True,
                "chatId": link.chatId,
                "username": link.username,
                "verified": link.verified,
            }

        return {"linked": False}

    def generate_verification_code(self) -> str:
        """Generate a verification code for linking"""
        return secrets.token_hex(4).upper()
