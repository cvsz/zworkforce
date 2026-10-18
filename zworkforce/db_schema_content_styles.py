"""Database persistence schema for Universal Content Factory and Style Registry."""

from __future__ import annotations

UNIVERSAL_CONTENT_SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS content_style_presets(
    tenant_id TEXT NOT NULL,
    style_id TEXT NOT NULL,
    category TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    supported_content_types_json TEXT NOT NULL DEFAULT '[]',
    audience_profile TEXT NOT NULL DEFAULT 'general',
    age_rating TEXT NOT NULL DEFAULT 'general',
    default_aspect_ratio TEXT NOT NULL DEFAULT '16:9',
    target_duration INTEGER NOT NULL DEFAULT 60,
    visual_style TEXT NOT NULL DEFAULT '',
    animation_style TEXT NOT NULL DEFAULT '',
    camera_language TEXT NOT NULL DEFAULT '',
    lighting_profile TEXT NOT NULL DEFAULT '',
    color_grading TEXT NOT NULL DEFAULT '',
    editing_pace TEXT NOT NULL DEFAULT '',
    narration_style TEXT NOT NULL DEFAULT '',
    music_profile TEXT NOT NULL DEFAULT '',
    subtitle_style TEXT NOT NULL DEFAULT '',
    thumbnail_style TEXT NOT NULL DEFAULT '',
    safety_policy TEXT NOT NULL DEFAULT 'standard',
    publishing_targets_json TEXT NOT NULL DEFAULT '[]',
    provider_capabilities_json TEXT NOT NULL DEFAULT '[]',
    estimated_cost_class TEXT NOT NULL DEFAULT 'standard',
    prompt_template_version INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id, style_id)
);
CREATE INDEX IF NOT EXISTS idx_content_styles_cat ON content_style_presets(tenant_id, category, active);

CREATE TABLE IF NOT EXISTS universal_creative_briefs(
    tenant_id TEXT NOT NULL,
    id TEXT NOT NULL,
    brand_id TEXT NOT NULL DEFAULT '',
    style_id TEXT NOT NULL,
    title TEXT NOT NULL,
    objective TEXT NOT NULL DEFAULT '',
    target_audience TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'en',
    topic_keywords_json TEXT NOT NULL DEFAULT '[]',
    requirements_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id, id)
);
CREATE INDEX IF NOT EXISTS idx_creative_briefs_tenant ON universal_creative_briefs(tenant_id, status);
"""
