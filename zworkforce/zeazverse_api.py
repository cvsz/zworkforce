"""HTTP transport and endpoint handlers for ZEAZVERSE AI Virtual Idol Studio."""

from __future__ import annotations

import json
import hashlib
import tempfile
import uuid
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


_EPISODE_JSON_FIELDS = (
    "story_concept_json", "characters_json", "script_json", "storyboard_json",
    "asset_manifest_json", "render_manifest_json", "audio_plan_json",
    "editing_plan_json", "qa_report_json", "publishing_metadata_json",
)
_CHARACTER_JSON_FIELDS = (
    "appearance_json", "personality_json", "story_themes_json", "dialogue_style_json",
    "voice_profile_json", "costume_config_json", "accessories_json",
    "consistency_rules_json", "reference_turnaround_json",
)
_SCENE_JSON_FIELDS = (
    "characters_json", "character_ref_ids_json", "dialogue_json", "audio_json",
    "model_settings_json", "qa_checks_json",
)
_APPROVAL_LOCKED_STATES = {"READY_FOR_REVIEW", "APPROVED", "UPLOADING", "PRIVATE_UPLOADED", "PUBLISHED"}


def _decode_json_fields(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    for key in fields:
        value = row.get(key)
        if isinstance(value, str):
            try:
                row[key[:-5]] = json.loads(value)
            except (ValueError, TypeError):
                row[key[:-5]] = [] if key.endswith(("_json",)) and key in {"characters_json", "story_themes_json", "accessories_json", "qa_checks_json", "character_ref_ids_json"} else {}
    return row


def _query_first(query: dict, key: str, default: str = "") -> str:
    value = query.get(key, default)
    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else default
    return str(value)


def _episode_characters(app, tenant_id: str, episode: dict[str, Any]) -> list[dict[str, Any]]:
    all_characters = app.db.zeazverse_list_characters(tenant_id)
    raw = episode.get("characters_json", episode.get("characters", []))
    try:
        selected = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        selected = []
    if not selected:
        return all_characters
    wanted = {str(item) for item in selected}
    found = [character for character in all_characters if character["id"] in wanted]
    if len(found) != len(wanted):
        raise ZeazverseValidationError("episode references an unknown character")
    return found


def _require_episode_editable(episode: dict[str, Any]) -> None:
    if episode.get("status") in _APPROVAL_LOCKED_STATES:
        raise ZeazverseValidationError("episode is locked pending publication")


def _episode_content_etag(episode: dict[str, Any], scenes: list[dict[str, Any]] | None = None) -> str:
    fields = (
        "title", "content_class", "target_duration_seconds", "story_concept_json",
        "characters_json", "script_json", "storyboard_json", "asset_manifest_json",
        "render_manifest_json", "audio_plan_json", "editing_plan_json", "publishing_metadata_json",
    )
    payload: dict[str, Any] = {}
    for key in fields:
        value = episode.get(key)
        if key.endswith("_json") and isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                pass
        payload[key] = value
    payload["scenes"] = scenes or []
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
        chars = [_decode_json_fields(c, _CHARACTER_JSON_FIELDS) for c in chars]
        return True, {"characters": chars}

    if path == "/api/v1/zeazverse/series":
        series = app.db.zeazverse_list_series(tenant_id)
        return True, {"series": [_decode_json_fields(item, ("metadata_json",)) for item in series]}

    if path == "/api/v1/zeazverse/episodes":
        episodes = app.db.zeazverse_list_episodes(
            tenant_id, _query_first(query, "series_id"), int(_query_first(query, "limit", "100"))
        )
        return True, {"episodes": [_decode_json_fields(ep, _EPISODE_JSON_FIELDS) for ep in episodes]}

    if path == "/api/v1/zeazverse/approvals":
        return True, {"approvals": app.db.zeazverse_list_approvals(
            tenant_id, _query_first(query, "state", "pending"), int(_query_first(query, "limit", "100"))
        )}

    if path == "/api/v1/zeazverse/publications":
        return True, {"publications": app.db.zeazverse_list_publications(
            tenant_id, _query_first(query, "episode_id"), int(_query_first(query, "limit", "100"))
        )}

    if path.startswith("/api/v1/zeazverse/characters/"):
        char_id = path.split("/")[-1]
        char = app.db.zeazverse_get_character(tenant_id, char_id)
        if not char:
            return True, {"error": "character_not_found"}
        char = _decode_json_fields(char, _CHARACTER_JSON_FIELDS)
        return True, {"character": char}

    # 4. Episodes & Storyboards
    if path.startswith("/api/v1/zeazverse/episodes/"):
        parts = path.split("/")
        ep_id = parts[5]
        if len(parts) == 6:
            ep = app.db.zeazverse_get_episode(tenant_id, ep_id)
            if not ep:
                return True, {"error": "episode_not_found"}
            return True, {"episode": _decode_json_fields(ep, _EPISODE_JSON_FIELDS)}
        if len(parts) == 7 and parts[6] == "scenes":
            scenes = app.db.zeazverse_list_scenes(tenant_id, ep_id)
            return True, {"episode_id": ep_id, "scenes": [_decode_json_fields(s, _SCENE_JSON_FIELDS) for s in scenes]}

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
        app.db.audit(tenant_id, principal.name, "zeazverse.channel.setup_step", "zeazverse_channel", "zeazverse_main", {"step_id": step_id, "status": status})
        return True, {"channel": ch, "updated_step": step_id, "status": status}, 200

    # 2. Create Series
    if path == "/api/v1/zeazverse/series":
        data = validate_series_data(body)
        series = app.db.zeazverse_create_series(
            tenant_id, data["id"], data["title"], data["synopsis"], data["content_class"], created_by=principal.name
        )
        app.db.audit(tenant_id, principal.name, "zeazverse.series.create", "zeazverse_series", data["id"], {})
        return True, {"series": series}, 201

    # 3. Create Episode
    if path == "/api/v1/zeazverse/episodes":
        data = validate_episode_data(body)
        data["idempotency_key"] = idem_key
        ep = app.db.zeazverse_create_episode(tenant_id, data, created_by=principal.name)
        app.db.audit(tenant_id, principal.name, "zeazverse.episode.create", "zeazverse_episode", ep["id"], {})
        return True, {"episode": ep}, 201

    # 4. Generate Storyboard
    if path.startswith("/api/v1/zeazverse/episodes/") and path.endswith("/generate-storyboard"):
        ep_id = path.split("/")[5]
        ep = app.db.zeazverse_get_episode(tenant_id, ep_id)
        if not ep:
            return True, {"error": "episode_not_found"}, 404
        _require_episode_editable(ep)
        chars = _episode_characters(app, tenant_id, ep)
        scenes = generate_cinematic_storyboard(ep, chars)
        app.db.zeazverse_save_scenes(tenant_id, ep_id, scenes)
        app.db.zeazverse_update_episode_status(
            tenant_id, ep_id, "SCRIPT_APPROVED", extra_fields={"storyboard_json": scenes}
        )
        app.db.audit(tenant_id, principal.name, "zeazverse.storyboard.generate", "zeazverse_episode", ep_id,
                     {"scene_count": len(scenes)})
        return True, {"episode_id": ep_id, "scenes": scenes, "status": "SCRIPT_APPROVED"}, 200

    # 5. Generate SEO Metadata
    if path.startswith("/api/v1/zeazverse/episodes/") and path.endswith("/generate-seo"):
        ep_id = path.split("/")[5]
        ep = app.db.zeazverse_get_episode(tenant_id, ep_id)
        if not ep:
            return True, {"error": "episode_not_found"}, 404
        _require_episode_editable(ep)
        chars = _episode_characters(app, tenant_id, ep)
        seo = generate_youtube_seo_metadata(ep, chars)
        app.db.zeazverse_update_episode_status(
            tenant_id, ep_id, ep.get("status", "IDEA"), extra_fields={"publishing_metadata_json": seo}
        )
        app.db.audit(tenant_id, principal.name, "zeazverse.seo.generate", "zeazverse_episode", ep_id, {})
        return True, {"episode_id": ep_id, "seo_metadata": seo}, 200

    # 6. Render Episode
    if path.startswith("/api/v1/zeazverse/episodes/") and path.endswith("/render"):
        ep_id = path.split("/")[5]
        ep = app.db.zeazverse_get_episode(tenant_id, ep_id)
        if not ep:
            return True, {"error": "episode_not_found"}, 404
        _require_episode_editable(ep)
        scenes = app.db.zeazverse_list_scenes(tenant_id, ep_id)
        if not scenes:
            chars = _episode_characters(app, tenant_id, ep)
            scenes = generate_cinematic_storyboard(ep, chars)
            app.db.zeazverse_save_scenes(tenant_id, ep_id, scenes)

        with tempfile.TemporaryDirectory(prefix="zeazverse-render-", dir=str(app.settings.data_dir)) as render_dir:
            pipeline = VideoEditingPipeline(output_dir=render_dir)
            render_result = pipeline.render_episode(ep_id, scenes, {})
            video_artifact = app.artifacts.put_file(
                tenant_id,
                render_result["output_video_uri"],
                actor=principal.name,
                content_type="video/mp4",
                metadata={"episode_id": ep_id, "render_kind": render_result["render_kind"]},
            )
            subtitle_artifact = app.artifacts.put_file(
                tenant_id,
                render_result["subtitles_vtt_uri"],
                actor=principal.name,
                content_type="text/vtt",
                metadata={"episode_id": ep_id, "render_id": render_result["render_id"]},
            )
        render_result["video_artifact"] = video_artifact
        render_result["subtitle_artifact"] = subtitle_artifact
        render_result["output_video_uri"] = video_artifact["storage_uri"]
        render_result["subtitles_vtt_uri"] = subtitle_artifact["storage_uri"]
        qa_report = evaluate_qa_continuity(scenes, render_result)

        app.db.zeazverse_update_episode_status(
            tenant_id,
            ep_id,
            "QA_PENDING" if qa_report["technical_checks_passed"] else "FAILED",
            extra_fields={"render_manifest_json": render_result, "qa_report_json": qa_report},
        )
        app.db.audit(tenant_id, principal.name, "zeazverse.render.create", "zeazverse_episode", ep_id,
                     {"render_id": render_result["render_id"], "sha256": render_result["output_sha256"], "render_kind": render_result["render_kind"]})
        return True, {
            "episode_id": ep_id,
            "render_result": render_result,
            "qa_report": qa_report,
            "status": "QA_PENDING" if qa_report["technical_checks_passed"] else "FAILED",
        }, 200

    # 7. Record a human visual QA decision before publication approval.
    if path.startswith("/api/v1/zeazverse/episodes/") and path.endswith("/qa-review"):
        ep_id = path.split("/")[5]
        ep = app.db.zeazverse_get_episode(tenant_id, ep_id)
        if not ep:
            return True, {"error": "episode_not_found"}, 404
        if type(body.get("visual_review_passed")) is not bool:
            raise ZeazverseValidationError("visual_review_passed must be a boolean")
        try:
            qa_report = json.loads(ep.get("qa_report_json") or "{}")
        except (ValueError, TypeError):
            qa_report = {}
        if ep.get("status") != "QA_PENDING" or not qa_report.get("technical_checks_passed"):
            raise ZeazverseValidationError("episode must pass technical checks before visual review")
        qa_report["visual_review_status"] = "passed" if body["visual_review_passed"] else "failed"
        qa_report["visual_reviewer"] = principal.name
        qa_report["visual_review_notes"] = str(body.get("notes", "")).strip()[:2000]
        status = "QA_PASSED" if body["visual_review_passed"] else "FAILED"
        app.db.zeazverse_update_episode_status(
            tenant_id, ep_id, status, extra_fields={"qa_report_json": qa_report}
        )
        app.db.audit(tenant_id, principal.name, "zeazverse.qa.review", "zeazverse_episode", ep_id,
                     {"visual_review_passed": body["visual_review_passed"], "notes": qa_report["visual_review_notes"]})
        return True, {"episode_id": ep_id, "status": status, "qa_report": qa_report}, 200

    # 8. Request Publishing Approval
    if path.startswith("/api/v1/zeazverse/episodes/") and path.endswith("/request-approval"):
        ep_id = path.split("/")[5]
        ep = app.db.zeazverse_get_episode(tenant_id, ep_id)
        if not ep:
            return True, {"error": "episode_not_found"}, 404
        request_suffix = hashlib.sha256(f"{tenant_id}:{ep_id}:{idem_key}".encode("utf-8")).hexdigest()[:24] if idem_key else uuid.uuid4().hex[:24]
        req_id = f"appr_{ep_id}_{request_suffix}"
        if idem_key:
            with app.db.connection() as c:
                existing = c.execute(
                    "SELECT * FROM zeazverse_approval_requests WHERE tenant_id=? AND id=?",
                    (tenant_id, req_id),
                ).fetchone()
            if existing:
                return True, {"approval_request": dict(existing), "episode_id": ep_id}, 200
        if ep.get("status") != "QA_PASSED":
            raise ZeazverseValidationError("episode requires completed human visual QA before approval")
        target_visibility = str(body.get("target_visibility", "private")).strip().lower()
        if target_visibility not in {"private", "unlisted", "public"}:
            raise ZeazverseValidationError("target_visibility must be private, unlisted, or public")
        approval = app.db.zeazverse_create_approval_request(
            tenant_id, req_id, ep_id, target_visibility=target_visibility,
            expected_etag=_episode_content_etag(ep, app.db.zeazverse_list_scenes(tenant_id, ep_id)),
            created_by=principal.name,
        )
        if approval.get("state") == "pending":
            app.db.audit(tenant_id, principal.name, "zeazverse.approval.request", "zeazverse_approval", req_id,
                         {"episode_id": ep_id, "visibility": target_visibility, "expected_etag": approval.get("expected_etag", "")})
        return True, {"approval_request": approval, "episode_id": ep_id}, 201

    # 9. Human Review / Approval Decision
    if path == "/api/v1/zeazverse/approvals/decide":
        req_id = str(body.get("request_id", "")).strip()
        if type(body.get("approved")) is not bool:
            raise ZeazverseValidationError("approved must be a boolean")
        approved = body["approved"]
        comment = str(body.get("comment", "")).strip()
        if not req_id:
            raise ZeazverseValidationError("request_id is required")
        with app.db.connection() as c:
            current_approval = c.execute(
                "SELECT * FROM zeazverse_approval_requests WHERE tenant_id=? AND id=?",
                (tenant_id, req_id),
            ).fetchone()
        if not current_approval or current_approval["state"] != "pending":
            raise ZeazverseValidationError("approval is not pending or reviewer is not independent")
        approval_episode = app.db.zeazverse_get_episode(tenant_id, current_approval["episode_id"])
        if not approval_episode or approval_episode.get("status") != "READY_FOR_REVIEW":
            raise ZeazverseValidationError("episode is not in review")
        current_scenes = app.db.zeazverse_list_scenes(tenant_id, approval_episode["id"])
        if current_approval["expected_etag"] != _episode_content_etag(approval_episode, current_scenes):
            raise ZeazverseValidationError("episode content changed since approval was requested")
        current_etag = _episode_content_etag(approval_episode, current_scenes)
        approval = app.db.zeazverse_decide_approval(
            tenant_id, req_id, principal.name, approved, comment,
            reviewer_name=principal.name, expected_etag=current_etag,
        )
        if not approval:
            raise ZeazverseValidationError("approval is not pending or reviewer is not independent")
        ep_id = approval.get("episode_id", "")
        app.db.audit(tenant_id, principal.name, "zeazverse.approval.decide", "zeazverse_approval", req_id,
                     {"approved": approved, "episode_id": ep_id})
        return True, {"approval": approval}, 200

    # 10. YouTube Publish (blocked until a real provider is configured)
    if path.startswith("/api/v1/zeazverse/episodes/") and path.endswith("/publish"):
        ep_id = path.split("/")[5]
        ep = app.db.zeazverse_get_episode(tenant_id, ep_id)
        if not ep:
            return True, {"error": "episode_not_found"}, 404
        approval_id = str(body.get("approval_id", "")).strip()
        if not approval_id:
            app.db.audit(tenant_id, principal.name, "zeazverse.publish.attempt", "zeazverse_episode", ep_id,
                         {"result": "missing_approval"})
            raise ZeazverseValidationError("Publishing requires an approved approval_id")

        # Verify the approval without consuming it; provider absence must not mutate state.
        with app.db.connection() as c:
            appr = c.execute(
                "SELECT * FROM zeazverse_approval_requests WHERE tenant_id=? AND id=?", (tenant_id, approval_id)
            ).fetchone()
            if (not appr or appr["episode_id"] != ep_id or appr["state"] != "approved"
                    or appr["consumed_at"] is not None or ep.get("status") != "APPROVED"):
                app.db.audit(tenant_id, principal.name, "zeazverse.publish.attempt", "zeazverse_episode", ep_id,
                             {"approval_id": approval_id, "result": "approval_or_state_invalid"})
                raise ZeazverseValidationError("Invalid, unapproved, or already consumed approval request")
            if appr["expected_etag"] != _episode_content_etag(ep, app.db.zeazverse_list_scenes(tenant_id, ep_id)):
                app.db.audit(tenant_id, principal.name, "zeazverse.publish.attempt", "zeazverse_episode", ep_id,
                             {"approval_id": approval_id, "result": "stale_content"})
                raise ZeazverseValidationError("episode content changed since approval; re-request approval")

        app.db.audit(tenant_id, principal.name, "zeazverse.publish.attempt", "zeazverse_episode", ep_id,
                     {"approval_id": approval_id, "result": "provider_unavailable"})
        return True, {
            "error": "youtube_provider_unavailable",
            "message": "No authenticated YouTube provider is configured; approval remains unconsumed.",
            "episode_id": ep_id,
            "approval_id": approval_id,
            "status": "not_published",
        }, 503

    return False, None, 404
