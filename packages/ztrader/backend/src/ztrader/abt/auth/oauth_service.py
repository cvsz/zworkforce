"""// ZeaZDev [OAuth Service] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 3) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import os
import secrets
from typing import Any, Dict, Optional

from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ztrader.abt.models import User, UserPreference, NotificationPreference


class OAuthService:
    """OAuth service for managing authentication flows"""

    def __init__(self):
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

    async def verify_google_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify Google ID token and return user info"""
        try:
            # Verify the token
            idinfo = id_token.verify_oauth2_token(
                token, requests.Request(), self.google_client_id
            )

            # Token is valid, return user information
            return {
                "google_id": idinfo["sub"],
                "email": idinfo["email"],
                "name": idinfo.get("name"),
                "picture": idinfo.get("picture"),
                "email_verified": idinfo.get("email_verified", False),
            }
        except Exception as e:
            print(f"Token verification failed: {e}")
            return None

    async def get_or_create_user(
        self, db: AsyncSession, google_id: str, email: str, profile_picture: Optional[str] = None
    ):
        """Get existing user or create new user from OAuth data"""
        # Try to find user by Google ID
        result = await db.execute(select(User).where(User.googleId == google_id))
        user = result.scalar_one_or_none()

        if user:
            # Update profile picture if changed
            if profile_picture and user.profilePicture != profile_picture:
                user.profilePicture = profile_picture
                await db.flush()
        else:
            # Try to find by email (existing user without OAuth)
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if user:
                # Link Google account to existing user
                user.googleId = google_id
                user.oauthProvider = "google"
                user.profilePicture = profile_picture
                await db.flush()
            else:
                # Create new user
                user = User(
                    email=email,
                    googleId=google_id,
                    oauthProvider="google",
                    profilePicture=profile_picture,
                )
                db.add(user)
                await db.flush()

                # Create default preferences for new user
                user_pref = UserPreference(
                    userId=user.id,
                    theme="auto",
                    language="th",
                    dashboardLayout="grid",
                    refreshInterval=30,
                )
                db.add(user_pref)

                notif_pref = NotificationPreference(
                    userId=user.id,
                    tradeAlerts=True,
                    riskAlerts=True,
                    systemAlerts=True,
                    dailySummary=True,
                )
                db.add(notif_pref)
                await db.flush()

        return user

    def generate_session_token(self) -> str:
        """Generate a secure session token"""
        return secrets.token_urlsafe(32)
