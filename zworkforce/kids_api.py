"""HTTP transport for AI Kids Content Factory (delegated from App handler)."""

from __future__ import annotations

import re
from typing import Any

from .kids_factory import (
    KidsValidationError,
    build_storyboard,
    estimate_cost,
    kids_safety_check,
    mock_youtube_upload,
    prepare_youtube_metadata,
    render_deterministic_video,
    storyboard_to_timeline,
    validate_brand,
    validate_character,
    validate_episode,
    validate_media_upload,
    validate_scene,
    validate_script,
    validate_timeline,
)

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")


def _slug_or_raise(value: str, field: str) -> str:
    text = str(value or "").strip().lower()
    if not SLUG.fullmatch(text):
        raise KidsValidationError(f"{field} must match [a-z0-9-], 2..63 chars")
    return text


def kids_get(app, tenant_id: str, path: str, query: dict) -> tuple[bool, Any]:
    """Return (handled, payload). Raises ValueError on bad input."""
    from .api import _intq, _strq

    db = app.db
    if path == "/api/v1/kids/overview":
        return True, {"tenant_id": tenant_id, **db.kids_overview(tenant_id), **{"usage": db.kids_usage_summary(tenant_id)}}
    if path == "/api/v1/kids/brands":
        return True, {"items": db.kids_list_brands(tenant_id, limit=_intq(query, "limit", 100), offset=_intq(query, "offset", 0))}
    m = re.fullmatch(r"/api/v1/kids/brands/([a-z0-9][a-z0-9-]{0,62})", path)
    if m:
        brand = db.kids_get_brand(tenant_id, m.group(1))
        if not brand:
            return True, {"_status": 404, "_error": ("brand_not_found", "brand not found")}
        return True, brand
    if path == "/api/v1/kids/channels":
        return True, {"items": db.kids_list_channels(tenant_id, brand_id=_strq(query, "brand_id"))}
    if path == "/api/v1/kids/characters":
        return True, {"items": db.kids_list_characters(tenant_id, brand_id=_strq(query, "brand_id"))}
    m = re.fullmatch(r"/api/v1/kids/characters/([a-z0-9][a-z0-9-]{0,62})", path)
    if m:
        char = db.kids_get_character(tenant_id, m.group(1))
        if not char:
            return True, {"_status": 404, "_error": ("character_not_found", "character not found")}
        return True, char
    if path == "/api/v1/kids/episodes":
        return True, {"items": db.kids_list_episodes(tenant_id, brand_id=_strq(query, "brand_id"),
                                                      status=_strq(query, "status"),
                                                      limit=_intq(query, "limit", 100), offset=_intq(query, "offset", 0))}
    m = re.fullmatch(r"/api/v1/kids/episodes/([a-z0-9][a-z0-9-]{0,62})", path)
    if m:
        ep = db.kids_get_episode(tenant_id, m.group(1))
        if not ep:
            return True, {"_status": 404, "_error": ("episode_not_found", "episode not found")}
        return True, ep
    m = re.fullmatch(r"/api/v1/kids/episodes/([a-z0-9][a-z0-9-]{0,62})/script", path)
    if m:
        script = db.kids_latest_script(tenant_id, m.group(1))
        return True, script or {"episode_id": m.group(1), "version": 0, "body": {}}
    m = re.fullmatch(r"/api/v1/kids/episodes/([a-z0-9][a-z0-9-]{0,62})/scenes", path)
    if m:
        return True, {"items": db.kids_list_scenes(tenant_id, m.group(1))}
    m = re.fullmatch(r"/api/v1/kids/episodes/([a-z0-9][a-z0-9-]{0,62})/timeline", path)
    if m:
        timeline = db.kids_latest_timeline(tenant_id, m.group(1))
        return True, timeline or {"episode_id": m.group(1), "version": 0, "tracks": {}}
    if path == "/api/v1/kids/assets":
        return True, {"items": db.kids_list_assets(tenant_id, episode_id=_strq(query, "episode_id"))}
    if path == "/api/v1/kids/render-jobs":
        return True, {"items": db.kids_list_renders(tenant_id, episode_id=_strq(query, "episode_id"))}
    m = re.fullmatch(r"/api/v1/kids/render-jobs/([0-9a-f]{12})", path)
    if m:
        job = db.kids_get_render(tenant_id, m.group(1))
        if not job:
            return True, {"_status": 404, "_error": ("render_not_found", "render job not found")}
        return True, job
    if path == "/api/v1/kids/approvals":
        return True, {"items": db.kids_list_approvals(tenant_id, state=_strq(query, "state"))}
    if path == "/api/v1/kids/publishing":
        return True, {"items": db.kids_list_publishing(tenant_id, episode_id=_strq(query, "episode_id"))}
    m = re.fullmatch(r"/api/v1/kids/publishing/([0-9a-f]{12})", path)
    if m:
        job = db.kids_get_publishing(tenant_id, m.group(1))
        if not job:
            return True, {"_status": 404, "_error": ("publishing_not_found", "publishing job not found")}
        return True, job
    if path == "/api/v1/kids/analytics":
        return True, {"items": db.kids_list_analytics(tenant_id, channel_id=_strq(query, "channel_id"))}
    if path == "/api/v1/kids/providers":
        return True, {"items": [
            {"capability": "llm", "provider": "mock", "mode": "mock", "enabled": True},
            {"capability": "image", "provider": "mock", "mode": "mock", "enabled": True},
            {"capability": "video", "provider": "mock", "mode": "mock", "enabled": True},
            {"capability": "tts", "provider": "mock", "mode": "mock", "enabled": True},
            {"capability": "music", "provider": "mock", "mode": "mock", "enabled": True},
            {"capability": "render", "provider": "ffmpeg", "mode": "local", "enabled": True},
            {"capability": "publishing", "provider": "youtube_mock", "mode": "mock", "enabled": True},
        ]}
    if path == "/api/v1/kids/usage":
        return True, db.kids_usage_summary(tenant_id)
    return False, None


def kids_post(app, principal, tenant_id: str, path: str, body: dict, *, idempotency_key: str = "") -> tuple[bool, Any, int]:
    """Return (handled, payload, status)."""
    db = app.db
    actor = principal.name

    if path == "/api/v1/kids/brands":
        brand_id = _slug_or_raise(body.get("id", ""), "brand.id")
        validated = validate_brand(body)
        return True, db.kids_upsert_brand(tenant_id, brand_id, validated, actor), 201
    m = re.fullmatch(r"/api/v1/kids/brands/([a-z0-9][a-z0-9-]{0,62})/archive", path)
    if m:
        ok = db.kids_archive_brand(tenant_id, m.group(1), actor)
        if not ok:
            return True, {"error": {"code": "brand_not_found", "message": "brand not found"}}, 404
        return True, {"ok": True}, 200
    if path == "/api/v1/kids/channels":
        channel_id = _slug_or_raise(body.get("id", ""), "channel.id")
        brand_id = _slug_or_raise(body.get("brand_id", ""), "channel.brand_id")
        if not db.kids_get_brand(tenant_id, brand_id):
            raise KidsValidationError("channel.brand_id does not exist in this tenant")
        return True, db.kids_upsert_channel(tenant_id, channel_id, brand_id, body, actor), 201
    if path == "/api/v1/kids/characters":
        char_id = _slug_or_raise(body.get("id", ""), "character.id")
        brand_id = _slug_or_raise(body.get("brand_id", ""), "character.brand_id")
        if not db.kids_get_brand(tenant_id, brand_id):
            raise KidsValidationError("character.brand_id does not exist in this tenant")
        validated = validate_character(body)
        return True, db.kids_upsert_character(tenant_id, char_id, brand_id, validated, actor), 201
    m = re.fullmatch(r"/api/v1/kids/characters/([a-z0-9][a-z0-9-]{0,62})/(lock|unlock)", path)
    if m:
        ok = db.kids_lock_character(tenant_id, m.group(1), actor, locked=(m.group(2) == "lock"))
        if not ok:
            return True, {"error": {"code": "character_not_found", "message": "character not found"}}, 404
        return True, {"ok": True, "locked": m.group(2) == "lock"}, 200
    if path == "/api/v1/kids/episodes":
        ep_id = _slug_or_raise(body.get("id", ""), "episode.id")
        brand_id = _slug_or_raise(body.get("brand_id", ""), "episode.brand_id")
        if not db.kids_get_brand(tenant_id, brand_id):
            raise KidsValidationError("episode.brand_id does not exist in this tenant")
        validated = validate_episode(body)
        episode, created = db.kids_create_episode(tenant_id, ep_id, brand_id, validated, actor,
                                                  channel_id=str(body.get("channel_id", ""))[:64],
                                                  idempotency_key=idempotency_key or str(body.get("idempotency_key", "")))
        return True, episode, 201 if created else 200
    m = re.fullmatch(r"/api/v1/kids/episodes/([a-z0-9][a-z0-9-]{0,62})/script", path)
    if m:
        episode_id = m.group(1)
        if not db.kids_get_episode(tenant_id, episode_id):
            return True, {"error": {"code": "episode_not_found", "message": "episode not found"}}, 404
        validated = validate_script(body)
        script = db.kids_save_script(tenant_id, episode_id, validated, actor)
        db.kids_set_episode_status(tenant_id, episode_id, "scripted", actor)
        db.kids_record_usage(tenant_id, episode_id, "mock", "llm", 1.0, 0.2)
        return True, script, 201
    m = re.fullmatch(r"/api/v1/kids/episodes/([a-z0-9][a-z0-9-]{0,62})/storyboard", path)
    if m:
        episode_id = m.group(1)
        episode = db.kids_get_episode(tenant_id, episode_id)
        if not episode:
            return True, {"error": {"code": "episode_not_found", "message": "episode not found"}}, 404
        script = db.kids_latest_script(tenant_id, episode_id)
        script_body = (script.get("body") if script else {}) or {}
        try:
            num_scenes = int(body.get("num_scenes", 4))
        except (TypeError, ValueError):
            raise KidsValidationError("num_scenes must be an integer")
        plan = build_storyboard(script_body=script_body, num_scenes=num_scenes)
        saved = []
        for index, item in enumerate(plan):
            scene_id = f"s{index + 1:02d}"
            validated = validate_scene(item)
            saved.append(db.kids_upsert_scene(tenant_id, episode_id, scene_id, validated, actor))
        db.kids_set_episode_status(tenant_id, episode_id, "storyboarded", actor)
        db.kids_record_usage(tenant_id, episode_id, "mock", "llm", float(len(saved)), 0.1 * len(saved))
        return True, {"items": saved}, 201
    m = re.fullmatch(r"/api/v1/kids/episodes/([a-z0-9][a-z0-9-]{0,62})/scenes", path)
    if m:
        episode_id = m.group(1)
        if not db.kids_get_episode(tenant_id, episode_id):
            return True, {"error": {"code": "episode_not_found", "message": "episode not found"}}, 404
        scene_id = _slug_or_raise(body.get("id", ""), "scene.id")
        validated = validate_scene(body)
        return True, db.kids_upsert_scene(tenant_id, episode_id, scene_id, validated, actor), 201
    m = re.fullmatch(r"/api/v1/kids/episodes/([a-z0-9][a-z0-9-]{0,62})/timeline", path)
    if m:
        episode_id = m.group(1)
        episode = db.kids_get_episode(tenant_id, episode_id)
        if not episode:
            return True, {"error": {"code": "episode_not_found", "message": "episode not found"}}, 404
        scenes = db.kids_list_scenes(tenant_id, episode_id)
        if body.get("tracks"):
            validated = validate_timeline(body)
            tracks = validated["tracks"]
        else:
            tracks = storyboard_to_timeline(scenes, brand_name="")
        saved = db.kids_save_timeline(tenant_id, episode_id, tracks, actor)
        cost = estimate_cost(num_scenes=len(scenes), duration_total=sum(float(s.get("duration_seconds", 5)) for s in scenes))
        db.kids_record_usage(tenant_id, episode_id, "ffmpeg", "render_plan", 1.0, cost * 0.1)
        return True, {**saved, "estimated_cost_credits": cost}, 201
    if path == "/api/v1/kids/assets":
        validate_media_upload(filename=str(body.get("name", "")), content_type=str(body.get("content_type", "")),
                              size_bytes=int(body.get("size_bytes", 0) or 0))
        episode_id = str(body.get("episode_id", ""))
        if episode_id and not db.kids_get_episode(tenant_id, episode_id):
            raise KidsValidationError("asset.episode_id does not exist in this tenant")
        return True, db.kids_register_asset(tenant_id, body, actor), 201
    if path == "/api/v1/kids/render-jobs":
        episode_id = _slug_or_raise(body.get("episode_id", ""), "render.episode_id")
        episode = db.kids_get_episode(tenant_id, episode_id)
        if not episode:
            return True, {"error": {"code": "episode_not_found", "message": "episode not found"}}, 404
        timeline = db.kids_latest_timeline(tenant_id, episode_id)
        if not timeline:
            raise KidsValidationError("episode has no timeline; build timeline before rendering")
        preset = str(body.get("preset", "landscape_1080p"))
        job, created = db.kids_submit_render(tenant_id, episode_id, int(timeline.get("version", 1)), preset, actor,
                                             idempotency_key=idempotency_key or str(body.get("idempotency_key", "")))
        if not created:
            return True, job, 200
        # ดำเนินการ render แบบ synchronous สำหรับ vertical slice (bounded, deterministic)
        try:
            scenes = db.kids_list_scenes(tenant_id, episode_id)
            render_dir = app.settings.data_dir / "kids-renders" / tenant_id
            render_dir.mkdir(parents=True, exist_ok=True)
            out_path = render_dir / f"{job['id']}.mp4"
            result = render_deterministic_video(scenes=scenes, preset=preset, title=episode.get("title", ""), out_path=out_path)
            # ลงทะเบียน artifact ผ่าน store เดิม (content-addressed, SHA-256)
            artifact = None
            try:
                data = out_path.read_bytes()
                artifact = app.artifacts.put_bytes(tenant_id, f"{episode_id}-{job['id']}.mp4", data, actor=actor,
                                                   content_type="video/mp4",
                                                   metadata={"kids_episode": episode_id, "kids_render": job["id"], "synthetic": True})
            except Exception:
                artifact = None
            patch = {"status": "succeeded", "output_uri": result["output_uri"], "output_sha256": result["sha256"],
                     "thumbnail_uri": result.get("thumbnail_uri", "")}
            if artifact and artifact.get("storage_uri"):
                patch["output_uri"] = artifact["storage_uri"]
                patch["output_sha256"] = artifact.get("sha256", patch["output_sha256"])
            job = db.kids_update_render(tenant_id, job["id"], patch, actor) or job
            db.kids_set_episode_status(tenant_id, episode_id, "rendered", actor)
            db.kids_record_usage(tenant_id, episode_id, "ffmpeg", "video_render", 1.0, 0.5)
        except Exception as exc:
            job = db.kids_update_render(tenant_id, job["id"], {"status": "failed", "error": str(exc)[:1000]}, actor) or job
        return True, job, 201
    m = re.fullmatch(r"/api/v1/kids/render-jobs/([0-9a-f]{12})/retry", path)
    if m:
        job = db.kids_get_render(tenant_id, m.group(1))
        if not job:
            return True, {"error": {"code": "render_not_found", "message": "render job not found"}}, 404
        if job.get("status") != "failed":
            return True, job, 200
        job = db.kids_update_render(tenant_id, job["id"], {"status": "queued", "error": ""}, actor) or job
        return True, job, 200
    if path == "/api/v1/kids/approvals":
        episode_id = _slug_or_raise(body.get("episode_id", ""), "approval.episode_id")
        if not db.kids_get_episode(tenant_id, episode_id):
            return True, {"error": {"code": "episode_not_found", "message": "episode not found"}}, 404
        subject_type = str(body.get("subject_type", "episode"))[:24] or "episode"
        # รัน safety check อัตโนมัติก่อนขออนุมัติ (QA gate, ไม่แทน human approval)
        episode = db.kids_get_episode(tenant_id, episode_id)
        script = db.kids_latest_script(tenant_id, episode_id)
        scenes = db.kids_list_scenes(tenant_id, episode_id)
        corpus = (episode.get("summary", "") + " " + str((script or {}).get("body", "")) + " " +
                  " ".join(s.get("visual_prompt", "") for s in scenes))
        report = kids_safety_check(age_band=episode.get("age_band", "preschool"), text=corpus)
        db.kids_save_moderation(tenant_id, episode_id, report, f"quality-agent:{actor}")
        if not report["passed"]:
            db.kids_set_episode_status(tenant_id, episode_id, "in_review", actor)
            raise KidsValidationError(f"safety review blocked: {report['findings'][0]['rule']} ({report['findings'][0]['match']})")
        db.kids_set_episode_status(tenant_id, episode_id, "in_review", actor)
        approval = db.kids_request_approval(tenant_id, episode_id, subject_type,
                                            str(body.get("subject_id", episode_id))[:64],
                                            int(body.get("subject_version", 1) or 1), actor)
        return True, {**approval, "safety": {"passed": True}}, 201
    m = re.fullmatch(r"/api/v1/kids/approvals/([0-9a-f]{12})/(approve|reject)", path)
    if m:
        decided = db.kids_decide_approval(tenant_id, m.group(1), "approved" if m.group(2) == "approve" else "rejected",
                                          actor, str(body.get("comment", "")))
        if not decided:
            return True, {"error": {"code": "approval_not_found", "message": "approval not found"}}, 404
        return True, decided, 200
    if path == "/api/v1/kids/publishing/prepare":
        episode_id = _slug_or_raise(body.get("episode_id", ""), "publishing.episode_id")
        episode = db.kids_get_episode(tenant_id, episode_id)
        if not episode:
            return True, {"error": {"code": "episode_not_found", "message": "episode not found"}}, 404
        metadata = prepare_youtube_metadata(title=body.get("title") or episode.get("title", ""),
                                            description=body.get("description") or episode.get("summary", ""),
                                            audience=str(body.get("audience", "madeForKids")))
        job, created = db.kids_prepare_publishing(tenant_id, episode_id, {
            "render_job_id": str(body.get("render_job_id", "")),
            "channel_id": str(body.get("channel_id", "")),
            "platform": "youtube_mock",
            "title": metadata["title"], "description": metadata["description"],
            "audience": metadata["audience"], "visibility": str(body.get("visibility", "private")),
            "approval_id": str(body.get("approval_id", "")),
        }, actor, idempotency_key=idempotency_key or str(body.get("idempotency_key", "")))
        return True, job, 201 if created else 200
    m = re.fullmatch(r"/api/v1/kids/publishing/([0-9a-f]{12})/publish", path)
    if m:
        job = db.kids_get_publishing(tenant_id, m.group(1))
        if not job:
            return True, {"error": {"code": "publishing_not_found", "message": "publishing job not found"}}, 404
        metadata = prepare_youtube_metadata(title=job.get("title", "Kids video"), description=job.get("description", ""),
                                            audience=job.get("audience", "madeForKids"))
        # mock upload ที่ deterministic + idempotent (ห้าม upload ซ้ำเมื่อ network ล้มเหลว)
        external = mock_youtube_upload(metadata=metadata, idempotency_key=job.get("idempotency_key") or job["id"],
                                       sha256=job.get("render_job_id") or job["id"])
        try:
            done = db.kids_publish_approved(tenant_id, job["id"], external, actor)
        except ValueError as exc:
            raise KidsValidationError(str(exc))
        db.kids_record_usage(tenant_id, job["episode_id"], "youtube_mock", "upload", 1.0, 0.1)
        return True, {**(done or job), "mock_upload": external}, 200
    if path == "/api/v1/kids/analytics/snapshot":
        snap = db.kids_save_analytics(tenant_id, {"channel_id": str(body.get("channel_id", "")),
                                                  "episode_id": str(body.get("episode_id", "")),
                                                  "period": str(body.get("period", "7d")),
                                                  "metrics": body.get("metrics") or {"note": "synthetic fixture, not real YouTube data"},
                                                  "synthetic": True})
        return True, snap, 201
    return False, None, 0
