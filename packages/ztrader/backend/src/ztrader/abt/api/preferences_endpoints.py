"""// ZeaZDev [Backend API User Preferences Endpoints] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 3) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from ztrader.abt.models import NotificationPreference, UserPreference
from ztrader.abt.utils.database import get_db_connection

router = APIRouter()


class UpdatePreferencesRequest(BaseModel):
    user_id: int
    theme: Optional[str] = None
    language: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    dashboard_layout: Optional[str] = None
    refresh_interval: Optional[int] = None


class UpdateThemeRequest(BaseModel):
    user_id: int
    theme: str


class UpdateLanguageRequest(BaseModel):
    user_id: int
    language: str


class UpdateNotificationPreferencesRequest(BaseModel):
    user_id: int
    trade_alerts: Optional[bool] = None
    risk_alerts: Optional[bool] = None
    system_alerts: Optional[bool] = None
    daily_summary: Optional[bool] = None


@router.get("/preferences/{user_id}")
async def get_user_preferences(user_id: int):
    """Get user preferences"""
    async with get_db_connection() as db:
        result = await db.execute(
            select(UserPreference).where(UserPreference.userId == user_id)
        )
        prefs = result.scalar_one_or_none()

        if not prefs:
            # Return default preferences
            return {
                "theme": "auto",
                "language": "th",
                "dashboardLayout": "grid",
                "refreshInterval": 30,
            }

        return {
            "theme": prefs.theme,
            "language": prefs.language,
            "primaryColor": prefs.primaryColor,
            "secondaryColor": prefs.secondaryColor,
            "accentColor": prefs.accentColor,
            "dashboardLayout": prefs.dashboardLayout,
            "refreshInterval": prefs.refreshInterval,
        }


@router.put("/preferences")
async def update_user_preferences(request: UpdatePreferencesRequest):
    """Update user preferences"""
    async with get_db_connection() as db:
        # Build update data
        update_data = {}
        if request.theme is not None:
            update_data["theme"] = request.theme
        if request.language is not None:
            update_data["language"] = request.language
        if request.primary_color is not None:
            update_data["primaryColor"] = request.primary_color
        if request.secondary_color is not None:
            update_data["secondaryColor"] = request.secondary_color
        if request.accent_color is not None:
            update_data["accentColor"] = request.accent_color
        if request.dashboard_layout is not None:
            update_data["dashboardLayout"] = request.dashboard_layout
        if request.refresh_interval is not None:
            update_data["refreshInterval"] = request.refresh_interval

        # Upsert preferences
        result = await db.execute(
            select(UserPreference).where(UserPreference.userId == request.user_id)
        )
        prefs = result.scalar_one_or_none()

        if prefs is None:
            prefs = UserPreference(userId=request.user_id, **update_data)
            db.add(prefs)
        else:
            for key, value in update_data.items():
                setattr(prefs, key, value)
        await db.flush()

        return {
            "status": "UPDATED",
            "preferences": {
                "theme": prefs.theme,
                "language": prefs.language,
                "primaryColor": prefs.primaryColor,
                "secondaryColor": prefs.secondaryColor,
                "accentColor": prefs.accentColor,
                "dashboardLayout": prefs.dashboardLayout,
                "refreshInterval": prefs.refreshInterval,
            },
        }


@router.patch("/theme")
async def update_theme(request: UpdateThemeRequest):
    """Update user theme preference"""
    async with get_db_connection() as db:
        result = await db.execute(
            select(UserPreference).where(UserPreference.userId == request.user_id)
        )
        prefs = result.scalar_one_or_none()

        if prefs is None:
            prefs = UserPreference(userId=request.user_id, theme=request.theme)
            db.add(prefs)
        else:
            prefs.theme = request.theme
        await db.flush()

        return {"status": "UPDATED", "theme": prefs.theme}


@router.patch("/language")
async def update_language(request: UpdateLanguageRequest):
    """Update user language preference"""
    async with get_db_connection() as db:
        result = await db.execute(
            select(UserPreference).where(UserPreference.userId == request.user_id)
        )
        prefs = result.scalar_one_or_none()

        if prefs is None:
            prefs = UserPreference(userId=request.user_id, language=request.language)
            db.add(prefs)
        else:
            prefs.language = request.language
        await db.flush()

        return {"status": "UPDATED", "language": prefs.language}


@router.get("/notifications/preferences/{user_id}")
async def get_notification_preferences(user_id: int):
    """Get notification preferences"""
    async with get_db_connection() as db:
        result = await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.userId == user_id
            )
        )
        prefs = result.scalar_one_or_none()

        if not prefs:
            return {
                "tradeAlerts": True,
                "riskAlerts": True,
                "systemAlerts": True,
                "dailySummary": True,
            }

        return {
            "tradeAlerts": prefs.tradeAlerts,
            "riskAlerts": prefs.riskAlerts,
            "systemAlerts": prefs.systemAlerts,
            "dailySummary": prefs.dailySummary,
        }


@router.put("/notifications/preferences")
async def update_notification_preferences(
    request: UpdateNotificationPreferencesRequest,
):
    """Update notification preferences"""
    async with get_db_connection() as db:
        # Build update data
        update_data = {}
        if request.trade_alerts is not None:
            update_data["tradeAlerts"] = request.trade_alerts
        if request.risk_alerts is not None:
            update_data["riskAlerts"] = request.risk_alerts
        if request.system_alerts is not None:
            update_data["systemAlerts"] = request.system_alerts
        if request.daily_summary is not None:
            update_data["dailySummary"] = request.daily_summary

        # Upsert preferences
        result = await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.userId == request.user_id
            )
        )
        prefs = result.scalar_one_or_none()

        if prefs is None:
            prefs = NotificationPreference(userId=request.user_id, **update_data)
            db.add(prefs)
        else:
            for key, value in update_data.items():
                setattr(prefs, key, value)
        await db.flush()

        return {
            "status": "UPDATED",
            "preferences": {
                "tradeAlerts": prefs.tradeAlerts,
                "riskAlerts": prefs.riskAlerts,
                "systemAlerts": prefs.systemAlerts,
                "dailySummary": prefs.dailySummary,
            },
        }
