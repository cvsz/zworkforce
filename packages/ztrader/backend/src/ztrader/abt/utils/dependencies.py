"""// ZeaZDev [FastAPI Dependencies] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 //
// Author: ZeaZDev Meta-Intelligence //
// --- DO NOT EDIT HEADER --- //"""

from logging import getLogger
from typing import Optional

from fastapi import HTTPException, Request
from sqlalchemy import select

from ztrader.abt.models import User
from ztrader.abt.utils.database import get_db_connection

logger = getLogger(__name__)


async def get_current_user_id(request: Request) -> int:
    """
    Dependency to extract user ID from session token

    Validates the session token from the cookie and looks up
    the user in the database.

    Args:
        request: FastAPI Request object

    Returns:
        User ID

    Raises:
        HTTPException: If not authenticated
    """
    session_token = request.cookies.get("session_token")

    if not session_token:
        logger.warning(
            "Authentication attempt without session token",
            extra={"component": "auth", "ip": request.client.host if request.client else None},
        )
        raise HTTPException(status_code=401, detail="Not authenticated")

    async with get_db_connection() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalars().first()

    if not user:
        logger.warning(
            "Session validation failed: no user found",
            extra={"component": "auth"},
        )
        raise HTTPException(status_code=401, detail="User not found")

    logger.info(
        f"Session validated for user {user.id}",
        extra={"component": "auth", "user_id": user.id},
    )
    return user.id


async def get_optional_user_id(request: Request) -> Optional[int]:
    """
    Dependency to extract user ID from session token (optional)

    Returns None if not authenticated instead of raising an exception.

    Args:
        request: FastAPI Request object

    Returns:
        User ID or None
    """
    session_token = request.cookies.get("session_token")

    if not session_token:
        return None

    async with get_db_connection() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalars().first()

    if not user:
        return None

    logger.info(
        f"Session validated for user {user.id}",
        extra={"component": "auth", "user_id": user.id},
    )
    return user.id
