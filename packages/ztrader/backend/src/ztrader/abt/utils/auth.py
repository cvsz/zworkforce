"""// ZeaZDev [Auth Utilities] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 //
// Author: ZeaZDev Meta-Intelligence //
// --- DO NOT EDIT HEADER --- //"""

from typing import Any, Dict

from fastapi import Response


def create_session_response(
    user_id: int,
    email: str,
    profile_picture: str,
    session_token: str,
    response: Response,
) -> Dict[str, Any]:
    """
    Create a standardized session response with secure cookie

    Args:
        user_id: User ID
        email: User email
        profile_picture: User profile picture URL
        session_token: Generated session token
        response: FastAPI Response object to set cookie on

    Returns:
        Dict with user info and login status
    """
    # Set secure cookie with httpOnly, secure, and samesite flags
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,  # Requires HTTPS in production
        max_age=86400 * 7,  # 7 days
        samesite="lax",
    )

    return {
        "user_id": user_id,
        "email": email,
        "profile_picture": profile_picture,
        "status": "LOGIN_SUCCESS",
    }
