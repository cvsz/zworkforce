"""Persistence mixin for ZEAZVERSE Idol Studio in zworkforce Database."""

from __future__ import annotations

import json
from typing import Any

from .db_base import json_dumps, json_loads, utcnow
from .zeazverse_bibles import (
    CANONICAL_CHARACTERS,
    CHANNEL_SETUP_STEPS,
    ZEAZVERSE_BRAND,
)

_PUBLISH_LOCKED_EPISODE_STATES = {"READY_FOR_REVIEW", "APPROVED", "UPLOADING", "PRIVATE_UPLOADED", "PUBLISHED"}


class ZeazverseMixin:
    """Methods for persisting channels, characters, series, episodes, jobs, and publications."""

    # ------------------ Channels ------------------
    def zeazverse_get_or_create_channel(
        self, tenant_id: str, channel_id: str = "zeazverse_main", created_by: str = "system"
    ) -> dict[str, Any]:
        with self.connection() as c:
            row = c.execute(
                "SELECT * FROM zeazverse_channels WHERE tenant_id=? AND id=?", (tenant_id, channel_id)
            ).fetchone()
            if row:
                return dict(row)
            now = utcnow()
            checklist = {s["id"]: {"status": "pending", "updated_at": now} for s in CHANNEL_SETUP_STEPS}
            c.execute(
                """INSERT INTO zeazverse_channels (
                    tenant_id, id, brand_name, tagline, preferred_handle, actual_handle,
                    youtube_channel_id, description, primary_language, default_visibility,
                    setup_status, setup_checklist_json, branding_assets_json,
                    feature_eligibility_json, publishing_settings_json, created_by,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, '', '', ?, ?, 'private', 'pending', ?, ?, '{}', '{}', ?, ?, ?)""",
                (
                    tenant_id,
                    channel_id,
                    ZEAZVERSE_BRAND["name"],
                    ZEAZVERSE_BRAND["tagline"],
                    ZEAZVERSE_BRAND["preferred_handle"],
                    ZEAZVERSE_BRAND["description"],
                    ZEAZVERSE_BRAND["primary_language"],
                    json_dumps(checklist),
                    json_dumps(ZEAZVERSE_BRAND["assets"]),
                    created_by,
                    now,
                    now,
                ),
            )
            return dict(
                c.execute(
                    "SELECT * FROM zeazverse_channels WHERE tenant_id=? AND id=?", (tenant_id, channel_id)
                ).fetchone()
            )

    def zeazverse_update_channel_setup_step(
        self, tenant_id: str, channel_id: str, step_id: str, status: str, notes: str = ""
    ) -> dict[str, Any]:
        allowed_steps = {step["id"] for step in CHANNEL_SETUP_STEPS}
        if step_id not in allowed_steps:
            raise ValueError("unknown ZEAZVERSE channel setup step")
        if status not in {"completed", "verified", "pending", "blocked", "requires_user_action"}:
            raise ValueError("invalid ZEAZVERSE channel setup status")
        if len(notes) > 2000:
            raise ValueError("channel setup notes exceed 2000 characters")
        ch = self.zeazverse_get_or_create_channel(tenant_id, channel_id)
        checklist = json_loads(ch.get("setup_checklist_json"), {})
        checklist[step_id] = {"status": status, "notes": notes, "updated_at": utcnow()}
        now = utcnow()
        with self.connection() as c:
            c.execute(
                "UPDATE zeazverse_channels SET setup_checklist_json=?, updated_at=? WHERE tenant_id=? AND id=?",
                (json_dumps(checklist), now, tenant_id, channel_id),
            )
            return dict(
                c.execute(
                    "SELECT * FROM zeazverse_channels WHERE tenant_id=? AND id=?", (tenant_id, channel_id)
                ).fetchone()
            )

    # ------------------ Characters ------------------
    def zeazverse_seed_canonical_characters(self, tenant_id: str, created_by: str = "system") -> list[dict[str, Any]]:
        seeded = []
        now = utcnow()
        with self.connection() as c:
            for cid, data in CANONICAL_CHARACTERS.items():
                existing = c.execute(
                    "SELECT * FROM zeazverse_characters WHERE tenant_id=? AND id=?", (tenant_id, cid)
                ).fetchone()
                if not existing:
                    c.execute(
                        """INSERT INTO zeazverse_characters (
                            tenant_id, id, name, archetype, age, nationality,
                            appearance_json, personality_json, story_themes_json,
                            dialogue_style_json, voice_profile_json, costume_config_json,
                            accessories_json, consistency_rules_json, reference_turnaround_json,
                            status, version, created_by, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'canonical', 1, ?, ?, ?)""",
                        (
                            tenant_id,
                            cid,
                            data["name"],
                            data["archetype"],
                            data["age"],
                            data["nationality"],
                            json_dumps(data["appearance"]),
                            json_dumps(data["personality"]),
                            json_dumps(data["story_themes"]),
                            json_dumps(data.get("dialogue_style", {"speech_style": data.get("personality", {}).get("speech_style", "")})),
                            json_dumps(data.get("voice_profile", {})),
                            json_dumps(data.get("costume", {})),
                            json_dumps(data.get("accessories", data.get("costume", {}).get("accessories", []))),
                            json_dumps(data.get("consistency_rules", {})),
                            json_dumps(data.get("reference_turnaround", {"views": data.get("consistency_rules", {}).get("turnaround_views", [])})),
                            created_by,
                            now,
                            now,
                        ),
                    )
                seeded.append(
                    dict(
                        c.execute(
                            "SELECT * FROM zeazverse_characters WHERE tenant_id=? AND id=?", (tenant_id, cid)
                        ).fetchone()
                    )
                )
        return seeded

    def zeazverse_list_characters(self, tenant_id: str) -> list[dict[str, Any]]:
        self.zeazverse_seed_canonical_characters(tenant_id)
        with self.connection() as c:
            rows = c.execute("SELECT * FROM zeazverse_characters WHERE tenant_id=? ORDER BY id", (tenant_id,)).fetchall()
            return [dict(r) for r in rows]

    def zeazverse_get_character(self, tenant_id: str, character_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute(
                "SELECT * FROM zeazverse_characters WHERE tenant_id=? AND id=?", (tenant_id, character_id)
            ).fetchone()
            return dict(row) if row else None

    # ------------------ Series & Episodes ------------------
    def zeazverse_create_series(
        self, tenant_id: str, series_id: str, title: str, synopsis: str = "", content_class: str = "Cyberpunk Stories", created_by: str = "system"
    ) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO zeazverse_series (
                    tenant_id, id, title, synopsis, content_class, target_format, status,
                    metadata_json, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, '9:16', 'active', '{}', ?, ?, ?)
                ON CONFLICT(tenant_id, id) DO UPDATE SET title=excluded.title, synopsis=excluded.synopsis, updated_at=excluded.updated_at""",
                (tenant_id, series_id, title, synopsis, content_class, created_by, now, now),
            )
            return dict(c.execute("SELECT * FROM zeazverse_series WHERE tenant_id=? AND id=?", (tenant_id, series_id)).fetchone())

    def zeazverse_list_series(self, tenant_id: str) -> list[dict[str, Any]]:
        with self.connection() as c:
            rows = c.execute(
                "SELECT * FROM zeazverse_series WHERE tenant_id=? ORDER BY created_at DESC, id",
                (tenant_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def zeazverse_create_episode(
        self, tenant_id: str, ep_data: dict[str, Any], created_by: str = "system"
    ) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as c:
            idempotency_key = str(ep_data.get("idempotency_key", ""))
            if idempotency_key:
                existing = c.execute(
                    "SELECT * FROM zeazverse_episodes WHERE tenant_id=? AND idempotency_key=?",
                    (tenant_id, idempotency_key),
                ).fetchone()
                if existing:
                    return dict(existing)
            c.execute(
                """INSERT INTO zeazverse_episodes (
                    tenant_id, id, series_id, channel_id, story_id, title, content_class,
                    canvas_format, fps, target_duration_seconds, status,
                    story_concept_json, characters_json, script_json, storyboard_json,
                    asset_manifest_json, render_manifest_json, audio_plan_json,
                    editing_plan_json, qa_report_json, publishing_metadata_json,
                    version, idempotency_key, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """ + (" ON CONFLICT DO NOTHING" if idempotency_key else ""),
                (
                    tenant_id,
                    ep_data["id"],
                    ep_data["series_id"],
                    ep_data.get("channel_id", "zeazverse_main"),
                    ep_data.get("story_id", f"story-{ep_data['id']}"),
                    ep_data["title"],
                    ep_data.get("content_class", "Cyberpunk Stories"),
                    ep_data.get("canvas_format", "1080x1920"),
                    ep_data.get("fps", 30),
                    ep_data.get("target_duration_seconds", 30.0),
                    ep_data.get("status", "IDEA"),
                    json_dumps(ep_data.get("story_concept", {})),
                    json_dumps(ep_data.get("characters", [])),
                    json_dumps(ep_data.get("script", {})),
                    json_dumps(ep_data.get("storyboard", {})),
                    json_dumps(ep_data.get("asset_manifest", {})),
                    json_dumps(ep_data.get("render_manifest", {})),
                    json_dumps(ep_data.get("audio_plan", {})),
                    json_dumps(ep_data.get("editing_plan", {})),
                    json_dumps(ep_data.get("qa_report", {})),
                    json_dumps(ep_data.get("publishing_metadata", {})),
                    ep_data.get("version", 1),
                    ep_data.get("idempotency_key", ""),
                    created_by,
                    now,
                    now,
                ),
            )
            row = c.execute(
                "SELECT * FROM zeazverse_episodes WHERE tenant_id=? AND idempotency_key=?" if idempotency_key else
                "SELECT * FROM zeazverse_episodes WHERE tenant_id=? AND id=?",
                (tenant_id, idempotency_key) if idempotency_key else (tenant_id, ep_data["id"]),
            ).fetchone()
            if not row:
                raise ValueError("episode id conflicts with an existing record")
            return dict(row)

    def zeazverse_get_episode(self, tenant_id: str, ep_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM zeazverse_episodes WHERE tenant_id=? AND id=?", (tenant_id, ep_id)).fetchone()
            return dict(row) if row else None

    def zeazverse_list_episodes(self, tenant_id: str, series_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with self.connection() as c:
            if series_id:
                rows = c.execute(
                    "SELECT * FROM zeazverse_episodes WHERE tenant_id=? AND series_id=? ORDER BY created_at DESC, id LIMIT ?",
                    (tenant_id, series_id, limit),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM zeazverse_episodes WHERE tenant_id=? ORDER BY created_at DESC, id LIMIT ?",
                    (tenant_id, limit),
                ).fetchall()
            return [dict(row) for row in rows]

    def zeazverse_update_episode_status(
        self, tenant_id: str, ep_id: str, status: str, extra_fields: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        allowed_fields = {
            "story_concept_json", "characters_json", "script_json", "storyboard_json",
            "asset_manifest_json", "render_manifest_json", "audio_plan_json",
            "editing_plan_json", "qa_report_json", "publishing_metadata_json",
        }
        if extra_fields and not set(extra_fields).issubset(allowed_fields):
            raise ValueError("unsupported ZEAZVERSE episode update field")
        now = utcnow()
        with self.connection() as c:
            row = c.execute(
                "SELECT status FROM zeazverse_episodes WHERE tenant_id=? AND id=?",
                (tenant_id, ep_id),
            ).fetchone()
            if not row:
                raise ValueError("episode not found")
            current_status = str(row["status"])
            approval_decision = current_status == "READY_FOR_REVIEW" and status in {"APPROVED", "CANCELLED"}
            if current_status in _PUBLISH_LOCKED_EPISODE_STATES and (extra_fields or (status != current_status and not approval_decision)):
                raise ValueError("episode content is locked pending publication")
            updated = c.execute(
                "UPDATE zeazverse_episodes SET status=?, updated_at=? WHERE tenant_id=? AND id=?",
                (status, now, tenant_id, ep_id),
            )
            if updated.rowcount != 1:
                raise ValueError("episode not found")
            if extra_fields:
                for k, v in extra_fields.items():
                    val = json_dumps(v) if isinstance(v, (dict, list)) else v
                    c.execute(f"UPDATE zeazverse_episodes SET {k}=? WHERE tenant_id=? AND id=?", (val, tenant_id, ep_id))
            return dict(c.execute("SELECT * FROM zeazverse_episodes WHERE tenant_id=? AND id=?", (tenant_id, ep_id)).fetchone())

    # ------------------ Storyboard & Scenes ------------------
    def zeazverse_save_scenes(self, tenant_id: str, ep_id: str, scenes: list[dict[str, Any]]) -> None:
        now = utcnow()
        with self.connection() as c:
            c.execute("DELETE FROM zeazverse_scenes WHERE tenant_id=? AND episode_id=?", (tenant_id, ep_id))
            for s in scenes:
                c.execute(
                    """INSERT INTO zeazverse_scenes (
                        tenant_id, episode_id, id, ordering, time_start_seconds, time_end_seconds,
                        characters_json, character_ref_ids_json, environment, subject_action,
                        camera_framing, camera_movement, lighting, physical_interaction,
                        dialogue_json, audio_json, positive_prompt, negative_prompt,
                        first_frame_continuity, last_frame_continuity, generation_model,
                        model_settings_json, expected_output, qa_checks_json, status,
                        output_artifact_uri, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        tenant_id,
                        ep_id,
                        s["id"],
                        s.get("ordering", 0),
                        s.get("time_start_seconds", 0.0),
                        s.get("time_end_seconds", 5.0),
                        json_dumps(s.get("characters", [])),
                        json_dumps(s.get("character_ref_ids", [])),
                        s.get("environment", ""),
                        s.get("subject_action", ""),
                        s.get("camera_framing", ""),
                        s.get("camera_movement", ""),
                        s.get("lighting", ""),
                        s.get("physical_interaction", ""),
                        json_dumps(s.get("dialogue", {})),
                        json_dumps(s.get("audio", {})),
                        s.get("positive_prompt", ""),
                        s.get("negative_prompt", ""),
                        s.get("first_frame_continuity", ""),
                        s.get("last_frame_continuity", ""),
                        s.get("generation_model", "mock-video-v1"),
                        json_dumps(s.get("model_settings", {})),
                        s.get("expected_output", ""),
                        json_dumps(s.get("qa_checks", [])),
                        s.get("status", "pending"),
                        s.get("output_artifact_uri", ""),
                        now,
                        now,
                    ),
                )

    def zeazverse_list_scenes(self, tenant_id: str, ep_id: str) -> list[dict[str, Any]]:
        with self.connection() as c:
            rows = c.execute(
                "SELECT * FROM zeazverse_scenes WHERE tenant_id=? AND episode_id=? ORDER BY ordering ASC",
                (tenant_id, ep_id),
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------ Approvals & Publications ------------------
    def zeazverse_create_approval_request(
        self, tenant_id: str, req_id: str, episode_id: str, target_visibility: str = "private", expected_etag: str = "", created_by: str = "operator"
    ) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                existing = c.execute(
                    "SELECT * FROM zeazverse_approval_requests WHERE tenant_id=? AND id=?",
                    (tenant_id, req_id),
                ).fetchone()
                if existing:
                    c.execute("COMMIT")
                    return dict(existing)
                transitioned = c.execute(
                    "UPDATE zeazverse_episodes SET status='READY_FOR_REVIEW',updated_at=? "
                    "WHERE tenant_id=? AND id=? AND status='QA_PASSED'",
                    (now, tenant_id, episode_id),
                )
                if transitioned.rowcount != 1:
                    c.execute("ROLLBACK")
                    raise ValueError("episode requires completed human visual QA before approval")
                c.execute(
                    """INSERT INTO zeazverse_approval_requests (
                        id, tenant_id, episode_id, action, target_visibility, expected_etag,
                        state, reviewer, comment, decided_at, consumed_at, created_by, created_at
                    ) VALUES (?, ?, ?, 'publish', ?, ?, 'pending', '', '', NULL, NULL, ?, ?)""",
                    (req_id, tenant_id, episode_id, target_visibility, expected_etag, created_by, now),
                )
                row = c.execute(
                    "SELECT * FROM zeazverse_approval_requests WHERE tenant_id=? AND id=?",
                    (tenant_id, req_id),
                ).fetchone()
                c.execute("COMMIT")
                return dict(row) if row else {}
            except Exception:
                try:
                    c.execute("ROLLBACK")
                except Exception:
                    pass
                raise

    def zeazverse_decide_approval(
        self, tenant_id: str, req_id: str, reviewer: str, approved: bool, comment: str = "",
        reviewer_name: str = "", expected_etag: str = "",
    ) -> dict[str, Any] | None:
        now = utcnow()
        state = "approved" if approved else "rejected"
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                current = c.execute(
                    "SELECT episode_id FROM zeazverse_approval_requests WHERE tenant_id=? AND id=?",
                    (tenant_id, req_id),
                ).fetchone()
                if not current:
                    c.execute("ROLLBACK")
                    return None
                result = c.execute(
                    "UPDATE zeazverse_approval_requests SET state=?, reviewer=?, comment=?, decided_at=? "
                    "WHERE tenant_id=? AND id=? AND state='pending' AND expected_etag=? AND created_by<>? "
                    "AND NOT EXISTS (SELECT 1 FROM api_keys2 k WHERE k.tenant_id=zeazverse_approval_requests.tenant_id "
                    "AND k.id=zeazverse_approval_requests.created_by AND k.name=?)",
                    (state, reviewer, comment[:2000], now, tenant_id, req_id, expected_etag, reviewer, reviewer_name),
                )
                if result.rowcount != 1:
                    c.execute("ROLLBACK")
                    return None
                updated_episode = c.execute(
                    "UPDATE zeazverse_episodes SET status=?,updated_at=? WHERE tenant_id=? AND id=? AND status='READY_FOR_REVIEW'",
                    ("APPROVED" if approved else "CANCELLED", now, tenant_id, current["episode_id"]),
                )
                if updated_episode.rowcount != 1:
                    c.execute("ROLLBACK")
                    return None
                row = c.execute(
                    "SELECT * FROM zeazverse_approval_requests WHERE tenant_id=? AND id=?",
                    (tenant_id, req_id),
                ).fetchone()
                c.execute("COMMIT")
                return dict(row) if row else None
            except Exception:
                try:
                    c.execute("ROLLBACK")
                except Exception:
                    pass
                raise

    def zeazverse_consume_approval(self, tenant_id: str, req_id: str) -> bool:
        now = utcnow()
        with self.connection() as c:
            result = c.execute(
                "UPDATE zeazverse_approval_requests SET consumed_at=? WHERE tenant_id=? AND id=? AND state='approved' AND consumed_at IS NULL",
                (now, tenant_id, req_id),
            )
            return result.rowcount == 1

    def zeazverse_record_publication(
        self, tenant_id: str, pub_id: str, episode_id: str, channel_id: str, video_id: str,
        visibility: str = "private", approval_id: str = "", idempotency_key: str = "",
        created_by: str = "system", status: str = "prepared", upload_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO zeazverse_publications (
                    id, tenant_id, episode_id, channel_id, platform, youtube_video_id,
                    visibility, made_for_kids, contains_synthetic_media, approval_request_id,
                    status, upload_etag, upload_metadata_json, error, idempotency_key,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'youtube', ?, ?, 0, 1, ?, ?, '', ?, '', ?, ?, ?, ?)
                ON CONFLICT DO NOTHING""",
                (
                    pub_id,
                    tenant_id,
                    episode_id,
                    channel_id,
                    video_id,
                    visibility,
                    approval_id,
                    status,
                    json_dumps(upload_metadata or {}),
                    idempotency_key,
                    created_by,
                    now,
                    now,
                ),
            )
            row = c.execute(
                "SELECT * FROM zeazverse_publications WHERE tenant_id=? AND id=?",
                (tenant_id, pub_id),
            ).fetchone()
            if not row and idempotency_key:
                row = c.execute(
                    "SELECT * FROM zeazverse_publications WHERE tenant_id=? AND idempotency_key=?",
                    (tenant_id, idempotency_key),
                ).fetchone()
            return dict(row) if row else {}

    def zeazverse_list_approvals(self, tenant_id: str, state: str = "pending", limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with self.connection() as c:
            if state:
                rows = c.execute(
                    "SELECT * FROM zeazverse_approval_requests WHERE tenant_id=? AND state=? ORDER BY created_at DESC LIMIT ?",
                    (tenant_id, state, limit),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM zeazverse_approval_requests WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",
                    (tenant_id, limit),
                ).fetchall()
            return [dict(row) for row in rows]

    def zeazverse_list_publications(self, tenant_id: str, episode_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with self.connection() as c:
            if episode_id:
                rows = c.execute(
                    "SELECT * FROM zeazverse_publications WHERE tenant_id=? AND episode_id=? ORDER BY created_at DESC LIMIT ?",
                    (tenant_id, episode_id, limit),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM zeazverse_publications WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",
                    (tenant_id, limit),
                ).fetchall()
            return [dict(row) for row in rows]
