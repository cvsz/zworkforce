"""// ZeaZDev [Health Check API Endpoints] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 5) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import logging
import os
from datetime import datetime

import psutil
import redis
from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select, text

from ztrader.abt.models import User
from ztrader.abt.utils.database import get_db_connection, time_database_operation

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
async def basic_health_check():
    """
    Basic health check endpoint
    Returns simple status for load balancers
    """
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@router.get("/detailed")
async def detailed_health_check():
    """
    Detailed health check with component status
    Includes database, Redis, and system metrics
    """
    components = {}
    overall_status = "healthy"

    # Check database
    try:
        async with get_db_connection() as db:
            async def _count_users():
                result = await db.execute(select(func.count()).select_from(User))
                return result.scalar()

            timing_result = await time_database_operation(_count_users)

            components["database"] = {
                "status": "healthy",
                "responseTime": timing_result["responseTime"],
            }
    except Exception as error:
        logger.warning(
            "Database health check failed",
            extra={"error_type": type(error).__name__},
        )
        components["database"] = {
            "status": "unhealthy",
            "error": "Database health check failed",
        }
        overall_status = "unhealthy"

    # Check Redis
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url)

        start_time = datetime.utcnow()
        r.ping()
        end_time = datetime.utcnow()

        response_time = (end_time - start_time).total_seconds() * 1000

        components["redis"] = {
            "status": "healthy",
            "responseTime": round(response_time, 2),
        }
    except Exception as error:
        logger.warning(
            "Redis health check failed",
            extra={"error_type": type(error).__name__},
        )
        components["redis"] = {
            "status": "unhealthy",
            "error": "Redis health check failed",
        }
        overall_status = "unhealthy"

    # System metrics
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        metrics = {
            "cpuUsage": round(cpu_percent, 2),
            "memoryUsage": round(memory.percent, 2),
            "diskUsage": round(disk.percent, 2),
        }
    except Exception as error:
        logger.warning(
            "System metrics collection failed",
            extra={"error_type": type(error).__name__},
        )
        metrics = {"error": "Could not retrieve system metrics"}

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "components": components,
        "metrics": metrics,
    }


@router.get("/database")
async def database_health_check():
    """
    Database-specific health check
    Tests database connectivity and basic operations
    """
    try:
        async with get_db_connection() as db:
            async def _count_users():
                result = await db.execute(select(func.count()).select_from(User))
                return result.scalar()

            timing_result = await time_database_operation(_count_users)
            user_count = timing_result["result"]
            read_time = timing_result["responseTime"]

            result = await db.execute(text("SELECT version()"))
            row = result.fetchone()
            db_version = row[0] if row else "Unknown"

            return {
                "status": "healthy",
                "connection": "established",
                "responseTime": read_time,
                "recordCount": user_count,
                "version": db_version,
                "timestamp": datetime.utcnow().isoformat(),
            }
    except Exception as error:
        logger.warning(
            "Database-specific health check failed",
            extra={"error_type": type(error).__name__},
        )
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "error": "Database health check failed",
                "timestamp": datetime.utcnow().isoformat(),
            },
        ) from None


@router.get("/redis")
async def redis_health_check():
    """
    Redis-specific health check
    Tests Redis connectivity and operations
    """
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url)

        # Test ping
        start_time = datetime.utcnow()
        r.ping()
        end_time = datetime.utcnow()

        ping_time = (end_time - start_time).total_seconds() * 1000

        # Get Redis info
        info = r.info()

        # Test set/get
        test_key = "__health_check__"
        r.set(test_key, "ok", ex=10)
        test_value = r.get(test_key)
        r.delete(test_key)

        return {
            "status": "healthy",
            "connection": "established",
            "responseTime": round(ping_time, 2),
            "version": info.get("redis_version", "Unknown"),
            "connectedClients": info.get("connected_clients", 0),
            "usedMemory": info.get("used_memory_human", "Unknown"),
            "testOperation": "success" if test_value == b"ok" else "failed",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as error:
        logger.warning(
            "Redis-specific health check failed",
            extra={"error_type": type(error).__name__},
        )
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "error": "Redis health check failed",
                "timestamp": datetime.utcnow().isoformat(),
            },
        ) from None


@router.get("/system")
async def system_health_check():
    """
    System resource health check
    Returns CPU, memory, and disk usage
    """
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()

        # Memory usage
        memory = psutil.virtual_memory()

        # Disk usage
        disk = psutil.disk_usage("/")

        # Network stats
        net_io = psutil.net_io_counters()

        return {
            "status": "healthy",
            "cpu": {
                "usage": round(cpu_percent, 2),
                "count": cpu_count,
                "status": "healthy" if cpu_percent < 80 else "warning",
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "percent": round(memory.percent, 2),
                "status": "healthy" if memory.percent < 80 else "warning",
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": round(disk.percent, 2),
                "status": "healthy" if disk.percent < 80 else "warning",
            },
            "network": {
                "bytesSent": net_io.bytes_sent,
                "bytesReceived": net_io.bytes_recv,
                "packetsSent": net_io.packets_sent,
                "packetsReceived": net_io.packets_recv,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as error:
        logger.warning(
            "System health check failed",
            extra={"error_type": type(error).__name__},
        )
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "error": "System health check failed",
                "timestamp": datetime.utcnow().isoformat(),
            },
        ) from None
