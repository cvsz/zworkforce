"""Curated Cloudflare API reference and deny-by-default operation planning.

No Cloudflare credentials, API requests, or mutation execution in this module.
"""
from __future__ import annotations

import re
from typing import Any

DOCS = {
    "overview": "https://developers.cloudflare.com/api/overview/",
    "permissions": "https://developers.cloudflare.com/fundamentals/api/reference/permissions/",
    "tokens": "https://developers.cloudflare.com/fundamentals/api/how-to/create-via-api/",
    "tunnels": "https://developers.cloudflare.com/tunnel/get-started/",
}
OPERATIONS = {
    "dns.list": {"method": "GET", "path": "/zones/{zone_id}/dns_records", "permission": "Zone DNS Read", "resource": "zone"},
    "zone.get": {"method": "GET", "path": "/zones/{zone_id}", "permission": "Zone Read", "resource": "zone"},
    "tunnel.list": {"method": "GET", "path": "/accounts/{account_id}/cfd_tunnel", "permission": "Account Cloudflare Tunnel Read", "resource": "account"},
    "dns.create": {"method": "POST", "path": "/zones/{zone_id}/dns_records", "permission": "Zone DNS Write", "resource": "zone"},
    "dns.delete": {"method": "DELETE", "path": "/zones/{zone_id}/dns_records/{record_id}", "permission": "Zone DNS Write", "resource": "zone"},
    "tunnel.create": {"method": "POST", "path": "/accounts/{account_id}/cfd_tunnel", "permission": "Account Cloudflare Tunnel Write", "resource": "account"},
}
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.]{2,63}$")


def references() -> dict[str, Any]:
    return {"official_sources": [{"id": key, "url": value} for key, value in DOCS.items()],
            "api_base": "https://api.cloudflare.com/client/v4",
            "live_verified": False, "execution_available": False}


def operation_plan(operation: str) -> dict[str, Any]:
    if not isinstance(operation, str) or not IDENTIFIER.fullmatch(operation):
        raise ValueError("invalid Cloudflare operation identifier")
    spec = OPERATIONS.get(operation)
    if spec is None:
        raise ValueError("unsupported Cloudflare operation")
    mutating = spec["method"] != "GET"
    return {
        "operation": operation,
        **spec,
        "api_base": "https://api.cloudflare.com/client/v4",
        "execute": False,
        "requires_resource_ownership_evidence": True,
        "requires_explicit_approval": mutating,
        "requires_reviewed_plan_digest": mutating,
        "requirements": ["tenant-scoped server-side API token", "resource allowlist",
                         "approved ownership manifest", "audit trail",
                         "Cloudflare API permission limited to exact resource"],
        "warning": "This is documentation-only; it does not authorize or execute changes",
    }
