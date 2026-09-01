"""// ZeaZDev [Secret Rotation API Endpoints] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 5) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ztrader.abt.services.secret_rotation_service import SecretRotationService

router = APIRouter()
rotation_service = SecretRotationService()


class RotateSecretRequest(BaseModel):
    secretType: str  # DATABASE, ENCRYPTION_KEY, API_KEY, OAUTH_SECRET
    secretName: str
    newValue: str
    userId: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class UpdatePolicyRequest(BaseModel):
    secretType: str
    secretName: str
    rotationIntervalDays: int
    gracePeriodDays: Optional[int] = None


@router.get("/rotation/schedule")
async def get_rotation_schedule(
    secretType: Optional[str] = Query(None, description="Filter by secret type"),
    includeDeprecated: bool = Query(False, description="Include deprecated rotations"),
):
    """
    Get rotation schedule for all secrets or specific type

    - **secretType**: Filter by type (DATABASE, ENCRYPTION_KEY, API_KEY, OAUTH_SECRET)
    - **includeDeprecated**: Include deprecated rotation records
    """
    schedules = await rotation_service.get_rotation_schedule(
        secret_type=secretType, include_deprecated=includeDeprecated
    )

    return {"schedules": schedules, "total": len(schedules)}


@router.post("/rotation/rotate")
async def rotate_secret(request: RotateSecretRequest):
    """
    Manually trigger a secret rotation

    - **secretType**: Type of secret to rotate
    - **secretName**: Name/identifier of the secret
    - **newValue**: New secret value (will be hashed, not stored)
    - **userId**: User ID performing the rotation
    - **metadata**: Additional information about the rotation
    """
    valid_types = [
        "DATABASE",
        "ENCRYPTION_KEY",
        "API_KEY",
        "OAUTH_SECRET",
        "WEBHOOK_SECRET",
    ]

    if request.secretType not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid secretType. Must be one of: {', '.join(valid_types)}",
        )

    try:
        result = await rotation_service.create_rotation_record(
            secret_type=request.secretType,
            secret_name=request.secretName,
            new_secret_value=request.newValue,
            rotated_by=request.userId,
            metadata=request.metadata,
        )

        return {
            "status": "success",
            "message": f"Secret {request.secretName} rotated successfully",
            "rotation": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rotation failed: {str(e)}")


@router.get("/rotation/history")
async def get_rotation_history(
    secretType: Optional[str] = Query(None, description="Filter by secret type"),
    secretName: Optional[str] = Query(None, description="Filter by secret name"),
    limit: int = Query(50, ge=1, le=500, description="Maximum records to return"),
):
    """
    Get rotation history with optional filters

    - **secretType**: Filter by secret type
    - **secretName**: Filter by secret name
    - **limit**: Maximum number of records (default: 50, max: 500)
    """
    history = await rotation_service.get_rotation_history(
        secret_type=secretType, secret_name=secretName, limit=limit
    )

    return {"history": history, "total": len(history)}


@router.get("/rotation/due")
async def get_secrets_due_for_rotation(
    daysAhead: int = Query(7, ge=1, le=90, description="Days to look ahead"),
):
    """
    Get secrets that are due for rotation within specified days

    - **daysAhead**: Number of days to look ahead (default: 7)
    """
    due_secrets = await rotation_service.get_secrets_due_for_rotation(
        days_ahead=daysAhead
    )

    # Separate overdue and upcoming
    overdue = [s for s in due_secrets if s.get("overdue", False)]
    upcoming = [s for s in due_secrets if not s.get("overdue", False)]

    return {
        "overdue": overdue,
        "upcoming": upcoming,
        "overdueCount": len(overdue),
        "upcomingCount": len(upcoming),
    }


@router.put("/rotation/policy")
async def update_rotation_policy(request: UpdatePolicyRequest):
    """
    Update the rotation policy for a specific secret

    - **secretType**: Type of secret
    - **secretName**: Name of secret
    - **rotationIntervalDays**: New rotation interval in days
    - **gracePeriodDays**: Grace period in days (optional)
    """
    if request.rotationIntervalDays < 1 or request.rotationIntervalDays > 365:
        raise HTTPException(
            status_code=400, detail="Rotation interval must be between 1 and 365 days"
        )

    try:
        result = await rotation_service.update_rotation_policy(
            secret_type=request.secretType,
            secret_name=request.secretName,
            rotation_interval_days=request.rotationIntervalDays,
            grace_period_days=request.gracePeriodDays,
        )

        return {
            "status": "success",
            "message": "Rotation policy updated",
            "policy": result,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@router.post("/rotation/complete/{secret_type}/{secret_name}")
async def mark_rotation_complete(secret_type: str, secret_name: str):
    """
    Mark a rotation as completed

    - **secret_type**: Type of secret
    - **secret_name**: Name of secret
    """
    try:
        result = await rotation_service.mark_rotation_complete(
            secret_type=secret_type, secret_name=secret_name
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Operation failed: {str(e)}")
