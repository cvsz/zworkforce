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
    "kids.create_campaign": {
        "name": "kids.create_campaign",
        "description": "Create a content campaign plan for a brand (requires automation:write).",
        "inputSchema": {"type": "object", "properties": {
            "id": {"type": "string"}, "brand_id": {"type": "string"}, "name": {"type": "string"},
            "topic": {"type": "string"}}, "required": ["id", "brand_id", "name"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.create_language_variant": {
        "name": "kids.create_language_variant",
        "description": "Draft a language variant shell for an episode (machine draft, needs human review).",
        "inputSchema": {"type": "object", "properties": {
            "episode_id": {"type": "string"}, "id": {"type": "string"}, "language": {"type": "string"}},
            "required": ["episode_id", "language"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.suggest_marketing": {
        "name": "kids.suggest_marketing",
        "description": "Draft marketing suggestions for an episode (estimates only, human-editable).",
        "inputSchema": {"type": "object", "properties": {"episode_id": {"type": "string"}}, "required": ["episode_id"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.queue_render": {
        "name": "kids.queue_render",
        "description": "Queue a render job for later tick processing (idempotent).",
        "inputSchema": {"type": "object", "properties": {
            "episode_id": {"type": "string"}, "preset": {"type": "string"}}, "required": ["episode_id"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.tick_render_queue": {
        "name": "kids.tick_render_queue",
        "description": "Process the oldest queued render job once (bounded attempts, dead-letter after 3).",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    },
    "kids.tick_all_renders": {
        "name": "kids.tick_all_renders",
        "description": "Process up to N queued render jobs (bounded fan-out, default 5, max 20).",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    },
    "kids.get_episode_cost": {
        "name": "kids.get_episode_cost",
        "description": "Cost breakdown for one episode from the recorded usage ledger.",
        "inputSchema": {"type": "object", "properties": {"episode_id": {"type": "string"}}, "required": ["episode_id"]},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.export_captions": {
        "name": "kids.export_captions",
        "description": "Build SRT/VTT/JSON caption tracks from episode scenes with timings.",
        "inputSchema": {"type": "object", "properties": {
            "episode_id": {"type": "string"}, "format": {"type": "string"}}, "required": ["episode_id"]},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.list_playlists": {
        "name": "kids.list_playlists",
        "description": "Playlist planning view: campaigns with ordered episode titles.",
        "inputSchema": {"type": "object", "properties": {"brand_id": {"type": "string"}}},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.submit_translation": {
        "name": "kids.submit_translation",
        "description": "Submit human translation lines for episode scenes (requires automation:write).",
        "inputSchema": {"type": "object", "properties": {
            "episode_id": {"type": "string"}, "scenes": {"type": "array"}}, "required": ["episode_id", "scenes"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    },
    "kids.create_schedule": {
        "name": "kids.create_schedule",
        "description": "Schedule an episode for a channel slot (future ISO-8601 with timezone; conflicts fail).",
        "inputSchema": {"type": "object", "properties": {
            "channel_id": {"type": "string"}, "episode_id": {"type": "string"}, "slot_at": {"type": "string"}},
            "required": ["channel_id", "episode_id", "slot_at"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.list_schedules": {
        "name": "kids.list_schedules",
        "description": "List scheduled publishing slots.",
        "inputSchema": {"type": "object", "properties": {"channel_id": {"type": "string"}}},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.set_provider_route": {
        "name": "kids.set_provider_route",
        "description": "Set the ordered provider route for a capability (requires automation:write).",
        "inputSchema": {"type": "object", "properties": {
            "capability": {"type": "string"}, "providers": {"type": "array"}}, "required": ["capability", "providers"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.resolve_provider": {
        "name": "kids.resolve_provider",
        "description": "Resolve the provider route for a capability with enabled flags and cost preview.",
        "inputSchema": {"type": "object", "properties": {"capability": {"type": "string"}}, "required": ["capability"]},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.export_episode": {
        "name": "kids.export_episode",
        "description": "Export the full episode bundle for backup/restore drills.",
        "inputSchema": {"type": "object", "properties": {"episode_id": {"type": "string"}}, "required": ["episode_id"]},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.import_episode": {
        "name": "kids.import_episode",
        "description": "Restore an episode creative graph from an export bundle (same tenant; approvals must be re-done).",
        "inputSchema": {"type": "object", "properties": {
            "bundle": {"type": "object"}, "id": {"type": "string"}}, "required": ["bundle"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    },
    "kids.get_analytics_summary": {
        "name": "kids.get_analytics_summary",
        "description": "Aggregate persisted Kids Factory rows (never fabricated views).",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.derive_shorts": {
        "name": "kids.derive_shorts",
        "description": "Derive a 9:16 short-form episode from a landscape episode (requires automation:write).",
        "inputSchema": {"type": "object", "properties": {
            "episode_id": {"type": "string"}, "id": {"type": "string"}}, "required": ["episode_id"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.list_brands": {
        "name": "kids.list_brands",
        "description": "List Kids Factory brand profiles for the tenant.",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.list_campaigns": {
        "name": "kids.list_campaigns",
        "description": "List Kids Factory campaigns for the tenant.",
        "inputSchema": {"type": "object", "properties": {"brand_id": {"type": "string"}}},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "kids.run_episode_pipeline": {
        "name": "kids.run_episode_pipeline",
        "description": "Run the pre-publish agent pipeline for an episode (bounded, idempotent steps; publishing stays manual).",
        "inputSchema": {"type": "object", "properties": {
            "episode_id": {"type": "string"}, "preset": {"type": "string"}, "num_scenes": {"type": "integer"}},
            "required": ["episode_id"]},
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
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
    if name == "kids.list_campaigns":
        require("viewer", "workforce:read")
        return {"items": db.kids_list_campaigns(tenant_id, brand_id=str(args.get("brand_id", "")))}
    if name == "kids.create_campaign":
        require("operator", "automation:write")
        from .kids_api import _slug_or_raise
        campaign_id = _slug_or_raise(args.get("id", ""), "campaign.id")
        brand_id = _slug_or_raise(args.get("brand_id", ""), "campaign.brand_id")
        if not db.kids_get_brand(tenant_id, brand_id):
            raise ValueError("campaign.brand_id does not exist in this tenant")
        if not str(args.get("name", "")).strip():
            raise ValueError("campaign.name is required")
        return db.kids_upsert_campaign(tenant_id, campaign_id, brand_id, args, actor)
    if name == "kids.run_episode_pipeline":
        require("operator", "automation:write")
        from .kids_workflow import run_episode_pipeline
        return run_episode_pipeline(app, tenant_id, str(args.get("episode_id", "")), actor,
                                    preset=str(args.get("preset", "landscape_1080p")),
                                    num_scenes=int(args.get("num_scenes", 4) or 4))
    if name == "kids.derive_shorts":
        require("operator", "automation:write")
        from .kids_api import _slug_or_raise
        from .kids_factory import check_brand_quota, storyboard_to_timeline
        parent_id = str(args.get("episode_id", ""))
        parent = db.kids_get_episode(tenant_id, parent_id)
        if not parent:
            raise ValueError("episode not found")
        child_id = _slug_or_raise(args.get("id", f"{parent_id}-shorts"), "episode.id")
        check_brand_quota(db, tenant_id, parent["brand_id"], extra_episodes=1)
        child_validated = validate_episode({"title": f"{parent['title']} (Shorts)", "summary": parent.get("summary", ""),
                                            "age_band": parent.get("age_band", "preschool"),
                                            "language": parent.get("language", "en"),
                                            "objectives": parent.get("objectives", []),
                                            "vocabulary": parent.get("vocabulary", [])})
        child, created = db.kids_create_episode(tenant_id, child_id, parent["brand_id"], child_validated, actor,
                                                channel_id=parent.get("channel_id", ""))
        if created:
            for index, scene in enumerate(db.kids_list_scenes(tenant_id, parent_id)[:3]):
                db.kids_upsert_scene(tenant_id, child_id, f"s{index + 1:02d}",
                                     validate_scene({**scene, "ordering": index}), actor)
            db.kids_save_timeline(tenant_id, child_id, storyboard_to_timeline(db.kids_list_scenes(tenant_id, child_id)), actor)
            db.kids_record_derivation(tenant_id, parent_id, child_id, "shorts", actor)
        return {"created": created, "episode": child, "preset": "portrait_1080x1920"}
    if name == "kids.create_language_variant":
        require("operator", "automation:write")
        from .kids_api import _slug_or_raise as _slug2
        from .kids_factory import build_language_variant, check_brand_quota as _quota
        parent = db.kids_get_episode(tenant_id, str(args.get("episode_id", "")))
        if not parent:
            raise ValueError("episode not found")
        language = str(args.get("language", "")).strip().lower()
        child_id = _slug2(args.get("id", f"{parent['id']}-{language or 'variant'}"), "episode.id")
        _quota(db, tenant_id, parent["brand_id"], extra_episodes=1)
        draft = build_language_variant(parent=parent, language=language)
        child, created = db.kids_create_episode(tenant_id, child_id, parent["brand_id"],
                                                {k: draft[k] for k in ("title", "summary", "age_band", "language", "objectives", "vocabulary", "budget_credits")},
                                                actor, channel_id=parent.get("channel_id", ""))
        if created:
            db.kids_record_derivation(tenant_id, parent["id"], child_id, "language-variant", actor)
        return {"created": created, "episode": child, "translation_status": "needs_review"}
    if name == "kids.suggest_marketing":
        require("operator", "automation:write")
        from .kids_factory import suggest_marketing
        episode = db.kids_get_episode(tenant_id, str(args.get("episode_id", "")))
        if not episode:
            raise ValueError("episode not found")
        brand = db.kids_get_brand(tenant_id, episode.get("brand_id", "")) or {}
        return suggest_marketing(episode=episode, brand_name=brand.get("name", ""))
    if name == "kids.get_analytics_summary":
        from .security import AuthManager as _AM
        if not _AM.require(principal, "viewer", "workforce:read"):
            raise PermissionError("viewer role and workforce:read scope required")
        return db.kids_analytics_summary(tenant_id)
    if name == "kids.queue_render":
        require("operator", "automation:write")
        episode = db.kids_get_episode(tenant_id, str(args.get("episode_id", "")))
        if not episode:
            raise ValueError("episode not found")
        timeline = db.kids_latest_timeline(tenant_id, episode["id"])
        if not timeline:
            raise ValueError("episode has no timeline")
        job, created = db.kids_submit_render(tenant_id, episode["id"], int(timeline.get("version", 1)),
                                              str(args.get("preset", "landscape_1080p")), actor)
        return {"created": created, "render_job": job}
    if name == "kids.tick_render_queue":
        require("operator", "automation:write")
        from .kids_workflow import tick_render_queue
        return tick_render_queue(app, tenant_id, actor)
    if name == "kids.tick_all_renders":
        require("operator", "automation:write")
        from .kids_workflow import tick_all_renders
        try:
            limit = int(args.get("limit", 5) or 5)
        except (TypeError, ValueError):
            raise ValueError("limit must be an integer")
        return tick_all_renders(app, tenant_id, actor, limit=limit)
    if name == "kids.get_episode_cost":
        require("viewer", "workforce:read")
        if not db.kids_get_episode(tenant_id, str(args.get("episode_id", ""))):
            raise ValueError("episode not found")
        return db.kids_episode_cost(tenant_id, str(args.get("episode_id", "")))
    if name == "kids.export_captions":
        require("viewer", "workforce:read")
        from .kids_factory import build_captions_export
        episode_id = str(args.get("episode_id", ""))
        if not db.kids_get_episode(tenant_id, episode_id):
            raise ValueError("episode not found")
        return build_captions_export(scenes=db.kids_list_scenes(tenant_id, episode_id),
                                     format=str(args.get("format", "srt")))
    if name == "kids.list_playlists":
        require("viewer", "workforce:read")
        return {"items": db.kids_playlists(tenant_id, brand_id=str(args.get("brand_id", "")))}
    if name == "kids.submit_translation":
        require("operator", "automation:write")
        episode = db.kids_get_episode(tenant_id, str(args.get("episode_id", "")))
        if not episode:
            raise ValueError("episode not found")
        items = args.get("scenes")
        if not isinstance(items, list) or not items:
            raise ValueError("scenes must be a non-empty list")
        updated = []
        for entry in items[:60]:
            base = next((s for s in db.kids_list_scenes(tenant_id, episode["id"]) if s["id"] == entry.get("id")), None)
            if not base:
                raise ValueError(f"scene '{entry.get('id')}' does not exist in this episode")
            merged = dict(base)
            if str(entry.get("dialogue_line", "")).strip():
                merged["dialogue"] = {**(base.get("dialogue") or {}), "line": str(entry["dialogue_line"])[:280], "translated_by": actor}
            updated.append(db.kids_upsert_scene(tenant_id, episode["id"], base["id"], validate_scene(merged), actor))
        return {"scenes": updated}
    if name == "kids.create_schedule":
        require("operator", "automation:write")
        from .kids_api import _slug_or_raise as _slug3
        from .kids_factory import validate_schedule_slot
        channel_id = _slug3(args.get("channel_id", ""), "schedule.channel_id")
        episode_id = _slug3(args.get("episode_id", ""), "schedule.episode_id")
        if channel_id not in [c["id"] for c in db.kids_list_channels(tenant_id)]:
            raise ValueError("schedule.channel_id does not exist in this tenant")
        if not db.kids_get_episode(tenant_id, episode_id):
            raise ValueError("schedule.episode_id does not exist in this tenant")
        slot = validate_schedule_slot(slot_at=args.get("slot_at", ""), timezone_name=str(args.get("timezone", "UTC")))
        sched, created, conflict = db.kids_create_schedule(tenant_id, channel_id, episode_id, slot, actor)
        if conflict:
            raise ValueError("channel already has a scheduled item at this slot")
        return {"created": created, "schedule": sched}
    if name == "kids.list_schedules":
        require("viewer", "workforce:read")
        return {"items": db.kids_list_schedules(tenant_id, channel_id=str(args.get("channel_id", "")))}
    if name == "kids.set_provider_route":
        require("operator", "automation:write")
        from .kids_factory import resolve_provider_route as _resolve, validate_provider_route as _validate_route
        validated = _validate_route(capability=str(args.get("capability", "")), providers=args.get("providers", []))
        saved = db.kids_set_provider_route(tenant_id, validated["capability"], validated["providers"], actor)
        return dict(saved, resolved=_resolve(capability=validated["capability"], providers=validated["providers"]))
    if name == "kids.resolve_provider":
        require("viewer", "workforce:read")
        from .kids_factory import PROVIDER_CAPABILITIES as _caps, resolve_provider_route as _resolve2
        capability = str(args.get("capability", ""))
        if capability not in _caps:
            raise ValueError("unknown provider capability")
        routes = [r for r in db.kids_list_provider_routes(tenant_id) if r.get("capability") == capability]
        providers = routes[0].get("providers", []) if routes else ["mock"]
        return _resolve2(capability=capability, providers=providers)
    if name == "kids.export_episode":
        require("viewer", "workforce:read")
        bundle = db.kids_export_episode(tenant_id, str(args.get("episode_id", "")))
        if not bundle:
            raise ValueError("episode not found")
        return bundle
    if name == "kids.import_episode":
        require("operator", "automation:write")
        from .kids_api import _slug_or_raise as _slug4
        bundle = args.get("bundle")
        if not isinstance(bundle, dict):
            raise ValueError("bundle must be an object")
        override = _slug4(args.get("id", ""), "episode.id") if args.get("id") else ""
        return db.kids_import_bundle(tenant_id, bundle, actor, episode_id=override)
    if name == "kids.create_episode_draft":
        require("operator", "automation:write")
        validated = validate_episode(args)
        from .kids_api import _slug_or_raise  # reuse slug guard
        episode_id = _slug_or_raise(args.get("id", ""), "episode.id")
        brand_id = _slug_or_raise(args.get("brand_id", ""), "episode.brand_id")
        if not db.kids_get_brand(tenant_id, brand_id):
            raise ValueError("episode.brand_id does not exist in this tenant")
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
        saved = db.kids_save_script(tenant_id, episode_id, validated, actor)
        db.kids_set_episode_status(tenant_id, episode_id, "scripted", actor)
        db.kids_record_usage(tenant_id, episode_id, "mock", "llm", 1.0, 0.2)
        return saved
    if name == "kids.create_storyboard":
        require("operator", "automation:write")
        episode_id = str(args.get("episode_id", ""))
        if not db.kids_get_episode(tenant_id, episode_id):
            raise ValueError("episode not found")
        script = db.kids_latest_script(tenant_id, episode_id)
        plan = build_storyboard(script_body=((script or {}).get("body") or {}), num_scenes=int(args.get("num_scenes", 4) or 4))
        for index, item in enumerate(plan):
            item["id"] = f"s{index + 1:02d}"
        return {"items": db.kids_replace_storyboard(tenant_id, episode_id, plan, actor)}
    if name == "kids.request_character_review":
        require("operator", "automation:write")
        character_id = str(args.get("character_id", ""))
        char = db.kids_get_character(tenant_id, character_id)
        if not char:
            raise ValueError("character not found")
        db.kids_lock_character(tenant_id, character_id, actor, locked=True)
        episode_id = str(args.get("episode_id", "")) or f"character-{character_id}"
        approval = db.kids_request_approval(tenant_id, episode_id, "character", character_id,
                                            int(char.get("version", 1) or 1), actor)
        return {"character_id": character_id, "locked": True, "approval": approval,
                "note": "human approval required before publishing the Character Bible"}
    if name == "kids.generate_scene_assets":
        require("operator", "automation:write")
        episode_id = str(args.get("episode_id", "")); scene_id = str(args.get("scene_id", ""))
        if not db.kids_get_episode(tenant_id, episode_id):
            raise ValueError("episode not found")
        if not any(s["id"] == scene_id for s in db.kids_list_scenes(tenant_id, episode_id)):
            raise ValueError("scene does not exist in this episode")
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
        if not db.kids_get_episode(tenant_id, episode_id):
            raise ValueError("episode not found")
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
        from .kids_factory import build_safety_corpus
        episode_id = str(args.get("episode_id", ""))
        episode = db.kids_get_episode(tenant_id, episode_id)
        if not episode:
            raise ValueError("episode not found")
        corpus = build_safety_corpus(episode=episode, script=db.kids_latest_script(tenant_id, episode_id),
                                     scenes=db.kids_list_scenes(tenant_id, episode_id),
                                     timeline=db.kids_latest_timeline(tenant_id, episode_id))
        report = kids_safety_check(age_band=episode.get("age_band", "preschool"), text=corpus)
        db.kids_save_moderation(tenant_id, episode_id, report, f"quality-agent:{actor}")
        if not report["passed"]:
            raise ValueError("safety review blocked publishing")
        return db.kids_request_approval(tenant_id, episode_id, "episode", episode_id, int(episode.get("version", 1)), actor)
    if name == "kids.get_video_analytics":
        require("viewer", "workforce:read")
        return {"items": db.kids_list_analytics(tenant_id, channel_id=str(args.get("channel_id", ""))),
                "note": "synthetic fixtures only; real YouTube analytics require authorized API wiring"}
    raise ValueError(f"unknown MCP tool: {name}")
