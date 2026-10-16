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
                            json_dumps(data.get("dialogue_style", {})),
                            json_dumps(data.get("voice_profile", {})),
                            json_dumps(data.get("costume", {})),
                            json_dumps(data.get("accessories", [])),
                            json_dumps(data.get("consistency_rules", {})),
                            json_dumps(data.get("reference_turnaround", {})),
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

    def zeazverse_create_episode(
        self, tenant_id: str, ep_data: dict[str, Any], created_by: str = "system"
    ) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO zeazverse_episodes (
                    tenant_id, id, series_id, channel_id, story_id, title, content_class,
                    canvas_format, fps, target_duration_seconds, status,
                    story_concept_json, characters_json, script_json, storyboard_json,
                    asset_manifest_json, render_manifest_json, audio_plan_json,
                    editing_plan_json, qa_report_json, publishing_metadata_json,
                    version, idempotency_key, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
            return dict(c.execute("SELECT * FROM zeazverse_episodes WHERE tenant_id=? AND id=?", (tenant_id, ep_data["id"])).fetchone())

    def zeazverse_get_episode(self, tenant_id: str, ep_id: str) -> dict[str, Any] | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM zeazverse_episodes WHERE tenant_id=? AND id=?", (tenant_id, ep_id)).fetchone()
            return dict(row) if row else None

    def zeazverse_update_episode_status(
        self, tenant_id: str, ep_id: str, status: str, extra_fields: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as c:
            c.execute(
                "UPDATE zeazverse_episodes SET status=?, updated_at=? WHERE tenant_id=? AND id=?",
                (status, now, tenant_id, ep_id),
            )
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
            c.execute(
                """INSERT INTO zeazverse_approval_requests (
                    id, tenant_id, episode_id, action, target_visibility, expected_etag,
                    state, reviewer, comment, decided_at, consumed_at, created_by, created_at
                ) VALUES (?, ?, ?, 'publish', ?, ?, 'pending', '', '', NULL, NULL, ?, ?)""",
                (req_id, tenant_id, episode_id, target_visibility, expected_etag, created_by, now),
            )
            return dict(c.execute("SELECT * FROM zeazverse_approval_requests WHERE tenant_id=? AND id=?", (tenant_id, req_id)).fetchone())

    def zeazverse_decide_approval(
        self, tenant_id: str, req_id: str, reviewer: str, approved: bool, comment: str = ""
    ) -> dict[str, Any]:
        now = utcnow()
        state = "approved" if approved else "rejected"
        with self.connection() as c:
            c.execute(
                "UPDATE zeazverse_approval_requests SET state=?, reviewer=?, comment=?, decided_at=? WHERE tenant_id=? AND id=?",
                (state, reviewer, comment, now, tenant_id, req_id),
            )
            return dict(c.execute("SELECT * FROM zeazverse_approval_requests WHERE tenant_id=? AND id=?", (tenant_id, req_id)).fetchone())

    def zeazverse_consume_approval(self, tenant_id: str, req_id: str) -> None:
        now = utcnow()
        with self.connection() as c:
            c.execute(
                "UPDATE zeazverse_approval_requests SET consumed_at=? WHERE tenant_id=? AND id=? AND state='approved' AND consumed_at IS NULL",
                (now, tenant_id, req_id),
            )

    def zeazverse_record_publication(
        self, tenant_id: str, pub_id: str, episode_id: str, channel_id: str, video_id: str, visibility: str = "private", approval_id: str = "", idempotency_key: str = "", created_by: str = "system"
    ) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO zeazverse_publications (
                    id, tenant_id, episode_id, channel_id, platform, youtube_video_id,
                    visibility, made_for_kids, contains_synthetic_media, approval_request_id,
                    status, upload_etag, upload_metadata_json, error, idempotency_key,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'youtube', ?, ?, 0, 1, ?, 'published', '', '{}', '', ?, ?, ?, ?)""",
                (
                    pub_id,
                    tenant_id,
                    episode_id,
                    channel_id,
                    video_id,
                    visibility,
                    approval_id,
                    idempotency_key,
                    created_by,
                    now,
                    now,
                ),
            )
            return dict(c.execute("SELECT * FROM zeazverse_publications WHERE tenant_id=? AND id=?", (tenant_id, pub_id)).fetchone())
