"""// ZeaZDev [Audit API Endpoints] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 5) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ztrader.abt.services.audit_service import AuditService
from ztrader.abt.utils.exceptions import raise_bad_request, raise_not_found

router = APIRouter()
audit_service = AuditService()


class AuditLogQuery(BaseModel):
    userId: Optional[int] = None
    action: Optional[str] = None
    resource: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    page: int = 1
    limit: int = 50


@router.get("/logs")
async def get_audit_logs(
    userId: Optional[int] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource: Optional[str] = Query(None, description="Filter by resource"),
    startDate: Optional[str] = Query(None, description="Start date (ISO 8601)"),
    endDate: Optional[str] = Query(None, description="End date (ISO 8601)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=1000, description="Items per page"),
):
    """
    Query audit logs with optional filters

    - **userId**: Filter by user ID
    - **action**: Filter by action type (CREATE, READ, UPDATE, DELETE, LOGIN, LOGOUT)
    - **resource**: Filter by API endpoint (partial match)
    - **startDate**: Start of date range (ISO 8601 format)
    - **endDate**: End of date range (ISO 8601 format)
    - **page**: Page number (default: 1)
    - **limit**: Items per page (default: 50, max: 1000)
    """
    # Parse dates
    start_dt = None
    end_dt = None

    if startDate:
        try:
            start_dt = datetime.fromisoformat(startDate.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid startDate format. Use ISO 8601."
            )

    if endDate:
        try:
            end_dt = datetime.fromisoformat(endDate.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid endDate format. Use ISO 8601."
            )

    result = await audit_service.get_logs(
        user_id=userId,
        action=action,
        resource=resource,
        start_date=start_dt,
        end_date=end_dt,
        page=page,
        limit=limit,
    )

    return result


@router.get("/logs/{log_id}")
async def get_audit_log(log_id: int):
    """Get a specific audit log by ID"""
    log = await audit_service.get_log_by_id(log_id)

    if not log:
        raise_not_found("Audit log not found")

    return log


@router.get("/stats")
async def get_audit_stats(
    startDate: Optional[str] = Query(None, description="Start date (ISO 8601)"),
    endDate: Optional[str] = Query(None, description="End date (ISO 8601)"),
):
    """
    Get audit log statistics

    - **startDate**: Start of date range (ISO 8601 format)
    - **endDate**: End of date range (ISO 8601 format)
    """
    # Parse dates
    start_dt = None
    end_dt = None

    if startDate:
        try:
            start_dt = datetime.fromisoformat(startDate.replace("Z", "+00:00"))
        except ValueError:
            raise_bad_request("Invalid startDate format. Use ISO 8601.")

    if endDate:
        try:
            end_dt = datetime.fromisoformat(endDate.replace("Z", "+00:00"))
        except ValueError:
            raise_bad_request("Invalid endDate format. Use ISO 8601.")

    stats = await audit_service.get_stats(start_date=start_dt, end_date=end_dt)

    return stats


@router.get("/export")
async def export_audit_logs(
    format: str = Query("csv", description="Export format (csv or json)"),
    userId: Optional[int] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource: Optional[str] = Query(None, description="Filter by resource"),
    startDate: Optional[str] = Query(None, description="Start date (ISO 8601)"),
    endDate: Optional[str] = Query(None, description="End date (ISO 8601)"),
):
    """
    Export audit logs in CSV or JSON format

    - **format**: Export format (csv or json)
    - **userId**: Filter by user ID
    - **action**: Filter by action type
    - **resource**: Filter by API endpoint
    - **startDate**: Start of date range
    - **endDate**: End of date range
    """
    if format not in ["csv", "json"]:
        raise_bad_request("Format must be 'csv' or 'json'")

    # Parse dates
    start_dt = None
    end_dt = None

    if startDate:
        try:
            start_dt = datetime.fromisoformat(startDate.replace("Z", "+00:00"))
        except ValueError:
            raise_bad_request("Invalid startDate format. Use ISO 8601.")

    if endDate:
        try:
            end_dt = datetime.fromisoformat(endDate.replace("Z", "+00:00"))
        except ValueError:
            raise_bad_request("Invalid endDate format. Use ISO 8601.")

    # Get all logs (no pagination for export)
    result = await audit_service.get_logs(
        user_id=userId,
        action=action,
        resource=resource,
        start_date=start_dt,
        end_date=end_dt,
        page=1,
        limit=1000,  # Max limit for export
    )

    logs = result["logs"]

    if format == "json":
        return {
            "logs": logs,
            "exportedAt": datetime.utcnow().isoformat(),
            "totalRecords": len(logs),
        }

    # CSV format
    output = io.StringIO()
    if logs:
        fieldnames = [
            "id",
            "userId",
            "userEmail",
            "action",
            "resource",
            "method",
            "statusCode",
            "ipAddress",
            "userAgent",
            "createdAt",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for log in logs:
            # Only write non-sensitive fields to CSV
            row = {k: v for k, v in log.items() if k in fieldnames}
            writer.writerow(row)

    from fastapi.responses import StreamingResponse

    output.seek(0)
    filename = f"audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
