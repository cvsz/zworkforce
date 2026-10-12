"""Kids Content Factory persistence mixin (tenant-scoped, transactional, audited)."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from .db_base import json_dumps, json_loads, utcnow
from .db_schema_kids import KIDS_SCHEMA_SQL
from .kids_factory import timeline_checksum


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class KidsMixin:
    def _kids_init(self, c) -> None:
        c.executescript(KIDS_SCHEMA_SQL)

    # ----- internal helpers -----
    def _kids_row(self, table: str, tenant_id: str, row_id: str, *, episode_col: str = "id") -> dict | None:
        with self.connection() as c:
            if table == "kids_scenes":
                return None
            row = c.execute(
                f"SELECT * FROM {table} WHERE tenant_id=? AND {episode_col}=?", (tenant_id, row_id)
            ).fetchone()
            return self._decode(dict(row)) if row else None

    # ----- brands -----
    def kids_upsert_brand(self, tenant_id: str, brand_id: str, validated: dict, actor: str) -> dict:
        now = utcnow()
        with self.connection() as c:
            row = c.execute("SELECT version FROM kids_brands WHERE tenant_id=? AND id=?", (tenant_id, brand_id)).fetchone()
            version = int(row[0]) + 1 if row else 1
            c.execute(
                """INSERT INTO kids_brands(tenant_id,id,name,description,age_range,language,art_style,music_style,
                voice_defaults_json,content_policy_json,publishing_json,version,archived,created_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tenant_id,id) DO UPDATE SET name=excluded.name,description=excluded.description,
                age_range=excluded.age_range,language=excluded.language,art_style=excluded.art_style,
                music_style=excluded.music_style,voice_defaults_json=excluded.voice_defaults_json,
                content_policy_json=excluded.content_policy_json,publishing_json=excluded.publishing_json,
                version=excluded.version,updated_at=excluded.updated_at""",
                (tenant_id, brand_id, validated["name"], validated["description"], validated["age_range"],
                 validated["language"], validated["art_style"], validated["music_style"],
                 json_dumps(validated["voice_defaults"]), json_dumps(validated["content_policy"]),
                 json_dumps(validated["publishing"]), version, 0, actor, now, now),
            )
            snap_id = uuid.uuid4().hex
            c.execute("INSERT INTO kids_brand_snapshots(id,tenant_id,brand_id,version,snapshot_json,created_at) VALUES(?,?,?,?,?,?)",
                      (snap_id, tenant_id, brand_id, version, json_dumps({**validated, "id": brand_id, "version": version}), now))
        self.audit(tenant_id, actor, "kids.brand.upsert", "kids_brand", brand_id, {"version": version})
        return self.kids_get_brand(tenant_id, brand_id) or {}

    def kids_get_brand(self, tenant_id: str, brand_id: str) -> dict | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM kids_brands WHERE tenant_id=? AND id=?", (tenant_id, brand_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def kids_list_brands(self, tenant_id: str, *, limit: int = 100, offset: int = 0, include_archived: bool = False) -> list[dict]:
        limit = max(1, min(int(limit or 100), 200)); offset = max(0, int(offset or 0))
        sql = "SELECT * FROM kids_brands WHERE tenant_id=?"
        if not include_archived:
            sql += " AND archived=0"
        sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        with self.connection() as c:
            return self._rows(c.execute(sql, (tenant_id, limit, offset)).fetchall())

    def kids_archive_brand(self, tenant_id: str, brand_id: str, actor: str) -> bool:
        with self.connection() as c:
            cur = c.execute("UPDATE kids_brands SET archived=1,updated_at=? WHERE tenant_id=? AND id=?", (utcnow(), tenant_id, brand_id))
            updated = cur.rowcount > 0
        if updated:
            self.audit(tenant_id, actor, "kids.brand.archive", "kids_brand", brand_id, {})
        return updated

    # ----- channels -----
    def kids_upsert_channel(self, tenant_id: str, channel_id: str, brand_id: str, payload: dict, actor: str) -> dict:
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO kids_channels(tenant_id,id,brand_id,name,platform,external_account_ref,publishing_settings_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id,id) DO UPDATE SET brand_id=excluded.brand_id,name=excluded.name,
                platform=excluded.platform,external_account_ref=excluded.external_account_ref,
                publishing_settings_json=excluded.publishing_settings_json,updated_at=excluded.updated_at""",
                (tenant_id, channel_id, brand_id, str(payload.get("name", channel_id))[:160],
                 str(payload.get("platform", "youtube"))[:40], str(payload.get("external_account_ref", ""))[:200],
                 json_dumps(payload.get("publishing_settings") or {}), now, now),
            )
            row = c.execute("SELECT * FROM kids_channels WHERE tenant_id=? AND id=?", (tenant_id, channel_id)).fetchone()
            result = self._decode(dict(row)) if row else {}
        self.audit(tenant_id, actor, "kids.channel.upsert", "kids_channel", channel_id, {"brand_id": brand_id})
        return result

    def kids_list_channels(self, tenant_id: str, *, brand_id: str = "") -> list[dict]:
        with self.connection() as c:
            if brand_id:
                return self._rows(c.execute("SELECT * FROM kids_channels WHERE tenant_id=? AND brand_id=? ORDER BY id", (tenant_id, brand_id)).fetchall())
            return self._rows(c.execute("SELECT * FROM kids_channels WHERE tenant_id=? ORDER BY id", (tenant_id,)).fetchall())

    # ----- characters -----
    def kids_upsert_character(self, tenant_id: str, character_id: str, brand_id: str, validated: dict, actor: str) -> dict:
        now = utcnow()
        with self.connection() as c:
            row = c.execute("SELECT version FROM kids_characters WHERE tenant_id=? AND id=?", (tenant_id, character_id)).fetchone()
            version = int(row[0]) + 1 if row else 1
            c.execute(
                """INSERT INTO kids_characters(tenant_id,id,brand_id,name,role,description,species,personality_json,
                voice_profile_json,palette_json,costume_json,negative_prompt,version,locked,approval_state,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, ?,?) ON CONFLICT(tenant_id,id) DO UPDATE SET brand_id=excluded.brand_id,
                name=excluded.name,role=excluded.role,description=excluded.description,species=excluded.species,
                personality_json=excluded.personality_json,voice_profile_json=excluded.voice_profile_json,
                palette_json=excluded.palette_json,costume_json=excluded.costume_json,negative_prompt=excluded.negative_prompt,
                version=excluded.version,updated_at=excluded.updated_at""",
                (tenant_id, character_id, brand_id, validated["name"], validated["role"], validated["description"],
                 validated["species"], json_dumps(validated["personality"]), json_dumps(validated["voice_profile"]),
                 json_dumps(validated["palette"]), json_dumps(validated["costume"]), validated["negative_prompt"],
                 version, 0, "draft", now, now),
            )
            c.execute("INSERT INTO kids_character_versions(id,tenant_id,character_id,version,snapshot_json,created_by,created_at) VALUES(?,?,?,?,?,?,?)",
                      (uuid.uuid4().hex, tenant_id, character_id, version,
                       json_dumps({**validated, "brand_id": brand_id, "version": version}), actor, now))
            row = c.execute("SELECT * FROM kids_characters WHERE tenant_id=? AND id=?", (tenant_id, character_id)).fetchone()
            result = self._decode(dict(row)) if row else {}
        self.audit(tenant_id, actor, "kids.character.upsert", "kids_character", character_id, {"version": version})
        return result

    def kids_get_character(self, tenant_id: str, character_id: str) -> dict | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM kids_characters WHERE tenant_id=? AND id=?", (tenant_id, character_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def kids_list_characters(self, tenant_id: str, *, brand_id: str = "") -> list[dict]:
        with self.connection() as c:
            if brand_id:
                return self._rows(c.execute("SELECT * FROM kids_characters WHERE tenant_id=? AND brand_id=? ORDER BY name", (tenant_id, brand_id)).fetchall())
            return self._rows(c.execute("SELECT * FROM kids_characters WHERE tenant_id=? ORDER BY name", (tenant_id,)).fetchall())

    def kids_lock_character(self, tenant_id: str, character_id: str, actor: str, *, locked: bool = True) -> bool:
        with self.connection() as c:
            cur = c.execute("UPDATE kids_characters SET locked=?,updated_at=? WHERE tenant_id=? AND id=?",
                            (int(bool(locked)), utcnow(), tenant_id, character_id))
            updated = cur.rowcount > 0
        if updated:
            self.audit(tenant_id, actor, "kids.character.lock", "kids_character", character_id, {"locked": bool(locked)})
        return updated

    # ----- episodes -----
    def kids_create_episode(self, tenant_id: str, episode_id: str, brand_id: str, validated: dict, actor: str, *, channel_id: str = "", idempotency_key: str = "") -> tuple[dict, bool]:
        now = utcnow()
        if idempotency_key:
            with self.connection() as c:
                row = c.execute("SELECT * FROM kids_episodes WHERE tenant_id=? AND idempotency_key=?", (tenant_id, idempotency_key)).fetchone()
                if row:
                    return self._decode(dict(row)), False
        with self.connection() as c:
            exists = c.execute("SELECT id FROM kids_episodes WHERE tenant_id=? AND id=?", (tenant_id, episode_id)).fetchone()
            created = not bool(exists)
            if created:
                c.execute(
                    """INSERT INTO kids_episodes(tenant_id,id,brand_id,channel_id,title,summary,age_band,language,objectives_json,
                    vocabulary_json,status,version,budget_credits,idempotency_key,created_by,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (tenant_id, episode_id, brand_id, channel_id, validated["title"], validated["summary"],
                     validated["age_band"], validated["language"], json_dumps(validated["objectives"]),
                     json_dumps(validated["vocabulary"]), "draft", 1, float(validated["budget_credits"]),
                     idempotency_key or "", actor, now, now),
                )
            row = c.execute("SELECT * FROM kids_episodes WHERE tenant_id=? AND id=?", (tenant_id, episode_id)).fetchone()
            result = self._decode(dict(row)) if row else {}
        if created:
            self.audit(tenant_id, actor, "kids.episode.create", "kids_episode", episode_id, {"brand_id": brand_id})
        return result, created

    def kids_get_episode(self, tenant_id: str, episode_id: str) -> dict | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM kids_episodes WHERE tenant_id=? AND id=?", (tenant_id, episode_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def kids_list_episodes(self, tenant_id: str, *, brand_id: str = "", status: str = "", limit: int = 100, offset: int = 0) -> list[dict]:
        limit = max(1, min(int(limit or 100), 200)); offset = max(0, int(offset or 0))
        sql = "SELECT * FROM kids_episodes WHERE tenant_id=?"; args: list = [tenant_id]
        if brand_id:
            sql += " AND brand_id=?"; args.append(brand_id)
        if status:
            sql += " AND status=?"; args.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"; args += [limit, offset]
        with self.connection() as c:
            return self._rows(c.execute(sql, tuple(args)).fetchall())

    def kids_set_episode_status(self, tenant_id: str, episode_id: str, status: str, actor: str) -> bool:
        allowed = {"draft", "scripted", "storyboarded", "rendered", "in_review", "approved", "rejected", "published"}
        if status not in allowed:
            raise ValueError(f"unknown episode status '{status}'")
        with self.connection() as c:
            cur = c.execute("UPDATE kids_episodes SET status=?,updated_at=? WHERE tenant_id=? AND id=?", (status, utcnow(), tenant_id, episode_id))
            updated = cur.rowcount > 0
        if updated:
            self.audit(tenant_id, actor, "kids.episode.status", "kids_episode", episode_id, {"status": status})
        return updated

    # ----- scripts -----
    def kids_save_script(self, tenant_id: str, episode_id: str, validated: dict, actor: str) -> dict:
        with self.connection() as c:
            row = c.execute("SELECT COALESCE(MAX(version),0) n FROM kids_scripts WHERE tenant_id=? AND episode_id=?", (tenant_id, episode_id)).fetchone()
            version = int(row["n"] if hasattr(row, "keys") else row[0]) + 1
            script_id = uuid.uuid4().hex
            c.execute("INSERT INTO kids_scripts(id,tenant_id,episode_id,version,content_type,body_json,provenance_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                      (script_id, tenant_id, episode_id, version, validated["content_type"], json_dumps(validated["body"]),
                       json_dumps({"origin": "kids_factory", "synthetic": True}), actor, utcnow()))
            row = c.execute("SELECT * FROM kids_scripts WHERE id=?", (script_id,)).fetchone()
            result = self._decode(dict(row)) if row else {}
        self.audit(tenant_id, actor, "kids.script.save", "kids_episode", episode_id, {"version": version})
        return result

    def kids_latest_script(self, tenant_id: str, episode_id: str) -> dict | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM kids_scripts WHERE tenant_id=? AND episode_id=? ORDER BY version DESC LIMIT 1", (tenant_id, episode_id)).fetchone()
            return self._decode(dict(row)) if row else None

    # ----- scenes -----
    def kids_upsert_scene(self, tenant_id: str, episode_id: str, scene_id: str, validated: dict, actor: str) -> dict:
        now = utcnow()
        checksum = hashlib.sha256(json_dumps(validated).encode()).hexdigest()[:16]
        with self.connection() as c:
            c.execute(
                """INSERT INTO kids_scenes(tenant_id,episode_id,id,ordering,duration_seconds,objective,visual_prompt,negative_prompt,
                character_refs_json,camera_json,dialogue_json,music_cues_json,captions_json,asset_ids_json,checksum,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id,episode_id,id) DO UPDATE SET
                ordering=excluded.ordering,duration_seconds=excluded.duration_seconds,objective=excluded.objective,
                visual_prompt=excluded.visual_prompt,negative_prompt=excluded.negative_prompt,
                character_refs_json=excluded.character_refs_json,camera_json=excluded.camera_json,
                dialogue_json=excluded.dialogue_json,music_cues_json=excluded.music_cues_json,
                captions_json=excluded.captions_json,asset_ids_json=excluded.asset_ids_json,
                checksum=excluded.checksum,updated_at=excluded.updated_at""",
                (tenant_id, episode_id, scene_id, int(validated["ordering"]), float(validated["duration_seconds"]),
                 validated["objective"], validated["visual_prompt"], validated["negative_prompt"],
                 json_dumps(validated["character_refs"]), json_dumps(validated["camera"]), json_dumps(validated["dialogue"]),
                 json_dumps(validated["music_cues"]), json_dumps(validated["captions"]), json_dumps(validated["asset_ids"]),
                 checksum, now, now),
            )
            row = c.execute("SELECT * FROM kids_scenes WHERE tenant_id=? AND episode_id=? AND id=?", (tenant_id, episode_id, scene_id)).fetchone()
            result = self._decode(dict(row)) if row else {}
        self.audit(tenant_id, actor, "kids.scene.upsert", "kids_episode", episode_id, {"scene_id": scene_id})
        return result

    def kids_list_scenes(self, tenant_id: str, episode_id: str) -> list[dict]:
        with self.connection() as c:
            return self._rows(c.execute("SELECT * FROM kids_scenes WHERE tenant_id=? AND episode_id=? ORDER BY ordering", (tenant_id, episode_id)).fetchall())

    # ----- assets -----
    def kids_register_asset(self, tenant_id: str, asset: dict, actor: str) -> dict:
        asset_id = asset.get("id") or uuid.uuid4().hex[:12]
        with self.connection() as c:
            c.execute(
                """INSERT INTO kids_assets(id,tenant_id,episode_id,scene_id,kind,name,storage_uri,sha256,size_bytes,provenance_json,version,created_by,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING""",
                (asset_id, tenant_id, asset.get("episode_id", ""), asset.get("scene_id", ""), asset.get("kind", "image"),
                 asset.get("name", "")[:180], asset.get("storage_uri", "")[:1000], asset.get("sha256", "")[:64],
                 int(asset.get("size_bytes", 0)), json_dumps(asset.get("provenance") or {}), int(asset.get("version", 1)), actor, utcnow()),
            )
            row = c.execute("SELECT * FROM kids_assets WHERE id=?", (asset_id,)).fetchone()
            result = self._decode(dict(row)) if row else {}
            if result and result.get("tenant_id") != tenant_id:
                raise ValueError("cross-tenant asset access denied")
        self.audit(tenant_id, actor, "kids.asset.register", "kids_asset", asset_id, {"sha256": asset.get("sha256", "")[:16]})
        return result

    def kids_list_assets(self, tenant_id: str, *, episode_id: str = "") -> list[dict]:
        with self.connection() as c:
            if episode_id:
                return self._rows(c.execute("SELECT * FROM kids_assets WHERE tenant_id=? AND episode_id=? ORDER BY created_at", (tenant_id, episode_id)).fetchall())
            return self._rows(c.execute("SELECT * FROM kids_assets WHERE tenant_id=? ORDER BY created_at DESC LIMIT 200", (tenant_id,)).fetchall())

    # ----- timelines -----
    def kids_save_timeline(self, tenant_id: str, episode_id: str, tracks: dict, actor: str) -> dict:
        with self.connection() as c:
            row = c.execute("SELECT COALESCE(MAX(version),0) n FROM kids_timelines WHERE tenant_id=? AND episode_id=?", (tenant_id, episode_id)).fetchone()
            version = int(row["n"] if hasattr(row, "keys") else row[0]) + 1
            checksum = timeline_checksum(tracks)
            c.execute("INSERT INTO kids_timelines(tenant_id,episode_id,version,tracks_json,checksum,created_by,created_at) VALUES(?,?,?,?,?,?,?)",
                      (tenant_id, episode_id, version, json_dumps(tracks), checksum, actor, utcnow()))
        self.audit(tenant_id, actor, "kids.timeline.save", "kids_episode", episode_id, {"version": version, "checksum": checksum[:12]})
        return {"episode_id": episode_id, "version": version, "checksum": checksum, "tracks": tracks}

    def kids_latest_timeline(self, tenant_id: str, episode_id: str) -> dict | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM kids_timelines WHERE tenant_id=? AND episode_id=? ORDER BY version DESC LIMIT 1", (tenant_id, episode_id)).fetchone()
            return self._decode(dict(row)) if row else None

    # ----- render jobs -----
    def kids_submit_render(self, tenant_id: str, episode_id: str, timeline_version: int, preset: str, actor: str, *, idempotency_key: str = "") -> tuple[dict, bool]:
        if idempotency_key:
            with self.connection() as c:
                row = c.execute("SELECT * FROM kids_render_jobs WHERE tenant_id=? AND idempotency_key=?", (tenant_id, idempotency_key)).fetchone()
                if row:
                    return self._decode(dict(row)), False
        job_id = uuid.uuid4().hex[:12]
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO kids_render_jobs(id,tenant_id,episode_id,timeline_version,preset,status,output_uri,output_sha256,
                thumbnail_uri,error,idempotency_key,attempts,created_by,created_at,updated_at,finished_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)""",
                (job_id, tenant_id, episode_id, int(timeline_version), preset, "queued", "", "", "", "", idempotency_key or "", 0, actor, now, now),
            )
            row = c.execute("SELECT * FROM kids_render_jobs WHERE id=?", (job_id,)).fetchone()
            result = self._decode(dict(row)) if row else {}
        self.audit(tenant_id, actor, "kids.render.submit", "kids_render", job_id, {"episode_id": episode_id})
        return result, True

    def kids_update_render(self, tenant_id: str, job_id: str, patch: dict, actor: str) -> dict | None:
        allowed = {"status", "output_uri", "output_sha256", "thumbnail_uri", "error"}
        sets: list[str] = []; args: list = []
        for key in allowed:
            if key in patch:
                sets.append(f"{key}=?"); args.append(patch[key])
        if not sets:
            return self.kids_get_render(tenant_id, job_id)
        sets.append("updated_at=?"); args.append(utcnow())
        if patch.get("status") in ("succeeded", "failed"):
            sets.append("finished_at=?"); args.append(utcnow())
        args += [tenant_id, job_id]
        with self.connection() as c:
            cur = c.execute(f"UPDATE kids_render_jobs SET {', '.join(sets)} WHERE tenant_id=? AND id=?", tuple(args))
            if cur.rowcount == 0:
                return None
            row = c.execute("SELECT * FROM kids_render_jobs WHERE tenant_id=? AND id=?", (tenant_id, job_id)).fetchone()
            result = self._decode(dict(row)) if row else None
        self.audit(tenant_id, actor, "kids.render.update", "kids_render", job_id, {"status": patch.get("status", "")})
        return result

    def kids_get_render(self, tenant_id: str, job_id: str) -> dict | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM kids_render_jobs WHERE tenant_id=? AND id=?", (tenant_id, job_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def kids_list_renders(self, tenant_id: str, *, episode_id: str = "", limit: int = 50) -> list[dict]:
        with self.connection() as c:
            if episode_id:
                return self._rows(c.execute("SELECT * FROM kids_render_jobs WHERE tenant_id=? AND episode_id=? ORDER BY created_at DESC LIMIT ?",
                                            (tenant_id, episode_id, max(1, min(int(limit), 200)))).fetchall())
            return self._rows(c.execute("SELECT * FROM kids_render_jobs WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",
                                        (tenant_id, max(1, min(int(limit), 200)))).fetchall())

    # ----- approvals + moderation -----
    def kids_request_approval(self, tenant_id: str, episode_id: str, subject_type: str, subject_id: str, version: int, actor: str) -> dict:
        approval_id = uuid.uuid4().hex[:12]
        with self.connection() as c:
            c.execute(
                """INSERT INTO kids_approvals(id,tenant_id,episode_id,subject_type,subject_id,subject_version,state,reviewer,comment,created_by,created_at,decided_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,NULL)""",
                (approval_id, tenant_id, episode_id, subject_type, subject_id, int(version), "pending", "", "", actor, utcnow()),
            )
            row = c.execute("SELECT * FROM kids_approvals WHERE id=?", (approval_id,)).fetchone()
            result = self._decode(dict(row)) if row else {}
        self.audit(tenant_id, actor, "kids.approval.request", "kids_approval", approval_id, {"episode_id": episode_id})
        return result

    def kids_decide_approval(self, tenant_id: str, approval_id: str, decision: str, reviewer: str, comment: str = "") -> dict | None:
        if decision not in ("approved", "rejected"):
            raise ValueError("decision must be approved/rejected")
        with self.connection() as c:
            row = c.execute("SELECT * FROM kids_approvals WHERE tenant_id=? AND id=?", (tenant_id, approval_id)).fetchone()
            if not row:
                return None
            current = self._decode(dict(row))
            if current.get("state") != "pending":
                return current
            c.execute("UPDATE kids_approvals SET state=?,reviewer=?,comment=?,decided_at=? WHERE tenant_id=? AND id=?",
                      (decision, reviewer, comment[:1000], utcnow(), tenant_id, approval_id))
            row = c.execute("SELECT * FROM kids_approvals WHERE tenant_id=? AND id=?", (tenant_id, approval_id)).fetchone()
            result = self._decode(dict(row)) if row else None
        self.audit(tenant_id, reviewer, "kids.approval.decide", "kids_approval", approval_id, {"decision": decision})
        if result and decision == "approved":
            self.kids_set_episode_status(tenant_id, result["episode_id"], "approved", reviewer)
        elif result:
            self.kids_set_episode_status(tenant_id, result["episode_id"], "rejected", reviewer)
        return result

    def kids_list_approvals(self, tenant_id: str, *, state: str = "", limit: int = 100) -> list[dict]:
        with self.connection() as c:
            if state:
                return self._rows(c.execute("SELECT * FROM kids_approvals WHERE tenant_id=? AND state=? ORDER BY created_at DESC LIMIT ?",
                                            (tenant_id, state, max(1, min(int(limit), 200)))).fetchall())
            return self._rows(c.execute("SELECT * FROM kids_approvals WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",
                                        (tenant_id, max(1, min(int(limit), 200)))).fetchall())

    def kids_get_approval(self, tenant_id: str, approval_id: str) -> dict | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM kids_approvals WHERE tenant_id=? AND id=?", (tenant_id, approval_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def kids_episode_approved(self, tenant_id: str, episode_id: str) -> bool:
        with self.connection() as c:
            row = c.execute("SELECT 1 FROM kids_approvals WHERE tenant_id=? AND episode_id=? AND state='approved' LIMIT 1",
                            (tenant_id, episode_id)).fetchone()
            return bool(row)

    def kids_save_moderation(self, tenant_id: str, episode_id: str, report: dict, actor: str, *, scene_id: str = "") -> dict:
        mod_id = uuid.uuid4().hex[:12]
        with self.connection() as c:
            c.execute("INSERT INTO kids_moderation(id,tenant_id,episode_id,scene_id,checklist_json,passed,findings_json,reviewer,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                      (mod_id, tenant_id, episode_id, scene_id, json_dumps(report.get("checklist") or []),
                       int(bool(report.get("passed"))), json_dumps(report.get("findings") or []), actor, utcnow()))
            row = c.execute("SELECT * FROM kids_moderation WHERE id=?", (mod_id,)).fetchone()
            result = self._decode(dict(row)) if row else {}
        self.audit(tenant_id, actor, "kids.moderation.save", "kids_episode", episode_id, {"passed": bool(report.get("passed"))})
        return result

    # ----- publishing (approval-gated, idempotent, mock by default) -----
    def kids_prepare_publishing(self, tenant_id: str, episode_id: str, payload: dict, actor: str, *, idempotency_key: str = "") -> tuple[dict, bool]:
        if idempotency_key:
            with self.connection() as c:
                row = c.execute("SELECT * FROM kids_publishing_jobs WHERE tenant_id=? AND idempotency_key=?", (tenant_id, idempotency_key)).fetchone()
                if row:
                    return self._decode(dict(row)), False
        job_id = uuid.uuid4().hex[:12]
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO kids_publishing_jobs(id,tenant_id,episode_id,render_job_id,channel_id,platform,title,description,
                audience,visibility,status,external_id,error,idempotency_key,approval_id,created_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (job_id, tenant_id, episode_id, str(payload.get("render_job_id", ""))[:32], str(payload.get("channel_id", ""))[:64],
                 str(payload.get("platform", "youtube_mock"))[:32], str(payload.get("title", ""))[:100],
                 str(payload.get("description", ""))[:5000], str(payload.get("audience", "madeForKids"))[:24],
                 str(payload.get("visibility", "private"))[:16], "prepared", "", "", idempotency_key or "",
                 str(payload.get("approval_id", ""))[:32], actor, now, now),
            )
            row = c.execute("SELECT * FROM kids_publishing_jobs WHERE id=?", (job_id,)).fetchone()
            result = self._decode(dict(row)) if row else {}
        self.audit(tenant_id, actor, "kids.publishing.prepare", "kids_publishing", job_id, {"episode_id": episode_id})
        return result, True

    def kids_publish_approved(self, tenant_id: str, job_id: str, external: dict, actor: str) -> dict | None:
        """Complete a prepared job only when a matching approved approval exists."""
        with self.connection() as c:
            row = c.execute("SELECT * FROM kids_publishing_jobs WHERE tenant_id=? AND id=?", (tenant_id, job_id)).fetchone()
            if not row:
                return None
            job = self._decode(dict(row))
            if job.get("status") == "published":
                return job
            approval = None
            if job.get("approval_id"):
                arow = c.execute("SELECT * FROM kids_approvals WHERE tenant_id=? AND id=?", (tenant_id, job["approval_id"])).fetchone()
                approval = self._decode(dict(arow)) if arow else None
            if not approval or approval.get("state") != "approved" or approval.get("episode_id") != job.get("episode_id"):
                raise ValueError("publishing blocked: no approved publishing action for this episode")
            c.execute("UPDATE kids_publishing_jobs SET status='published',external_id=?,updated_at=? WHERE tenant_id=? AND id=?",
                      (str(external.get("external_id", ""))[:64], utcnow(), tenant_id, job_id))
            row = c.execute("SELECT * FROM kids_publishing_jobs WHERE tenant_id=? AND id=?", (tenant_id, job_id)).fetchone()
            result = self._decode(dict(row)) if row else None
        self.audit(tenant_id, actor, "kids.publishing.publish", "kids_publishing", job_id, {"external_id": external.get("external_id", "")})
        if result:
            self.kids_set_episode_status(tenant_id, job["episode_id"], "published", actor)
        return result

    def kids_get_publishing(self, tenant_id: str, job_id: str) -> dict | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM kids_publishing_jobs WHERE tenant_id=? AND id=?", (tenant_id, job_id)).fetchone()
            return self._decode(dict(row)) if row else None

    def kids_list_publishing(self, tenant_id: str, *, episode_id: str = "") -> list[dict]:
        with self.connection() as c:
            if episode_id:
                return self._rows(c.execute("SELECT * FROM kids_publishing_jobs WHERE tenant_id=? AND episode_id=? ORDER BY created_at DESC",
                                            (tenant_id, episode_id)).fetchall())
            return self._rows(c.execute("SELECT * FROM kids_publishing_jobs WHERE tenant_id=? ORDER BY created_at DESC LIMIT 100", (tenant_id,)).fetchall())

    # ----- analytics (synthetic labeled) + usage -----
    def kids_save_analytics(self, tenant_id: str, payload: dict) -> dict:
        snap_id = uuid.uuid4().hex[:12]
        with self.connection() as c:
            c.execute("INSERT INTO kids_analytics(id,tenant_id,channel_id,episode_id,period,metrics_json,synthetic,captured_at) VALUES(?,?,?,?,?,?,?,?)",
                      (snap_id, tenant_id, str(payload.get("channel_id", ""))[:64], str(payload.get("episode_id", ""))[:32],
                       str(payload.get("period", "7d"))[:16], json_dumps(payload.get("metrics") or {}),
                       int(bool(payload.get("synthetic", True))), utcnow()))
            row = c.execute("SELECT * FROM kids_analytics WHERE id=?", (snap_id,)).fetchone()
            return self._decode(dict(row)) if row else {}

    def kids_list_analytics(self, tenant_id: str, *, channel_id: str = "") -> list[dict]:
        with self.connection() as c:
            if channel_id:
                return self._rows(c.execute("SELECT * FROM kids_analytics WHERE tenant_id=? AND channel_id=? ORDER BY captured_at DESC LIMIT 100",
                                            (tenant_id, channel_id)).fetchall())
            return self._rows(c.execute("SELECT * FROM kids_analytics WHERE tenant_id=? ORDER BY captured_at DESC LIMIT 100", (tenant_id,)).fetchall())

    def kids_record_usage(self, tenant_id: str, episode_id: str, provider: str, capability: str, quantity: float, cost: float) -> None:
        with self.connection() as c:
            c.execute("INSERT INTO kids_usage(tenant_id,episode_id,provider,capability,quantity,cost_credits,created_at) VALUES(?,?,?,?,?,?,?)",
                      (tenant_id, episode_id, provider[:64], capability[:32], float(quantity), float(cost), utcnow()))

    def kids_usage_summary(self, tenant_id: str) -> dict:
        with self.connection() as c:
            row = c.execute("SELECT COALESCE(SUM(quantity),0) q,COALESCE(SUM(cost_credits),0) cost,COUNT(*) n FROM kids_usage WHERE tenant_id=?", (tenant_id,)).fetchone()
            d = dict(row)
            return {"events": int(d.get("n", 0)), "quantity": float(d.get("q", 0)), "cost_credits": float(d.get("cost", 0))}

    def kids_overview(self, tenant_id: str) -> dict:
        with self.connection() as c:
            def count(sql: str, args: tuple) -> int:
                row = c.execute(sql, args).fetchone()
                return int(row[0])
            return {
                "brands": count("SELECT COUNT(*) FROM kids_brands WHERE tenant_id=? AND archived=0", (tenant_id,)),
                "channels": count("SELECT COUNT(*) FROM kids_channels WHERE tenant_id=?", (tenant_id,)),
                "campaigns": count("SELECT COUNT(*) FROM kids_campaigns WHERE tenant_id=?", (tenant_id,)),
                "characters": count("SELECT COUNT(*) FROM kids_characters WHERE tenant_id=?", (tenant_id,)),
                "episodes": count("SELECT COUNT(*) FROM kids_episodes WHERE tenant_id=?", (tenant_id,)),
                "pending_approvals": count("SELECT COUNT(*) FROM kids_approvals WHERE tenant_id=? AND state='pending'", (tenant_id,)),
                "render_jobs": count("SELECT COUNT(*) FROM kids_render_jobs WHERE tenant_id=?", (tenant_id,)),
                "published_videos": count("SELECT COUNT(*) FROM kids_publishing_jobs WHERE tenant_id=? AND status='published'", (tenant_id,)),
                "failed_renders": count("SELECT COUNT(*) FROM kids_render_jobs WHERE tenant_id=? AND status='failed'", (tenant_id,)),
                "agent_runs": count("SELECT COUNT(*) FROM kids_agent_runs WHERE tenant_id=?", (tenant_id,)),
            }

    # ----- campaigns -----
    def kids_upsert_campaign(self, tenant_id: str, campaign_id: str, brand_id: str, payload: dict, actor: str) -> dict:
        now = utcnow()
        name = str(payload.get("name", campaign_id))[:160] or campaign_id
        with self.connection() as c:
            c.execute(
                """INSERT INTO kids_campaigns(tenant_id,id,brand_id,name,topic,curriculum_json,playlist_json,calendar_json,status,created_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id,id) DO UPDATE SET brand_id=excluded.brand_id,name=excluded.name,
                topic=excluded.topic,curriculum_json=excluded.curriculum_json,playlist_json=excluded.playlist_json,
                calendar_json=excluded.calendar_json,status=excluded.status,updated_at=excluded.updated_at""",
                (tenant_id, campaign_id, brand_id, name, str(payload.get("topic", ""))[:500],
                 json_dumps(payload.get("curriculum") or {}), json_dumps(payload.get("playlist") or []),
                 json_dumps(payload.get("calendar") or {}), str(payload.get("status", "planned"))[:24], actor, now, now),
            )
            row = c.execute("SELECT * FROM kids_campaigns WHERE tenant_id=? AND id=?", (tenant_id, campaign_id)).fetchone()
            result = self._decode(dict(row)) if row else {}
        self.audit(tenant_id, actor, "kids.campaign.upsert", "kids_campaign", campaign_id, {"brand_id": brand_id})
        return result

    def kids_list_campaigns(self, tenant_id: str, *, brand_id: str = "") -> list[dict]:
        with self.connection() as c:
            if brand_id:
                return self._rows(c.execute("SELECT * FROM kids_campaigns WHERE tenant_id=? AND brand_id=? ORDER BY updated_at DESC",
                                            (tenant_id, brand_id)).fetchall())
            return self._rows(c.execute("SELECT * FROM kids_campaigns WHERE tenant_id=? ORDER BY updated_at DESC LIMIT 200",
                                        (tenant_id,)).fetchall())

    def kids_get_campaign(self, tenant_id: str, campaign_id: str) -> dict | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM kids_campaigns WHERE tenant_id=? AND id=?", (tenant_id, campaign_id)).fetchone()
            return self._decode(dict(row)) if row else None

    # ----- agent runs (durable checkpoints, idempotent steps) -----
    def kids_record_agent_run(self, tenant_id: str, episode_id: str, agent: str, step: str, status: str,
                              actor: str, *, input_data: dict | None = None, output_data: dict | None = None,
                              error: str = "", idempotency_key: str = "") -> tuple[dict, bool]:
        if idempotency_key:
            with self.connection() as c:
                row = c.execute("SELECT * FROM kids_agent_runs WHERE tenant_id=? AND idempotency_key=?",
                                (tenant_id, idempotency_key)).fetchone()
                if row:
                    return self._decode(dict(row)), False
        run_id = uuid.uuid4().hex[:12]
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO kids_agent_runs(id,tenant_id,episode_id,agent,step,status,input_json,output_json,attempts,error,idempotency_key,created_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (run_id, tenant_id, episode_id, agent[:64], step[:64], status[:24], json_dumps(input_data or {}),
                 json_dumps(output_data or {}), 1, error[:2000], idempotency_key or "", actor, now, now),
            )
            row = c.execute("SELECT * FROM kids_agent_runs WHERE id=?", (run_id,)).fetchone()
            result = self._decode(dict(row)) if row else {}
        self.audit(tenant_id, actor, "kids.agent_run", "kids_episode", episode_id, {"agent": agent, "step": step, "status": status})
        return result, True

    def kids_list_agent_runs(self, tenant_id: str, *, episode_id: str = "", limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit or 100), 200))
        with self.connection() as c:
            if episode_id:
                return self._rows(c.execute("SELECT * FROM kids_agent_runs WHERE tenant_id=? AND episode_id=? ORDER BY created_at LIMIT ?",
                                            (tenant_id, episode_id, limit)).fetchall())
            return self._rows(c.execute("SELECT * FROM kids_agent_runs WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",
                                        (tenant_id, limit)).fetchall())

    # ----- derivations (e.g. Shorts from landscape episodes) -----
    def kids_record_derivation(self, tenant_id: str, parent_id: str, child_id: str, kind: str, actor: str) -> dict:
        from .db_base import utcnow as _now
        with self.connection() as c:
            c.execute("INSERT INTO kids_derivations(tenant_id,parent_episode_id,child_episode_id,kind,created_by,created_at) VALUES(?,?,?,?,?,?)",
                      (tenant_id, parent_id, child_id, kind[:24], actor, _now()))
            row = c.execute("SELECT * FROM kids_derivations WHERE tenant_id=? AND child_episode_id=?", (tenant_id, child_id)).fetchone()
            return dict(row) if row else {}

    def kids_get_derivation(self, tenant_id: str, child_id: str) -> dict | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM kids_derivations WHERE tenant_id=? AND child_episode_id=?", (tenant_id, child_id)).fetchone()
            return dict(row) if row else None

    def kids_list_derivations(self, tenant_id: str, *, parent_id: str = "") -> list[dict]:
        with self.connection() as c:
            if parent_id:
                rows = c.execute("SELECT * FROM kids_derivations WHERE tenant_id=? AND parent_episode_id=? ORDER BY created_at",
                                 (tenant_id, parent_id)).fetchall()
            else:
                rows = c.execute("SELECT * FROM kids_derivations WHERE tenant_id=? ORDER BY created_at DESC LIMIT 200", (tenant_id,)).fetchall()
            return [dict(r) for r in rows]

    # ----- voice profiles -----
    def kids_upsert_voice(self, tenant_id: str, voice_id: str, validated: dict, actor: str) -> dict:
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO kids_voice_profiles(tenant_id,id,name,provider,model,voice_id,language,style,speed,rights_json,created_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id,id) DO UPDATE SET name=excluded.name,provider=excluded.provider,
                model=excluded.model,voice_id=excluded.voice_id,language=excluded.language,style=excluded.style,speed=excluded.speed,
                rights_json=excluded.rights_json,updated_at=excluded.updated_at""",
                (tenant_id, voice_id, validated["name"], validated["provider"], validated["model"], validated["voice_id"],
                 validated["language"], validated["style"], float(validated["speed"]), json_dumps(validated["rights"]), actor, now, now),
            )
            row = c.execute("SELECT * FROM kids_voice_profiles WHERE tenant_id=? AND id=?", (tenant_id, voice_id)).fetchone()
            result = self._decode(dict(row)) if row else {}
        self.audit(tenant_id, actor, "kids.voice.upsert", "kids_voice", voice_id, {"language": validated["language"]})
        return result

    def kids_list_voices(self, tenant_id: str, *, language: str = "") -> list[dict]:
        with self.connection() as c:
            if language:
                return self._rows(c.execute("SELECT * FROM kids_voice_profiles WHERE tenant_id=? AND language=? ORDER BY name",
                                            (tenant_id, language)).fetchall())
            return self._rows(c.execute("SELECT * FROM kids_voice_profiles WHERE tenant_id=? ORDER BY name", (tenant_id,)).fetchall())

    def kids_get_voice(self, tenant_id: str, voice_id: str) -> dict | None:
        with self.connection() as c:
            row = c.execute("SELECT * FROM kids_voice_profiles WHERE tenant_id=? AND id=?", (tenant_id, voice_id)).fetchone()
            return self._decode(dict(row)) if row else None

    # ----- music tracks -----
    def kids_register_music(self, tenant_id: str, validated: dict, actor: str, *, episode_id: str = "", asset_id: str = "") -> dict:
        import uuid as _uuid
        track_id = _uuid.uuid4().hex[:12]
        with self.connection() as c:
            c.execute("INSERT INTO kids_music_tracks(id,tenant_id,episode_id,title,provider,license,provenance_json,duration_seconds,asset_id,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                      (track_id, tenant_id, episode_id[:32], validated["title"], validated["provider"], validated["license"],
                       json_dumps({**validated["provenance"], "synthetic": True}), float(validated["duration_seconds"]),
                       asset_id[:32], actor, utcnow()))
            row = c.execute("SELECT * FROM kids_music_tracks WHERE id=?", (track_id,)).fetchone()
            result = self._decode(dict(row)) if row else {}
        self.audit(tenant_id, actor, "kids.music.register", "kids_music", track_id, {"license": validated["license"][:40]})
        return result

    def kids_list_music(self, tenant_id: str, *, episode_id: str = "") -> list[dict]:
        with self.connection() as c:
            if episode_id:
                return self._rows(c.execute("SELECT * FROM kids_music_tracks WHERE tenant_id=? AND episode_id=? ORDER BY created_at",
                                            (tenant_id, episode_id)).fetchall())
            return self._rows(c.execute("SELECT * FROM kids_music_tracks WHERE tenant_id=? ORDER BY created_at DESC LIMIT 200",
                                        (tenant_id,)).fetchall())
