"""Database persistence mixin for Universal Content Styles and Creative Briefs."""

from __future__ import annotations

from typing import Any

from .content_styles_data import CONTENT_STYLE_PRESETS
from .db_base import json_dumps, json_loads, utcnow


class ContentStylesMixin:
    """Methods for persisting and querying the 128 Content Style Presets."""

    def seed_content_style_presets(self, tenant_id: str) -> int:
        now = utcnow()
        count = 0
        with self.connection() as c:
            for s in CONTENT_STYLE_PRESETS:
                if True:
                    inserted = c.execute(
                        """INSERT INTO content_style_presets (
                            tenant_id, style_id, category, display_name, description,
                            supported_content_types_json, audience_profile, age_rating,
                            default_aspect_ratio, target_duration, visual_style,
                            animation_style, camera_language, lighting_profile,
                            color_grading, editing_pace, narration_style, music_profile,
                            subtitle_style, thumbnail_style, safety_policy,
                            publishing_targets_json, provider_capabilities_json,
                            estimated_cost_class, prompt_template_version, active,
                            version, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?) ON CONFLICT(tenant_id, style_id) DO NOTHING""",
                        (
                            tenant_id,
                            s["style_id"],
                            s["category"],
                            s["display_name"],
                            s["description"],
                            json_dumps(s["supported_content_types"]),
                            s["audience_profile"],
                            s["age_rating"],
                            s["default_aspect_ratio"],
                            s["target_duration"],
                            s["visual_style"],
                            s["animation_style"],
                            s["camera_language"],
                            s["lighting_profile"],
                            s["color_grading"],
                            s["editing_pace"],
                            s["narration_style"],
                            s["music_profile"],
                            s["subtitle_style"],
                            s["thumbnail_style"],
                            s["safety_policy"],
                            json_dumps(s["publishing_targets"]),
                            json_dumps(s["provider_capabilities"]),
                            s["estimated_cost_class"],
                            s["prompt_template_version"],
                            s["active"],
                            now,
                            now,
                        ),
                    )
                    count += max(0, inserted.rowcount)
        return count

    def list_content_style_presets(
        self, tenant_id: str, category: str | None = None, active_only: bool = True
    ) -> list[dict[str, Any]]:
        self.seed_content_style_presets(tenant_id)
        with self.connection() as c:
            query = "SELECT * FROM content_style_presets WHERE tenant_id=?"
            params: list[Any] = [tenant_id]
            if category:
                query += " AND category=?"
                params.append(category)
            if active_only:
                query += " AND active=1"
            query += " ORDER BY category ASC, display_name ASC"
            rows = c.execute(query, tuple(params)).fetchall()
            result = []
            for r in rows:
                item = dict(r)
                item["supported_content_types"] = json_loads(item.get("supported_content_types_json"), [])
                item["publishing_targets"] = json_loads(item.get("publishing_targets_json"), [])
                item["provider_capabilities"] = json_loads(item.get("provider_capabilities_json"), [])
                result.append(item)
            return result

    def get_content_style_preset(self, tenant_id: str, style_id: str) -> dict[str, Any] | None:
        self.seed_content_style_presets(tenant_id)
        with self.connection() as c:
            row = c.execute(
                "SELECT * FROM content_style_presets WHERE tenant_id=? AND style_id=?", (tenant_id, style_id)
            ).fetchone()
            if not row:
                return None
            item = dict(row)
            item["supported_content_types"] = json_loads(item.get("supported_content_types_json"), [])
            item["publishing_targets"] = json_loads(item.get("publishing_targets_json"), [])
            item["provider_capabilities"] = json_loads(item.get("provider_capabilities_json"), [])
            return item

    def create_creative_brief(
        self, tenant_id: str, brief_id: str, style_id: str, title: str, objective: str = "", created_by: str = "system"
    ) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as c:
            c.execute(
                """INSERT INTO universal_creative_briefs (
                    tenant_id, id, style_id, title, objective, status, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?)""",
                (tenant_id, brief_id, style_id, title, objective, created_by, now, now),
            )
            row = c.execute(
                "SELECT * FROM universal_creative_briefs WHERE tenant_id=? AND id=?", (tenant_id, brief_id)
            ).fetchone()
            return dict(row)
