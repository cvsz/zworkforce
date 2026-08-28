"""Dependency-light, authenticated control-panel operational API."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..core.auth import Principal, require_roles
from ..core.cache import CacheKey, get_cache
from ..services.upload_manager import get_upload_manager

router = APIRouter(prefix="/admin", tags=["control-panel"])


@router.get("/metrics")
async def metrics(
    _principal: Principal = Depends(require_roles("admin", "viewer")),
) -> dict[str, Any]:
    """Return live cache and upload metrics without synthetic defaults."""
    cache = get_cache()
    upload = await get_upload_manager().health_check()
    return {
        "upload": upload,
        "cache": await cache.health_check(),
        "timestamp": time.time(),
    }


@router.get("/uploads/{session_id}")
async def upload_status(
    session_id: str,
    principal: Principal = Depends(
        require_roles("admin", "developer", "agent", "cli_service", "viewer")
    ),
) -> dict[str, Any]:
    """Return a tenant-scoped upload session."""
    session = await get_upload_manager().get_session(session_id, principal.tenant_id)
    if session is None:
        raise HTTPException(404, "Upload session not found")
    return session.to_dict()


@router.get("/uploads")
async def uploads(
    principal: Principal = Depends(
        require_roles("admin", "developer", "agent", "cli_service", "viewer")
    ),
) -> list[dict[str, Any]]:
    """Return real upload sessions visible to the current tenant."""
    return await get_upload_manager().list_sessions(principal.tenant_id)


@router.get("/feature-flags")
async def feature_flags(
    _principal: Principal = Depends(require_roles("admin", "viewer")),
) -> dict[str, bool]:
    """Return configured feature flags from shared cache."""
    cache = get_cache()
    values = await cache.get(CacheKey.build("feature", "flags"), {})
    return {str(key): bool(value) for key, value in values.items()}


@router.put("/feature-flags/{name}")
async def update_feature_flag(
    name: str,
    enabled: bool,
    _principal: Principal = Depends(require_roles("admin")),
) -> dict[str, Any]:
    """Atomically publish the latest feature-flag map to shared cache."""
    if not name or len(name) > 128 or not name.replace("_", "").isalnum():
        raise HTTPException(400, "Invalid feature flag name")
    cache = get_cache()
    key = CacheKey.build("feature", "flags")
    values = dict(await cache.get(key, {}))
    values[name] = enabled
    await cache.set(key, values, ttl=86400)
    return {"name": name, "enabled": enabled}
