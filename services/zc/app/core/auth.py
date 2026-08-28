import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from app.core.config import get_config

# mTLS + JWT implementation (Phase 5)

def create_short_lived_token(subject: str, role: str) -> str:
    """Create a short-lived JWT token (5 minutes) for agent/client auth."""
    payload = {
        "sub": subject,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, get_config().jwt_secret or "", algorithm="HS256")

def verify_token(token: str) -> Optional[dict]:
    """Verify and decode token."""
    try:
        payload = jwt.decode(token, get_config().jwt_secret or "", algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

# OPA (Open Policy Agent) Integration
import httpx
from fastapi import Request, HTTPException

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
