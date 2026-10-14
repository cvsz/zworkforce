"""HTTP transport and endpoint handlers for ZEAZVERSE AI Virtual Idol Studio."""

from __future__ import annotations

import json
from typing import Any

from .zeazverse_bibles import (
    CANONICAL_CHARACTERS,
    CHANNEL_SETUP_STEPS,
    CONTENT_CLASSES,
    PUBLISHING_STATES,
    ZEAZVERSE_BRAND,
)
from .zeazverse_domain import (
    ZeazverseValidationError,
    evaluate_qa_continuity,
    generate_cinematic_storyboard,
    generate_youtube_seo_metadata,
    validate_character_data,
    validate_episode_data,
    validate_scene_data,
    validate_series_data,
    validate_slug,
)
from .zeazverse_adapters import (
    MockAudioProviderAdapter,
    MockImageProviderAdapter,
    MockVideoProviderAdapter,
    VideoEditingPipeline,
)


def zeazverse_get(app, tenant_id: str, path: str, query: dict) -> tuple[bool, Any]:
    """Handles GET requests under /api/v1/zeazverse/..."""
    # 1. Overview & Brand
    if path == "/api/v1/zeazverse/brand":
        return True, {"brand": ZEAZVERSE_BRAND, "content_classes": CONTENT_CLASSES, "states": PUBLISHING_STATES}

    # 2. Channel Setup & Status
    if path == "/api/v1/zeazverse/channel":
        channel = app.db.zeazverse_get_or_create_channel(tenant_id)
        checklist = json.loads(channel.get("setup_checklist_json", "{}"))
        return True, {
            "channel": channel,
            "checklist": checklist,
            "all_steps": CHANNEL_SETUP_STEPS,
            "brand": ZEAZVERSE_BRAND,
        }

    # 3. Characters & Bibles
    if path == "/api/v1/zeazverse/characters":
        chars = app.db.zeazverse_list_characters(tenant_id)
        # Parse JSON fields for caller convenience
        for c in chars:
            for k in ["appearance_json", "personality_json", "story_themes_json", "costume_config_json"]:
                if k in c and isinstance(c[k], str):
                    try:
                        c[k[:-5]] = json.loads(c[k])
                    except Exception:
                        c[k[:-5]] = {}
        return True, {"characters": chars}

    if path.startswith("/api/v1/zeazverse/characters/"):
        char_id = path.split("/")[-1]
        char = app.db.zeazverse_get_character(tenant_id, char_id)
        if not char:
            return True, {"error": "character_not_found"}
        for k in ["appearance_json", "personality_json", "story_themes_json", "costume_config_json", "consistency_rules_json"]:
            if k in char and isinstance(char[k], str):
                try:
                    char[k[:-5]] = json.loads(char[k])
                except Exception:
                    char[k[:-5]] = {}
        return True, {"character": char}

    # 4. Episodes & Storyboards
    if path.startswith("/api/v1/zeazverse/episodes/"):
        parts = path.split("/")
        ep_id = parts[5]
        if len(parts) == 6:
            ep = app.db.zeazverse_get_episode(tenant_id, ep_id)
            if not ep:
                return True, {"error": "episode_not_found"}
            return True, {"episode": ep}
        if len(parts) == 7 and parts[6] == "scenes":
            scenes = app.db.zeazverse_list_scenes(tenant_id, ep_id)
            return True, {"episode_id": ep_id, "scenes": scenes}

    return False, None


def zeazverse_post(
    app, principal, tenant_id: str, path: str, body: dict, query: dict, idem_key: str
) -> tuple[bool, Any, int]:
    """Handles POST requests under /api/v1/zeazverse/..."""
    # 1. Update Channel Setup Step
    if path == "/api/v1/zeazverse/channel/setup-step":
        step_id = str(body.get("step_id", "")).strip()
        status = str(body.get("status", "completed")).strip()
        notes = str(body.get("notes", "")).strip()
        if not step_id:
            raise ZeazverseValidationError("step_id is required")
        ch = app.db.zeazverse_update_channel_setup_step(tenant_id, "zeazverse_main", step_id, status, notes)
        return True, {"channel": ch, "updated_step": step_id, "status": status}, 200

    # 2. Create Series
    if path == "/api/v1/zeazverse/series":
        data = validate_series_data(body)
        series = app.db.zeazverse_create_series(
            tenant_id, data["id"], data["title"], data["synopsis"], data["content_class"], created_by=principal.key_id
        )
        return True, {"series": series}, 201

    # 3. Create Episode
    if path == "/api/v1/zeazverse/episodes":
        data = validate_episode_data(body)
        data["idempotency_key"] = idem_key
        ep = app.db.zeazverse_create_episode(tenant_id, data, created_by=principal.key_id)
        return True, {"episode": ep}, 201

    # 4. Generate Storyboard
    if path.startswith("/api/v1/zeazverse/episodes/") and path.endswith("/generate-storyboard"):
        ep_id = path.split("/")[5]
        ep = app.db.zeazverse_get_episode(tenant_id, ep_id)
        if not ep:
            return True, {"error": "episode_not_found"}, 404
        chars = app.db.zeazverse_list_characters(tenant_id)
        scenes = generate_cinematic_storyboard(ep, chars)
        app.db.zeazverse_save_scenes(tenant_id, ep_id, scenes)
        app.db.zeazverse_update_episode_status(
            tenant_id, ep_id, "SCRIPT_APPROVED", extra_fields={"storyboard_json": scenes}
        )
        return True, {"episode_id": ep_id, "scenes": scenes, "status": "SCRIPT_APPROVED"}, 200

    # 5. Generate SEO Metadata
    if path.startswith("/api/v1/zeazverse/episodes/") and path.endswith("/generate-seo"):
        ep_id = path.split("/")[5]
        ep = app.db.zeazverse_get_episode(tenant_id, ep_id)
        if not ep:
            return True, {"error": "episode_not_found"}, 404
        chars = app.db.zeazverse_list_characters(tenant_id)
        seo = generate_youtube_seo_metadata(ep, chars)
        app.db.zeazverse_update_episode_status(
            tenant_id, ep_id, ep.get("status", "IDEA"), extra_fields={"publishing_metadata_json": seo}
        )
        return True, {"episode_id": ep_id, "seo_metadata": seo}, 200

    # 6. Render Episode
    if path.startswith("/api/v1/zeazverse/episodes/") and path.endswith("/render"):
        ep_id = path.split("/")[5]
        ep = app.db.zeazverse_get_episode(tenant_id, ep_id)
        if not ep:
            return True, {"error": "episode_not_found"}, 404
        scenes = app.db.zeazverse_list_scenes(tenant_id, ep_id)
        if not scenes:
            chars = app.db.zeazverse_list_characters(tenant_id)
            scenes = generate_cinematic_storyboard(ep, chars)
            app.db.zeazverse_save_scenes(tenant_id, ep_id, scenes)

        pipeline = VideoEditingPipeline()
        render_result = pipeline.render_episode(ep_id, scenes, {})
        qa_report = evaluate_qa_continuity(scenes, render_result)

        app.db.zeazverse_update_episode_status(
            tenant_id,
            ep_id,
            "QA_PASSED" if qa_report["passed"] else "FAILED",
            extra_fields={"render_manifest_json": render_result, "qa_report_json": qa_report},
        )
        return True, {
            "episode_id": ep_id,
            "render_result": render_result,
            "qa_report": qa_report,
            "status": "QA_PASSED" if qa_report["passed"] else "FAILED",
        }, 200

    # 7. Request Publishing Approval
    if path.startswith("/api/v1/zeazverse/episodes/") and path.endswith("/request-approval"):
        ep_id = path.split("/")[5]
        ep = app.db.zeazverse_get_episode(tenant_id, ep_id)
        if not ep:
            return True, {"error": "episode_not_found"}, 404
        target_visibility = str(body.get("target_visibility", "private")).strip().lower()
        if target_visibility not in {"private", "unlisted", "public"}:
            raise ZeazverseValidationError("target_visibility must be private, unlisted, or public")
        req_id = f"appr_{ep_id}_{idem_key[:8] if idem_key else 'req'}"
        approval = app.db.zeazverse_create_approval_request(
            tenant_id, req_id, ep_id, target_visibility=target_visibility, created_by=principal.key_id
        )
        app.db.zeazverse_update_episode_status(tenant_id, ep_id, "READY_FOR_REVIEW")
        return True, {"approval_request": approval, "episode_id": ep_id}, 201

    # 8. Human Review / Approval Decision
    if path == "/api/v1/zeazverse/approvals/decide":
        req_id = str(body.get("request_id", "")).strip()
        approved = bool(body.get("approved", False))
        comment = str(body.get("comment", "")).strip()
        if not req_id:
            raise ZeazverseValidationError("request_id is required")
        approval = app.db.zeazverse_decide_approval(tenant_id, req_id, principal.key_id, approved, comment)
        ep_id = approval.get("episode_id", "")
        if ep_id:
            app.db.zeazverse_update_episode_status(
                tenant_id, ep_id, "APPROVED" if approved else "CANCELLED"
            )
        return True, {"approval": approval}, 200

    # 9. Private YouTube Publish
    if path.startswith("/api/v1/zeazverse/episodes/") and path.endswith("/publish"):
        ep_id = path.split("/")[5]
        ep = app.db.zeazverse_get_episode(tenant_id, ep_id)
        if not ep:
            return True, {"error": "episode_not_found"}, 404
        approval_id = str(body.get("approval_id", "")).strip()
        if not approval_id:
            raise ZeazverseValidationError("Publishing requires an approved approval_id")

        # Verify approval is approved and not already consumed
        with app.db.connection() as c:
            appr = c.execute(
                "SELECT * FROM zeazverse_approval_requests WHERE tenant_id=? AND id=?", (tenant_id, approval_id)
            ).fetchone()
            if not appr or appr["state"] != "approved" or appr["consumed_at"] is not None:
                raise ZeazverseValidationError("Invalid, unapproved, or already consumed approval request")

        # Mark approval as consumed (single-use idempotent contract)
        app.db.zeazverse_consume_approval(tenant_id, approval_id)

        pub_id = f"pub_{ep_id}_{idem_key[:8] if idem_key else 'yt'}"
        simulated_yt_id = f"yt_vid_{ep_id}"
        publication = app.db.zeazverse_record_publication(
            tenant_id,
            pub_id,
            ep_id,
            "zeazverse_main",
            simulated_yt_id,
            visibility="private",
            approval_id=approval_id,
            idempotency_key=idem_key,
            created_by=principal.key_id,
        )
        app.db.zeazverse_update_episode_status(tenant_id, ep_id, "PRIVATE_UPLOADED")
        return True, {
            "publication": publication,
            "episode_id": ep_id,
            "youtube_video_id": simulated_yt_id,
            "visibility": "private",
            "status": "PRIVATE_UPLOADED",
        }, 200

    return False, None, 404
