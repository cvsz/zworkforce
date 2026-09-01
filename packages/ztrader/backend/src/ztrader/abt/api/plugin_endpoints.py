"""// ZeaZDev [Plugin API Endpoints] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 4) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ztrader.abt.plugins.plugin_loader import PluginLoader
from ztrader.abt.utils.dependencies import get_current_user_id
from ztrader.abt.utils.exceptions import handle_service_error

router = APIRouter()
plugin_loader = PluginLoader()


class InstallPluginRequest(BaseModel):
    plugin_name: str
    config: Optional[Dict[str, Any]] = None


class TogglePluginRequest(BaseModel):
    enabled: bool


@router.get("/available")
async def list_available_plugins(plugin_type: Optional[str] = None):
    """List all available plugins"""
    try:
        plugins = await plugin_loader.list_available_plugins()

        # Filter by type if specified
        if plugin_type:
            plugins = [p for p in plugins if p["type"] == plugin_type.upper()]

        return {"plugins": plugins, "count": len(plugins)}
    except Exception as e:
        handle_service_error(e)


@router.get("/installed")
async def list_installed_plugins(user_id: int = Depends(get_current_user_id)):
    """List user's installed plugins"""
    try:
        plugins = await plugin_loader.get_user_plugins(user_id)
        return {"plugins": plugins, "count": len(plugins)}
    except Exception as e:
        handle_service_error(e)


@router.post("/install")
async def install_plugin(
    request: InstallPluginRequest, user_id: int = Depends(get_current_user_id)
):
    """Install a plugin for the user"""
    try:
        result = await plugin_loader.install_plugin_for_user(
            user_id=user_id, plugin_name=request.plugin_name, config=request.config
        )
        return result
    except Exception as e:
        handle_service_error(e)


@router.delete("/uninstall/{user_plugin_id}")
async def uninstall_plugin(
    user_plugin_id: int, user_id: int = Depends(get_current_user_id)
):
    """Uninstall a plugin"""
    try:
        # First disable the plugin
        await plugin_loader.toggle_plugin(user_plugin_id, False)
        return {"success": True, "user_plugin_id": user_plugin_id}
    except Exception as e:
        handle_service_error(e)


@router.post("/{user_plugin_id}/toggle")
async def toggle_plugin(user_plugin_id: int, request: TogglePluginRequest):
    """Enable or disable a plugin"""
    try:
        result = await plugin_loader.toggle_plugin(user_plugin_id, request.enabled)
        return result
    except Exception as e:
        handle_service_error(e)


@router.get("/discover")
async def discover_plugins():
    """Discover plugins from installed packages"""
    try:
        discovered = plugin_loader.discover_plugins()
        return {"plugins": discovered, "count": len(discovered)}
    except Exception as e:
        handle_service_error(e)
