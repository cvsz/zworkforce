"""
Enterprise Security Module - Phase 4
JWT Authentication, mTLS, OAuth2, and Advanced Security Controls
2026 Enterprise Standards for wire CLI-to-API System
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlunsplit

import jwt
import redis.asyncio as redis
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding
from pydantic import BaseModel, Field


class TokenClaims(BaseModel):
    """JWT Token Claims Structure"""
    sub: str  # Subject (user/service ID)
    iss: str = "wire-enterprise"  # Issuer
    aud: str = "wire-api"  # Audience
    iat: int  # Issued at
    exp: int  # Expiration
    jti: str  # JWT ID (unique identifier)
    roles: list[str] = []  # RBAC roles
    permissions: list[str] = []  # Fine-grained permissions
    client_id: Optional[str] = None  # CLI client identifier
    scope: list[str] = []  # OAuth2 scopes
    mtls_verified: bool = False  # mTLS verification status
    cert_fingerprint: Optional[str] = None  # Client cert fingerprint


class SecurityConfig(BaseModel):
    """Security Configuration"""
    jwt_secret_key: str = Field(default_factory=lambda: os.getenv("JWT_SECRET_KEY", secrets.token_hex(32)))
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
    jwt_refresh_expiration_days: int = int(os.getenv("JWT_REFRESH_EXPIRATION_DAYS", "30"))

    # mTLS Configuration
    mtls_enabled: bool = os.getenv("MTLS_ENABLED", "true").lower() == "true"
    ca_cert_path: Optional[Path] = Path(os.getenv("CA_CERT_PATH", "/etc/ssl/certs/ca.crt"))
    client_cert_required: bool = os.getenv("CLIENT_CERT_REQUIRED", "true").lower() == "true"

    # OAuth2 Configuration
    oauth2_providers: dict[str, dict] = {
        "github": {
            "client_id": os.getenv("GITHUB_CLIENT_ID", ""),
            "client_secret": os.getenv("GITHUB_CLIENT_SECRET", ""),
            "authorize_url": "https://github.com/login/oauth/authorize",
            "token_url": urlunsplit(
                ("https", "github.com", "/login/oauth/access_token", "", "")
            ),
            "userinfo_url": "https://api.github.com/user",
            "scopes": ["user:email"]
        },
        "google": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": urlunsplit(
                ("https", "oauth2.googleapis.com", "/token", "", "")
            ),
            "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
            "scopes": ["openid", "email", "profile"]
        }
    }

    # Rate Limiting per Role
    rate_limits: dict[str, dict] = {
        "admin": {"requests_per_minute": 1000, "burst": 100},
        "developer": {"requests_per_minute": 500, "burst": 50},
        "cli_service": {"requests_per_minute": 2000, "burst": 200},
        "anonymous": {"requests_per_minute": 60, "burst": 10}
    }

    # Security Headers
    security_headers: dict[str, str] = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
    }


class JWTManager:
    """JWT Token Management with Refresh Rotation"""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self._token_blacklist: set[str] = set()
        self._redis: Optional[redis.Redis] = None

    async def initialize(self, redis_client: redis.Redis):
        """Initialize with Redis for distributed token management"""
        self._redis = redis_client

    def generate_access_token(self, claims: TokenClaims) -> str:
        """Generate signed JWT access token"""
        payload = claims.dict()
        token = jwt.encode(payload, self.config.jwt_secret_key, algorithm=self.config.jwt_algorithm)
        return token

    def generate_refresh_token(self, user_id: str, token_family: str) -> str:
        """Generate refresh token with rotation tracking"""
        refresh_claims = {
            "sub": user_id,
            "type": "refresh",
            "family": token_family,
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(days=self.config.jwt_refresh_expiration_days)).timestamp()),
            "jti": secrets.token_hex(16)
        }
        return jwt.encode(refresh_claims, self.config.jwt_secret_key, algorithm=self.config.jwt_algorithm)

    def verify_token(self, token: str, verify_exp: bool = True) -> TokenClaims:
        """Verify and decode JWT token"""
        try:
            if token in self._token_blacklist:
                raise jwt.InvalidTokenError("Token has been revoked")

            payload = jwt.decode(
                token,
                self.config.jwt_secret_key,
                algorithms=[self.config.jwt_algorithm],
                options={"verify_exp": verify_exp}
            )

            return TokenClaims(**payload)

        except jwt.ExpiredSignatureError:
            raise jwt.InvalidTokenError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(f"Invalid token: {str(e)}")

    async def revoke_token(self, token: str, ttl_seconds: int = 3600):
        """Revoke token and add to blacklist"""
        self._token_blacklist.add(token)
        if self._redis:
            await self._redis.setex(f"revoked:{token}", ttl_seconds, "1")

    async def _revoke_token_family(self, family: str) -> None:
        """Revoke an entire family of refresh tokens"""
        if self._redis:
            await self._redis.setex(f"revoked_family:{family}", self.config.jwt_refresh_expiration_days * 86400, "1")

    async def rotate_refresh_token(self, old_refresh_token: str, user_id: str) -> tuple[str, str]:
        """Refresh token rotation with family tracking"""
        try:
            payload = jwt.decode(old_refresh_token, self.config.jwt_secret_key, algorithms=[self.config.jwt_algorithm])

            if payload.get("type") != "refresh":
                raise jwt.InvalidTokenError("Not a refresh token")

            # Check if token family is compromised
            family = str(payload.get("family", ""))
            jti = str(payload.get("jti", ""))

            if self._redis:
                used_key = f"refresh_used:{jti}"
                if await self._redis.exists(used_key):
                    # Token reuse detected - revoke entire family
                    await self._revoke_token_family(family)
                    raise jwt.InvalidTokenError("Token family compromised")

                await self._redis.setex(used_key, self.config.jwt_refresh_expiration_days * 86400, "1")

            # Generate new token pair
            new_access_claims = TokenClaims(
                sub=user_id,
                iat=int(datetime.now(timezone.utc).timestamp()),
                exp=int((datetime.now(timezone.utc) + timedelta(hours=self.config.jwt_expiration_hours)).timestamp()),
                jti=secrets.token_hex(16),
                roles=payload.get("roles", []),
                permissions=payload.get("permissions", [])
            )

            new_access_token = self.generate_access_token(new_access_claims)
            new_refresh_token = self.generate_refresh_token(user_id, family)

            return new_access_token, new_refresh_token

        except jwt.InvalidTokenError:
            raise


class mTLSValidator:
    """Mutual TLS Certificate Validation"""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.ca_cert: Optional[x509.Certificate] = None
        self.revoked_serials: set[int] = set()

        if config.mtls_enabled and config.ca_cert_path and config.ca_cert_path.exists():
            self._load_ca_cert()

    def _load_ca_cert(self):
        """Load CA certificate for client verification"""
        with open(self.config.ca_cert_path, "rb") as f:
            self.ca_cert = x509.load_pem_x509_certificate(f.read())

    def validate_client_cert(self, cert_der: bytes) -> dict[str, Any]:
        """Validate client certificate against CA"""
        if not self.config.mtls_enabled:
            return {"valid": True, "mtls_verified": False}

        try:
            client_cert = x509.load_der_x509_certificate(cert_der)

            # Check expiration
            now = datetime.now(timezone.utc)
            if client_cert.not_valid_before_utc > now or client_cert.not_valid_after_utc < now:
                return {"valid": False, "error": "Certificate expired or not yet valid"}

            # Check revocation
            if client_cert.serial_number in self.revoked_serials:
                return {"valid": False, "error": "Certificate revoked"}

            # Verify signature against CA
            try:
                if self.ca_cert is None:
                    return {"valid": False, "error": "CA certificate not loaded"}
                public_key: Any = self.ca_cert.public_key()
                public_key.verify(
                    client_cert.signature,
                    client_cert.tbs_certificate_bytes,
                    padding.PKCS1v15(),
                    client_cert.signature_hash_algorithm
                )
            except Exception as e:
                return {"valid": False, "error": f"Signature verification failed: {str(e)}"}

            # Extract subject information
            subject = {}
            for attr in client_cert.subject:
                subject[attr.oid._name] = attr.value

            # Calculate fingerprint
            fingerprint = hashlib.sha256(cert_der).hexdigest()

            return {
                "valid": True,
                "mtls_verified": True,
                "subject": subject,
                "serial_number": client_cert.serial_number,
                "fingerprint": fingerprint,
                "issuer": client_cert.issuer.rfc4514_string(),
                "not_after": client_cert.not_valid_after_utc.isoformat()
            }

        except Exception as e:
            return {"valid": False, "error": str(e)}

    def revoke_certificate(self, serial_number: int):
        """Add certificate to revocation list"""
        self.revoked_serials.add(serial_number)


class OAuth2Handler:
    """OAuth2 Provider Integration"""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self._state_cache: dict[str, str] = {}  # state -> user_id mapping

    def generate_authorization_url(self, provider: str, redirect_uri: str, user_id: str) -> str:
        """Generate OAuth2 authorization URL"""
        if provider not in self.config.oauth2_providers:
            raise ValueError(f"Unknown OAuth2 provider: {provider}")

        prov_config = self.config.oauth2_providers[provider]
        state = secrets.token_hex(16)
        self._state_cache[state] = user_id

        params = {
            "client_id": prov_config["client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(prov_config["scopes"]),
            "state": state,
            "access_type": "offline",
            "prompt": "consent"
        }

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{prov_config['authorize_url']}?{query}"

    async def exchange_code_for_token(self, provider: str, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange authorization code for access token"""
        import aiohttp

        if provider not in self.config.oauth2_providers:
            raise ValueError(f"Unknown OAuth2 provider: {provider}")

        prov_config = self.config.oauth2_providers[provider]

        async with aiohttp.ClientSession() as session:
            async with session.post(
                prov_config["token_url"],
                data={
                    "client_id": prov_config["client_id"],
                    "client_secret": prov_config["client_secret"],
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code"
                },
                headers={"Accept": "application/json"}
            ) as response:
                if response.status != 200:
                    raise ValueError(f"Token exchange failed: {await response.text()}")

                return await response.json()

    async def get_user_info(self, provider: str, access_token: str) -> dict[str, Any]:
        """Fetch user information from OAuth2 provider"""
        import aiohttp

        if provider not in self.config.oauth2_providers:
            raise ValueError(f"Unknown OAuth2 provider: {provider}")

        prov_config = self.config.oauth2_providers[provider]

        async with aiohttp.ClientSession() as session:
            async with session.get(
                prov_config["userinfo_url"],
                headers={"Authorization": f"Bearer {access_token}"}
            ) as response:
                if response.status != 200:
                    raise ValueError(f"User info fetch failed: {await response.text()}")

                return await response.json()


class RBACManager:
    """Role-Based Access Control Manager"""

    # Predefined Roles with Permissions
    ROLES = {
        "super_admin": {
            "inherits": [],
            "permissions": ["*"]  # All permissions
        },
        "admin": {
            "inherits": ["developer"],
            "permissions": [
                "users:read", "users:write", "users:delete",
                "projects:read", "projects:write", "projects:delete",
                "uploads:read", "uploads:write", "uploads:delete",
                "settings:read", "settings:write",
                "logs:read", "metrics:read",
                "feature_flags:read", "feature_flags:write"
            ]
        },
        "developer": {
            "inherits": ["viewer"],
            "permissions": [
                "projects:read", "projects:write",
                "uploads:read", "uploads:write",
                "artifacts:read", "artifacts:write",
                "logs:read"
            ]
        },
        "cli_service": {
            "inherits": ["developer"],
            "permissions": [
                "projects:*", "uploads:*", "artifacts:*",
                "sync:execute", "delta:apply"
            ]
        },
        "viewer": {
            "inherits": [],
            "permissions": [
                "projects:read", "uploads:read", "artifacts:read"
            ]
        },
        "anonymous": {
            "inherits": [],
            "permissions": ["health:read"]
        }
    }

    @classmethod
    def get_effective_permissions(cls, roles: list[str]) -> set[str]:
        """Calculate effective permissions from role hierarchy"""
        permissions = set()
        visited = set()

        def collect_permissions(role_name: str):
            if role_name in visited:
                return
            visited.add(role_name)

            if role_name not in cls.ROLES:
                return

            role_data = cls.ROLES[role_name]

            # Add inherited permissions
            for inherited_role in role_data.get("inherits", []):
                collect_permissions(inherited_role)

            # Add direct permissions
            for perm in role_data.get("permissions", []):
                permissions.add(perm)

        for role in roles:
            collect_permissions(role)

        return permissions

    @classmethod
    def check_permission(cls, user_roles: list[str], required_permission: str) -> bool:
        """Check if user has required permission"""
        effective_perms = cls.get_effective_permissions(user_roles)

        # Wildcard permission grants all
        if "*" in effective_perms:
            return True

        # Exact match or resource-level wildcard
        resource = required_permission.split(":")[0] if ":" in required_permission else required_permission
        resource_wildcard = f"{resource}:*"

        return required_permission in effective_perms or resource_wildcard in effective_perms


class SecurityMiddleware:
    """FastAPI Security Middleware"""

    def __init__(self, jwt_manager: JWTManager, mtls_validator: mTLSValidator, rbac_manager: RBACManager):
        self.jwt_manager = jwt_manager
        self.mtls_validator = mtls_validator
        self.rbac_manager = rbac_manager

    async def authenticate_request(self, headers: dict[str, str], client_cert: Optional[bytes] = None) -> TokenClaims:
        """Authenticate incoming request"""
        # Extract Authorization header
        auth_header = headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise jwt.InvalidTokenError("Missing or invalid Authorization header")

        token = auth_header[7:]  # Remove "Bearer " prefix
        claims = self.jwt_manager.verify_token(token)

        # Validate mTLS if enabled and certificate provided
        if client_cert:
            cert_result = self.mtls_validator.validate_client_cert(client_cert)
            if not cert_result["valid"]:
                raise jwt.InvalidTokenError(f"mTLS validation failed: {cert_result['error']}")

            claims.mtls_verified = True
            claims.cert_fingerprint = cert_result.get("fingerprint")

        return claims

    def authorize_request(self, claims: TokenClaims, required_permission: str):
        """Authorize request based on RBAC"""
        if not self.rbac_manager.check_permission(claims.roles, required_permission):
            raise PermissionError(f"Insufficient permissions. Required: {required_permission}")


# Factory function to create configured security components
def create_security_components(config: Optional[SecurityConfig] = None) -> dict[str, Any]:
    """Create and configure all security components"""
    cfg = config or SecurityConfig()

    jwt_mgr = JWTManager(cfg)
    mtls_val = mTLSValidator(cfg)
    oauth2_hdl = OAuth2Handler(cfg)
    rbac_mgr = RBACManager()
    sec_mid = SecurityMiddleware(jwt_mgr, mtls_val, rbac_mgr)

    return {
        "config": cfg,
        "jwt_manager": jwt_mgr,
        "mtls_validator": mtls_val,
        "oauth2_handler": oauth2_hdl,
        "rbac_manager": rbac_mgr,
        "security_middleware": sec_mid
    }
