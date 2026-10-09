"""Bounded, tenant-scoped, read-only Cloudflare API access."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

_API = "https://api.cloudflare.com/client/v4"
_ID = re.compile(r"^[a-fA-F0-9]{32}$")
_ALLOWED = {"zones", "dns_records", "tunnels"}
_MAX_BYTES = 1024 * 1024


class CloudflareReadError(ValueError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CloudflareReadError("Cloudflare API redirect rejected")


def _config(tenant_id: str, resource: str, resource_id: str) -> str:
    """Only trusted server configuration decides which token and resources are accessible."""
    try:
        config = json.loads(os.environ.get("ZWORKFORCE_CLOUDFLARE_READ_TENANTS", "{}"))
    except (ValueError, TypeError) as exc:
        raise CloudflareReadError("Invalid server Cloudflare tenant configuration") from exc
    if not isinstance(config, dict):
        raise CloudflareReadError("Invalid server Cloudflare tenant configuration")
    tenant = config.get(tenant_id)
    if not isinstance(tenant, dict):
        raise PermissionError("Cloudflare access not configured for tenant")
    allowed = tenant.get("zone_ids" if resource == "dns_records" else "account_ids")
    if resource == "zones":
        allowed = tenant.get("zone_ids")
        if not isinstance(allowed, list) or not allowed:
            raise PermissionError("No allowlisted zones")
    elif not isinstance(allowed, list) or resource_id not in allowed:
        raise PermissionError("Cloudflare resource is not allowlisted for tenant")
    if not isinstance(allowed, list) or any(not isinstance(x, str) or not _ID.fullmatch(x) for x in allowed):
        raise CloudflareReadError("Invalid resource allowlist configuration")
    token_var = tenant.get("token_env")
    if not isinstance(token_var, str) or not re.fullmatch(r"ZWORKFORCE_CF_TOKEN_[A-Z0-9_]{1,64}", token_var):
        raise CloudflareReadError("Invalid server-side token reference")
    token = os.environ.get(token_var, "")
    if not token:
        raise CloudflareReadError("Cloudflare token is not configured")
    return token


def read(tenant_id: str, resource: str, resource_id: str = "", page: int = 1) -> dict[str, Any]:
    if type(page) is not int or not 1 <= page <= 10:
        raise CloudflareReadError("page must be an integer between 1 and 10")
    if resource not in _ALLOWED:
        raise CloudflareReadError("Unsupported read resource")
    if resource == "zones":
        if resource_id:
            raise CloudflareReadError("zones does not accept resource_id")
    elif not isinstance(resource_id, str) or not _ID.fullmatch(resource_id):
        raise CloudflareReadError("Invalid Cloudflare resource ID")
    token = _config(tenant_id, resource, resource_id)
    path = {
        "zones": "/zones",
        "dns_records": f"/zones/{resource_id}/dns_records",
        "tunnels": f"/accounts/{resource_id}/cfd_tunnel",
    }[resource]
    request = urllib.request.Request(
        _API + path + f"?per_page=50&page={page}",
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.build_opener(_NoRedirect).open(request, timeout=8) as response:
            if response.status != 200:
                raise CloudflareReadError("Cloudflare API returned non-success status")
            raw = response.read(_MAX_BYTES + 1)
    except (OSError, urllib.error.URLError) as exc:
        raise CloudflareReadError("Cloudflare API request failed") from exc
    if len(raw) > _MAX_BYTES:
        raise CloudflareReadError("Cloudflare response too large")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise CloudflareReadError("Invalid Cloudflare API response") from exc
    if not isinstance(payload, dict) or payload.get("success") is not True or not isinstance(payload.get("result"), list):
        raise CloudflareReadError("Cloudflare API returned an unsuccessful response")
    # No provider object is returned wholesale. Only inventory fields relevant to operators.
    fields = {
        "zones": ("id", "name", "status"),
        "dns_records": ("id", "type", "name", "content", "proxied", "ttl"),
        "tunnels": ("id", "name", "status", "created_at"),
    }[resource]
    items = [{key: row[key] for key in fields if key in row and isinstance(row[key], (str, int, bool, type(None)))}
             for row in payload["result"] if isinstance(row, dict)]
    if resource == "zones":
        config = json.loads(os.environ["ZWORKFORCE_CLOUDFLARE_READ_TENANTS"])
        allowed = set(config[tenant_id]["zone_ids"])
        items = [item for item in items if item.get("id") in allowed]
    info = payload.get("result_info") or {}
    if not isinstance(info, dict):
        info = {}
    total_pages = info.get("total_pages")
    has_more = total_pages > page if type(total_pages) is int and total_pages >= 1 else None
    if resource == "tunnels" and has_more is None:
        total_count = info.get("total_count")
        if type(total_count) is int and total_count >= 0:
            has_more = page * 50 < total_count
    if resource == "zones":
        # Provider totals describe zones outside the tenant allowlist.
        has_more = None
    return {"resource": resource, "items": items, "page": page, "has_more": has_more, "partial": True,
            "source": "Cloudflare API", "live": True}
