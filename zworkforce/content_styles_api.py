"""HTTP transport for Universal Content Factory & Style Registry."""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote


def content_styles_get(app, tenant_id: str, path: str, query: dict) -> tuple[bool, Any]:
    """Handles GET /api/v1/content-styles/..."""
    if path == "/api/v1/content-styles/presets" or path == "/api/v1/content-styles":
        category = query.get("category", [None])[0]
        presets = app.db.list_content_style_presets(tenant_id, category=category)
        return True, {"presets": presets, "total": len(presets)}

    if path.startswith("/api/v1/content-styles/presets/"):
        style_id = unquote(path.removeprefix("/api/v1/content-styles/presets/"))
        preset = app.db.get_content_style_preset(tenant_id, style_id)
        if not preset:
            return True, {"_status": 404, "_error": ("preset_not_found", "Style preset not found")}
        return True, {"preset": preset}

    if path == "/api/v1/content-styles/categories":
        presets = app.db.list_content_style_presets(tenant_id)
        categories: dict[str, int] = {}
        for p in presets:
            cat = p.get("category", "General")
            categories[cat] = categories.get(cat, 0) + 1
        return True, {"categories": categories, "total_categories": len(categories), "total_presets": len(presets)}

    return False, None


def content_styles_post(
    app, principal, tenant_id: str, path: str, body: dict, query: dict, idem_key: str
) -> tuple[bool, Any, int]:
    """Handles POST /api/v1/content-styles/..."""
    if path == "/api/v1/content-styles/creative-briefs":
        brief_id = str(body.get("id", "")).strip()
        style_id = str(body.get("style_id", "")).strip()
        title = str(body.get("title", "")).strip()
        objective = str(body.get("objective", "")).strip()
        if not brief_id or not style_id or not title:
            return True, {"error": {"code": "validation_error", "message": "brief_id, style_id, and title are required"}}, 400

        preset = app.db.get_content_style_preset(tenant_id, style_id)
        if not preset:
            return True, {"error": {"code": "preset_not_found", "message": f"Style preset '{style_id}' not found"}}, 404

        brief = app.db.create_creative_brief(tenant_id, brief_id, style_id, title, objective, created_by=principal.key_id)
        return True, {"creative_brief": brief, "applied_style": preset}, 201

    return False, None, 404
