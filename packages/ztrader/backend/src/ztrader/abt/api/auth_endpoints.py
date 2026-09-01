"""// ZeaZDev [Backend API Auth Endpoints] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 3) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import secrets

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from ztrader.abt.auth.google_provider import GoogleOAuthProvider
from ztrader.abt.auth.oauth_service import OAuthService
from ztrader.abt.utils.auth import create_session_response

router = APIRouter()
oauth_service = OAuthService()
google_provider = GoogleOAuthProvider()

# Store for CSRF state tokens (in production, use Redis)
csrf_states = {}


class GoogleLoginRequest(BaseModel):
    id_token: str


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str


@router.get("/google/authorize")
async def google_authorize():
    """Initiate Google OAuth flow"""
    # Generate CSRF state token
    state = secrets.token_urlsafe(32)
    csrf_states[state] = True

    # Get authorization URL
    auth_url = google_provider.get_authorization_url(state)

    return {"authorization_url": auth_url, "state": state}


@router.post("/google/login")
async def google_login(request: GoogleLoginRequest, response: Response):
    """Login with Google ID token"""
    # Verify the token
    user_info = await oauth_service.verify_google_token(request.id_token)

    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    # Get or create user
    user = await oauth_service.get_or_create_user(
        google_id=user_info["google_id"],
        email=user_info["email"],
        profile_picture=user_info.get("picture"),
    )

    # Generate session token and create response
    session_token = oauth_service.generate_session_token()

    return create_session_response(
        user_id=user.id,
        email=user.email,
        profile_picture=user.profilePicture,
        session_token=session_token,
        response=response,
    )


@router.post("/google/callback")
async def google_callback(request: OAuthCallbackRequest, response: Response):
    """Handle Google OAuth callback"""
    # Verify CSRF state
    if request.state not in csrf_states:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Remove used state
    del csrf_states[request.state]

    try:
        # Exchange code for token
        token_data = google_provider.exchange_code_for_token(request.code)

        # Verify ID token
        user_info = await oauth_service.verify_google_token(token_data["id_token"])

        if not user_info:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Get or create user
        user = await oauth_service.get_or_create_user(
            google_id=user_info["google_id"],
            email=user_info["email"],
            profile_picture=user_info.get("picture"),
        )

        # Generate session token and create response
        session_token = oauth_service.generate_session_token()

        return create_session_response(
            user_id=user.id,
            email=user.email,
            profile_picture=user.profilePicture,
            session_token=session_token,
            response=response,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth callback failed: {str(e)}")


@router.get("/me")
async def get_current_user(request: Request):
    """Get current authenticated user"""
    # In production, validate session token from cookie
    session_token = request.cookies.get("session_token")

    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # For now, return a placeholder
    # In production, look up user from session token
    return {"authenticated": True, "message": "User info would be returned here"}


@router.post("/logout")
async def logout(response: Response):
    """Logout user"""
    # Clear session cookie
    response.delete_cookie(key="session_token")

    return {"status": "LOGGED_OUT"}
