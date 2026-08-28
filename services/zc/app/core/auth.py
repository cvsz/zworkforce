import jwt
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional
from app.core.config import get_config
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


@dataclass(frozen=True)
class Principal:
    """Verified request identity used by HTTP and service boundaries."""

    subject: str
    tenant_id: str
    roles: frozenset[str]


_bearer = HTTPBearer(auto_error=False)

# mTLS + JWT implementation (Phase 5)

def create_short_lived_token(subject: str, role: str) -> str:
    """Create a short-lived JWT token (5 minutes) for agent/client auth."""
    payload = {
        "sub": subject,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        "iat": datetime.now(timezone.utc)
    }
    config = get_config()
    if not config.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured")
    payload["tenant_id"] = subject
    payload["roles"] = [role]
    return jwt.encode(payload, config.jwt_secret, algorithm=config.jwt_algorithm)

def verify_token(token: str) -> Optional[dict]:
    """Verify and decode token."""
    try:
        config = get_config()
        if not config.jwt_secret:
            return None
        payload = jwt.decode(token, config.jwt_secret, algorithms=[config.jwt_algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def require_principal(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Principal:
    """Require a valid short-lived bearer token and normalized tenant claim."""
    config = get_config()
    if not config.auth_required:
        return Principal("development", "default", frozenset({"admin"}))
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = verify_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    raw_roles = payload.get("roles") or [payload.get("role", "")]
    roles = frozenset(str(role) for role in raw_roles if role)
    tenant_id = str(payload.get("tenant_id") or payload["sub"])
    return Principal(str(payload["sub"]), tenant_id, roles)


def require_roles(*allowed_roles: str):
    """Build a dependency enforcing at least one allowed role."""
    async def authorize(
        principal: Principal = Depends(require_principal),
    ) -> Principal:
        if not principal.roles.intersection(allowed_roles):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return principal

    return authorize

# OPA (Open Policy Agent) Integration
import httpx
from fastapi import Request

OPA_URL = "http://localhost:8181/v1/data/wire/authz/allow"

async def check_opa_policy(user_sub: str, role: str, action: str, resource: str) -> bool:
    """Evaluate access via Open Policy Agent (OPA)"""
    input_data = {
        "input": {
            "user": user_sub,
            "role": role,
            "action": action,
            "resource": resource
        }
    }

    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            response = await client.post(OPA_URL, json=input_data)
            response.raise_for_status()
            result = response.json()
            return result.get("result", False) is True
    except Exception as e:
        # Fail closed on OPA unavailability
        import logging
        logging.error(f"OPA Authorization failed: {e}")
        return False

def verify_mtls_cert(request: Request) -> bool:
    """
    Verify Mutual TLS (mTLS) certificate.
    In a k8s environment, the reverse proxy (like Cilium/Envoy) terminates mTLS 
    and passes the client cert details in headers (e.g., X-Forwarded-Client-Cert).
    """
    cert_header = request.headers.get("x-forwarded-client-cert")
    if not cert_header:
        raise HTTPException(status_code=401, detail="mTLS client certificate missing")

    # In a real enterprise setup, validate the SPIFFE ID or cert SAN here
    return True
