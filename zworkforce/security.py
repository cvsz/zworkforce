from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from typing import Any
import uuid

ROLE_LEVEL = {"viewer": 1, "operator": 2, "admin": 3, "superadmin": 4}
TENANT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
SENSITIVE_KEYS = {"authorization", "api_key", "apikey", "token", "password", "secret", "credential", "cookie", "set-cookie"}
PBKDF2_SCHEME = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000
PBKDF2_SALT_BYTES = 16
PBKDF2_MIN_ITERATIONS = 100_000
PBKDF2_MAX_ITERATIONS = 1_000_000


@dataclass(frozen=True)
class Principal:
    name: str
    role: str
    tenant_id: str
    scopes: tuple[str, ...]
    key_id: str

    def has_scope(self, scope: str) -> bool:
        return "*" in self.scopes or scope in self.scopes


class AuthManager:
    def __init__(self, db, bootstrap_keys=(), trust_proxy_identity: bool = False, proxy_identity_secret: str = "", oidc=None,
                 metrics_bearer: str = "", metrics_tenant_id: str = "default"):
        self.db = db
        self.trust_proxy_identity = trust_proxy_identity
        self.proxy_identity_secret = proxy_identity_secret
        self.oidc = oidc
        self.metrics_bearer = metrics_bearer.strip()
        self.metrics_tenant_id = metrics_tenant_id
        for item in bootstrap_keys:
            key_id = _bootstrap_key_id(item.tenant_id, item.name)
            self.db.upsert_api_key(key_id, item.tenant_id, item.name, _hash_secret(item.secret), item.role, list(item.scopes))

    def authenticate(self, authorization: str | None, x_api_key: str | None, proxy_headers: dict[str, str] | None = None) -> Principal | None:
        if self.trust_proxy_identity and proxy_headers:
            principal = self._proxy_principal(proxy_headers)
            if principal:
                return principal
        if authorization and authorization.lower().startswith("bearer ") and self.oidc:
            token = authorization[7:].strip()
            try:
                claims = self.oidc.verify(token)
                return Principal(claims["name"], claims["role"], claims["tenant_id"], tuple(claims.get("scopes") or ["*"]), "oidc")
            except Exception:
                pass
        candidate = x_api_key or ""
        if authorization and authorization.lower().startswith("bearer "):
            candidate = authorization[7:].strip()
        if not candidate:
            return None
        if self.metrics_bearer and hmac.compare_digest(candidate, self.metrics_bearer):
            return Principal("metrics-scraper", "viewer", self.metrics_tenant_id, ("metrics:read",), "metrics-bearer")
        for row in self.db.list_active_api_keys(limit=10_000):
            if not _verify_secret(row.get("key_hash", ""), candidate):
                continue
            self.db.touch_api_key(row["id"])
            scopes = tuple(row.get("scopes") or ["*"])
            return Principal(row["name"], row["role"], row["tenant_id"], scopes, row["id"])
        return None

    def _proxy_principal(self, headers: dict[str, str]) -> Principal | None:
        name = headers.get("X-Forwarded-User", "").strip()
        role = headers.get("X-Forwarded-Role", "").strip().lower()
        tenant = headers.get("X-Forwarded-Tenant", "").strip().lower()
        scopes_raw = headers.get("X-Forwarded-Scopes", "*").strip()
        signature = headers.get("X-ZWorkforce-Proxy-Signature", "").strip().lower()
        timestamp = headers.get("X-ZWorkforce-Proxy-Timestamp", "").strip()
        if not (name and role in ROLE_LEVEL and TENANT_RE.fullmatch(tenant) and scopes_raw and signature and timestamp and self.proxy_identity_secret):
            return None
        try:
            ts = int(timestamp)
        except ValueError:
            return None
        if abs(int(time.time()) - ts) > 60:
            return None
        material = f"{name}\n{role}\n{tenant}\n{scopes_raw}\n{timestamp}".encode()
        expected = hmac.new(self.proxy_identity_secret.encode(), material, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return None
        scopes = tuple(s.strip() for s in scopes_raw.split(",") if s.strip())
        if not scopes:
            return None
        return Principal(name, role, tenant, scopes, "proxy")

    @staticmethod
    def require(principal: Principal | None, role: str, scope: str | None = None) -> bool:
        if principal and principal.key_id == "metrics-bearer" and (role != "viewer" or scope != "metrics:read"):
            return False
        if not principal or ROLE_LEVEL.get(principal.role, 0) < ROLE_LEVEL.get(role, 999):
            return False
        return not scope or principal.has_scope(scope)

    def create_key(self, tenant_id: str, name: str, role: str, scopes: list[str]) -> tuple[str, str]:
        if role not in ROLE_LEVEL:
            raise ValueError("invalid role")
        if not TENANT_RE.fullmatch(tenant_id):
            raise ValueError("invalid tenant")
        if not name.strip() or len(name) > 100:
            raise ValueError("key name is required and must be <= 100 characters")
        secret = "zwf_" + secrets.token_urlsafe(32)
        key_id = self.db.create_api_key_record(tenant_id, name.strip(), _hash_secret(secret), role, scopes or ["*"])
        return key_id, secret


class RateLimiter:
    def __init__(self, limit_per_minute: int):
        self.limit = max(1, int(limit_per_minute))
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - 60.0
        with self._lock:
            q = self._events[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.limit:
                retry = max(1, int(60 - (now - q[0])))
                return False, retry
            q.append(now)
            if len(self._events) > 10_000:
                for stale in list(self._events)[:1000]:
                    if not self._events[stale] or self._events[stale][-1] < cutoff:
                        self._events.pop(stale, None)
            return True, 0


def _bootstrap_key_id(tenant_id: str, name: str) -> str:
    material = f"zworkforce/bootstrap/{tenant_id}/{name}"
    return "bootstrap-" + uuid.uuid5(uuid.NAMESPACE_URL, material).hex


def _hash_secret(secret: str, salt: bytes | None = None) -> str:
    salt = salt if salt is not None else secrets.token_bytes(PBKDF2_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{PBKDF2_SCHEME}${PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def _verify_secret(stored: str, candidate: str) -> bool:
    if not isinstance(stored, str):
        return False
    parts = stored.split("$")
    if len(parts) == 4 and parts[0] == PBKDF2_SCHEME:
        try:
            iterations = int(parts[1])
            salt = bytes.fromhex(parts[2])
            expected = bytes.fromhex(parts[3])
        except ValueError:
            return False
        if not PBKDF2_MIN_ITERATIONS <= iterations <= PBKDF2_MAX_ITERATIONS or not salt or not expected:
            return False
        derived = hashlib.pbkdf2_hmac("sha256", candidate.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(derived, expected)
    return False


def resolve_tenant(principal: Principal, requested: str | None) -> str:
    if principal.role == "superadmin" and requested:
        tenant = requested.strip().lower()
        if not TENANT_RE.fullmatch(tenant):
            raise ValueError("invalid X-Tenant-ID")
        return tenant
    return principal.tenant_id


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS or any(word in str(key).lower() for word in ("secret", "token", "password", "api_key")):
                out[key] = "[REDACTED]"
            else:
                out[key] = redact(item)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact(v) for v in value)
    if isinstance(value, str) and len(value) > 8000:
        return value[:8000] + "…"
    return value


def canonical_request_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
