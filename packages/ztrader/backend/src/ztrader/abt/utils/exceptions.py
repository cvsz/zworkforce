"""// ZeaZDev [Exception Handling Utilities] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 //
// Author: ZeaZDev Meta-Intelligence //
// --- DO NOT EDIT HEADER --- //"""

from fastapi import HTTPException


def raise_bad_request(detail: str) -> None:
    """Raise a 400 Bad Request exception"""
    raise HTTPException(status_code=400, detail=detail)


def raise_not_found(detail: str) -> None:
    """Raise a 404 Not Found exception"""
    raise HTTPException(status_code=404, detail=detail)


def raise_internal_error(error: Exception) -> None:
    """Raise a 500 Internal Server Error exception"""
    raise HTTPException(status_code=500, detail=str(error))


def handle_service_error(error: Exception) -> None:
    """
    Handle service layer errors by raising appropriate HTTP exceptions

    Args:
        error: The exception to handle

    Raises:
        HTTPException: With appropriate status code
    """
    if isinstance(error, ValueError):
        raise_bad_request(str(error))
    else:
        raise_internal_error(error)
