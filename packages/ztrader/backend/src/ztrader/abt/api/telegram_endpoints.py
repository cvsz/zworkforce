"""// ZeaZDev [Backend API Telegram Endpoints] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 3) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ztrader.abt.services.notification_service import NotificationService
from ztrader.abt.services.telegram_service import TelegramService
from ztrader.abt.utils.exceptions import raise_bad_request

router = APIRouter()
telegram_service = TelegramService()
notification_service = NotificationService()


class LinkTelegramRequest(BaseModel):
    user_id: int
    chat_id: str
    username: Optional[str] = None


class UnlinkTelegramRequest(BaseModel):
    user_id: int


class SendTestNotificationRequest(BaseModel):
    user_id: int


@router.post("/link")
async def link_telegram(request: LinkTelegramRequest):
    """Link Telegram account to user"""
    result = await telegram_service.link_telegram_account(
        user_id=request.user_id, chat_id=request.chat_id, username=request.username
    )

    if not result["success"]:
        raise_bad_request(result.get("error", "Failed to link account"))

    return {"status": "LINKED", "chat_id": request.chat_id}


@router.post("/unlink")
async def unlink_telegram(request: UnlinkTelegramRequest):
    """Unlink Telegram account from user"""
    result = await telegram_service.unlink_telegram_account(request.user_id)

    if not result["success"]:
        raise_bad_request(result.get("error", "Failed to unlink account"))

    return {"status": "UNLINKED"}


@router.get("/status/{user_id}")
async def get_telegram_status(user_id: int):
    """Get Telegram link status for user"""
    status = await telegram_service.get_telegram_link_status(user_id)
    return status


@router.post("/notify/test")
async def send_test_notification(request: SendTestNotificationRequest):
    """Send a test notification to user's Telegram"""
    test_message = (
        "This is a test notification from ABTPro. "
        "Your Telegram notifications are working correctly! 🎉"
    )
    success = await notification_service.send_system_notification(
        user_id=request.user_id,
        message_text=test_message,
    )

    if not success:
        raise_bad_request(
            "Failed to send notification. Check Telegram link and preferences."
        )

    return {"status": "NOTIFICATION_SENT"}
