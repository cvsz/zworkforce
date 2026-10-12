"""MCP tools for AI Kids Content Factory (deny-by-default for mutations)."""

from __future__ import annotations

from typing import Any

from .kids_factory import (
    build_storyboard,
    kids_safety_check,
    validate_character,
    validate_episode,
    validate_scene,
    validate_script,
)

KIDS_MCP_TOOLS: dict[str, dict[str, Any]] = {
    "kids.list_brands": {
        "name": "kids.list_brands",
        "description": "List Kids Factory brand profiles for the tenant.",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.create_episode_draft": {
        "name": "kids.create_episode_draft",
        "description": "Create a Kids Factory episode draft (requires automation:write).",
        "inputSchema": {"type": "object", "properties": {
            "id": {"type": "string"}, "brand_id": {"type": "string"}, "title": {"type": "string"},
            "summary": {"type": "string"}, "age_band": {"type": "string"}, "language": {"type": "string"}},
            "required": ["id", "brand_id", "title"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.generate_script": {
        "name": "kids.generate_script",
        "description": "Generate a structured mock script draft for an episode (synthetic fixture).",
        "inputSchema": {"type": "object", "properties": {
            "episode_id": {"type": "string"}, "content_type": {"type": "string"}}, "required": ["episode_id"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    },
    "kids.create_storyboard": {
        "name": "kids.create_storyboard",
        "description": "Build a deterministic storyboard from the latest script.",
        "inputSchema": {"type": "object", "properties": {
            "episode_id": {"type": "string"}, "num_scenes": {"type": "integer"}}, "required": ["episode_id"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    },
    "kids.request_character_review": {
        "name": "kids.request_character_review",
        "description": "Request human review for a character (locks reference and opens approval).",
        "inputSchema": {"type": "object", "properties": {"character_id": {"type": "string"}}, "required": ["character_id"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    },
    "kids.generate_scene_assets": {
        "name": "kids.generate_scene_assets",
        "description": "Register clearly-labeled synthetic scene assets (mock provider, no real generation).",
        "inputSchema": {"type": "object", "properties": {
            "episode_id": {"type": "string"}, "scene_id": {"type": "string"}}, "required": ["episode_id", "scene_id"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    },
    "kids.submit_render": {
        "name": "kids.submit_render",
        "description": "Submit a deterministic sample render (FFmpeg local, synthetic).",
        "inputSchema": {"type": "object", "properties": {
            "episode_id": {"type": "string"}, "preset": {"type": "string"}}, "required": ["episode_id"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.get_render_status": {
        "name": "kids.get_render_status",
        "description": "Read a Kids Factory render job by id.",
        "inputSchema": {"type": "object", "properties": {"render_job_id": {"type": "string"}}, "required": ["render_job_id"]},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.request_publish_approval": {
        "name": "kids.request_publish_approval",
        "description": "Request human approval before any YouTube publishing (mandatory gate).",
        "inputSchema": {"type": "object", "properties": {"episode_id": {"type": "string"}}, "required": ["episode_id"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    },
    "kids.get_video_analytics": {
        "name": "kids.get_video_analytics",
        "description": "Read synthetic analytics snapshots (explicitly labeled, never fabricated as real).",
        "inputSchema": {"type": "object", "properties": {"channel_id": {"type": "string"}}},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
}


def call_kids_tool(app, principal, tenant_id: str, name: str, args: dict[str, Any]) -> Any:
    """Dispatch kids.* tools with explicit authorization. Raises on misuse."""
    from .security import AuthManager

    def require(role: str, scope: str) -> None:
        if not AuthManager.require(principal, role, scope):
            raise PermissionError(f"{role} role and {scope} scope required")

    db = app.db
    actor = principal.name
    if name == "kids.list_brands":
        require("viewer", "workforce:read")
        return {"items": db.kids_list_brands(tenant_id, limit=int(args.get("limit", 50) or 50))}
    if name == "kids.create_episode_draft":
        require("operator", "automation:write")
        validated = validate_episode(args)
        from .kids_api import _slug_or_raise  # reuse slug guard
        episode_id = _slug_or_raise(args.get("id", ""), "episode.id")
        brand_id = _slug_or_raise(args.get("brand_id", ""), "episode.brand_id")
        episode, created = db.kids_create_episode(tenant_id, episode_id, brand_id, validated, actor)
        return {"created": created, "episode": episode}
    if name == "kids.generate_script":
        require("operator", "automation:write")
        episode_id = str(args.get("episode_id", ""))
        episode = db.kids_get_episode(tenant_id, episode_id)
        if not episode:
            raise ValueError("episode not found")
        body = {
            "hook": f"Hello friends! Let's learn with {episode.get('title', 'LumiKids')}",
            "intro": "Original preschool intro song",
            "concept": f"Learn: {', '.join(episode.get('objectives', []) or ['colors'])}",
            "repetition": "Sing it again!",
            "dialogue": "Lumi: What color is this?",
            "verses": "Red bus, blue sky, yellow sun up high",
            "chorus": "Colors, colors, we all love colors",
            "transitions": "Rolling to the next stop",
            "ending": "Great job, little learners!",
        }
        validated = validate_script({"content_type": str(args.get("content_type", "nursery_rhyme")), "body": body})
        return db.kids_save_script(tenant_id, episode_id, validated, actor)
    if name == "kids.create_storyboard":
        require("operator", "automation:write")
        episode_id = str(args.get("episode_id", ""))
        script = db.kids_latest_script(tenant_id, episode_id)
        plan = build_storyboard(script_body=((script or {}).get("body") or {}), num_scenes=int(args.get("num_scenes", 4) or 4))
        saved = []
        for index, item in enumerate(plan):
            saved.append(db.kids_upsert_scene(tenant_id, episode_id, f"s{index + 1:02d}", validate_scene(item), actor))
        return {"items": saved}
    if name == "kids.request_character_review":
        require("operator", "automation:write")
        character_id = str(args.get("character_id", ""))
        char = db.kids_get_character(tenant_id, character_id)
        if not char:
            raise ValueError("character not found")
        db.kids_lock_character(tenant_id, character_id, actor, locked=True)
        return {"character_id": character_id, "locked": True, "note": "human approval required before publishing the Character Bible"}
    if name == "kids.generate_scene_assets":
        require("operator", "automation:write")
        episode_id = str(args.get("episode_id", "")); scene_id = str(args.get("scene_id", ""))
        asset = db.kids_register_asset(tenant_id, {
            "episode_id": episode_id, "scene_id": scene_id, "kind": "image",
            "name": f"{scene_id}-synthetic.png", "storage_uri": "synthetic://mock/scene",
            "sha256": "0" * 64, "size_bytes": 0,
            "provenance": {"provider": "mock", "synthetic": True},
        }, actor)
        return asset
    if name == "kids.submit_render":
        require("operator", "automation:write")
        episode_id = str(args.get("episode_id", ""))
        timeline = db.kids_latest_timeline(tenant_id, episode_id)
        if not timeline:
            raise ValueError("episode has no timeline")
        job, created = db.kids_submit_render(tenant_id, episode_id, int(timeline.get("version", 1)),
                                              str(args.get("preset", "landscape_1080p")), actor)
        return {"created": created, "render_job": job, "note": "render completes via /api/v1/kids/render-jobs (synchronous sample)"}
    if name == "kids.get_render_status":
        require("viewer", "workforce:read")
        job = db.kids_get_render(tenant_id, str(args.get("render_job_id", "")))
        if not job:
            raise ValueError("render job not found")
        return job
    if name == "kids.request_publish_approval":
        require("operator", "automation:write")
        episode_id = str(args.get("episode_id", ""))
        episode = db.kids_get_episode(tenant_id, episode_id)
        if not episode:
            raise ValueError("episode not found")
        report = kids_safety_check(age_band=episode.get("age_band", "preschool"), text=episode.get("summary", ""))
        db.kids_save_moderation(tenant_id, episode_id, report, f"quality-agent:{actor}")
        if not report["passed"]:
            raise ValueError("safety review blocked publishing")
        return db.kids_request_approval(tenant_id, episode_id, "episode", episode_id, int(episode.get("version", 1)), actor)
    if name == "kids.get_video_analytics":
        require("viewer", "workforce:read")
        return {"items": db.kids_list_analytics(tenant_id, channel_id=str(args.get("channel_id", ""))),
                "note": "synthetic fixtures only; real YouTube analytics require authorized API wiring"}
    raise ValueError(f"unknown MCP tool: {name}")
