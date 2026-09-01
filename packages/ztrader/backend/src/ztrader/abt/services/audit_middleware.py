"""// ZeaZDev [Audit Middleware] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 5) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ztrader.abt.services.audit_service import AuditService


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically log all API requests to audit trail"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.audit_service = AuditService()

    def get_user_id(self, request: Request) -> int:
        """Extract user ID from request (if available)"""
        # Try to get from request state (set by auth middleware)
        if hasattr(request.state, "user_id"):
            return request.state.user_id

        # Try to get from headers (simple implementation)
        user_id_header = request.headers.get("X-User-Id")
        if user_id_header:
            try:
                return int(user_id_header)
            except ValueError:
                pass

        return None

    def get_action_from_method(self, method: str, path: str) -> str:
        """Determine action type from HTTP method and path"""
        if "login" in path.lower():
            return "LOGIN"
        elif "logout" in path.lower():
            return "LOGOUT"
        elif method == "POST":
            return "CREATE"
        elif method == "GET":
            return "READ"
        elif method in ["PUT", "PATCH"]:
            return "UPDATE"
        elif method == "DELETE":
            return "DELETE"
        else:
            return method

    def should_log(self, path: str) -> bool:
        """Determine if this endpoint should be logged"""
        # Skip certain endpoints
        skip_paths = [
            "/metrics",  # Prometheus metrics
            "/health",  # Health checks
            "/docs",  # API documentation
            "/openapi.json",
            "/favicon.ico",
        ]

        for skip_path in skip_paths:
            if path.startswith(skip_path):
                return False

        return True

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log to audit trail"""

        # Process the request
        response = await call_next(request)

        # Check if we should log this request
        if not self.should_log(request.url.path):
            return response

        # Extract request information
        user_id = self.get_user_id(request)
        action = self.get_action_from_method(request.method, request.url.path)
        resource = request.url.path
        method = request.method
        status_code = response.status_code
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        # Get request data (query params and body)
        request_data = {}

        # Add query parameters
        if request.query_params:
            request_data["query"] = dict(request.query_params)

        # Add path parameters
        if hasattr(request, "path_params") and request.path_params:
            request_data["path"] = request.path_params

        # Note: We can't easily get the request body here because it's
        # already been consumed. If you need body logging, you'd need to
        # implement a custom Request class

        # Log to audit trail (async, non-blocking)
        try:
            await self.audit_service.log_api_call(
                user_id=user_id,
                action=action,
                resource=resource,
                method=method,
                status_code=status_code,
                ip_address=ip_address,
                user_agent=user_agent,
                request_data=request_data if request_data else None,
            )
        except Exception as e:
            # Don't fail the request if audit logging fails
            print(f"Audit logging error: {e}")

        return response
