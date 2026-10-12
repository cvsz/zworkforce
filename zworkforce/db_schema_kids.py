"""Kids Content Factory persistence schema (SQLite + PostgreSQL compatible)."""

from __future__ import annotations

KIDS_SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS kids_brands(
    tenant_id TEXT NOT NULL,
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    age_range TEXT NOT NULL DEFAULT '3-6',
    language TEXT NOT NULL DEFAULT 'en',
    art_style TEXT NOT NULL DEFAULT '',
    music_style TEXT NOT NULL DEFAULT '',
    voice_defaults_json TEXT NOT NULL DEFAULT '{}',
    content_policy_json TEXT NOT NULL DEFAULT '{}',
    publishing_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1,
    archived INTEGER NOT NULL DEFAULT 0,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id,id)
);
CREATE INDEX IF NOT EXISTS idx_kids_brands_tenant ON kids_brands(tenant_id,archived);

CREATE TABLE IF NOT EXISTS kids_brand_snapshots(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    brand_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kids_brand_snap ON kids_brand_snapshots(tenant_id,brand_id,version);

CREATE TABLE IF NOT EXISTS kids_channels(
    tenant_id TEXT NOT NULL,
    id TEXT NOT NULL,
    brand_id TEXT NOT NULL,
    name TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'youtube',
    external_account_ref TEXT NOT NULL DEFAULT '',
    publishing_settings_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id,id)
);

CREATE TABLE IF NOT EXISTS kids_characters(
    tenant_id TEXT NOT NULL,
    id TEXT NOT NULL,
    brand_id TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'friend',
    description TEXT NOT NULL DEFAULT '',
    species TEXT NOT NULL DEFAULT '',
    personality_json TEXT NOT NULL DEFAULT '[]',
    voice_profile_json TEXT NOT NULL DEFAULT '{}',
    palette_json TEXT NOT NULL DEFAULT '[]',
    costume_json TEXT NOT NULL DEFAULT '{}',
    negative_prompt TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    locked INTEGER NOT NULL DEFAULT 0,
    approval_state TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id,id)
);
CREATE INDEX IF NOT EXISTS idx_kids_chars_brand ON kids_characters(tenant_id,brand_id);

CREATE TABLE IF NOT EXISTS kids_character_versions(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    character_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(tenant_id,character_id,version)
);

CREATE TABLE IF NOT EXISTS kids_episodes(
    tenant_id TEXT NOT NULL,
    id TEXT NOT NULL,
    brand_id TEXT NOT NULL,
    channel_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    age_band TEXT NOT NULL DEFAULT 'preschool',
    language TEXT NOT NULL DEFAULT 'en',
    objectives_json TEXT NOT NULL DEFAULT '[]',
    vocabulary_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,
    budget_credits REAL NOT NULL DEFAULT 0,
    idempotency_key TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id,id)
);
CREATE INDEX IF NOT EXISTS idx_kids_episodes_brand ON kids_episodes(tenant_id,brand_id,status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_kids_episodes_idem ON kids_episodes(tenant_id,idempotency_key) WHERE idempotency_key <> '';

CREATE TABLE IF NOT EXISTS kids_scripts(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'nursery_rhyme',
    body_json TEXT NOT NULL DEFAULT '{}',
    provenance_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(tenant_id,episode_id,version)
);

CREATE TABLE IF NOT EXISTS kids_scenes(
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    id TEXT NOT NULL,
    ordering INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL NOT NULL DEFAULT 5,
    objective TEXT NOT NULL DEFAULT '',
    visual_prompt TEXT NOT NULL DEFAULT '',
    negative_prompt TEXT NOT NULL DEFAULT '',
    character_refs_json TEXT NOT NULL DEFAULT '[]',
    camera_json TEXT NOT NULL DEFAULT '{}',
    dialogue_json TEXT NOT NULL DEFAULT '{}',
    music_cues_json TEXT NOT NULL DEFAULT '[]',
    captions_json TEXT NOT NULL DEFAULT '[]',
    asset_ids_json TEXT NOT NULL DEFAULT '[]',
    checksum TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id,episode_id,id)
);
CREATE INDEX IF NOT EXISTS idx_kids_scenes_ep ON kids_scenes(tenant_id,episode_id,ordering);

CREATE TABLE IF NOT EXISTS kids_assets(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL DEFAULT '',
    scene_id TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'image',
    name TEXT NOT NULL DEFAULT '',
    storage_uri TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    provenance_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kids_assets_ep ON kids_assets(tenant_id,episode_id,scene_id);

CREATE TABLE IF NOT EXISTS kids_timelines(
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    tracks_json TEXT NOT NULL DEFAULT '{}',
    checksum TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id,episode_id,version)
);

CREATE TABLE IF NOT EXISTS kids_render_jobs(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    timeline_version INTEGER NOT NULL DEFAULT 1,
    preset TEXT NOT NULL DEFAULT 'landscape_1080p',
    status TEXT NOT NULL DEFAULT 'queued',
    output_uri TEXT NOT NULL DEFAULT '',
    output_sha256 TEXT NOT NULL DEFAULT '',
    thumbnail_uri TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    attempts INTEGER NOT NULL DEFAULT 0,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finished_at TEXT NULL
);
CREATE INDEX IF NOT EXISTS idx_kids_render_ep ON kids_render_jobs(tenant_id,episode_id,status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_kids_render_idem ON kids_render_jobs(tenant_id,idempotency_key) WHERE idempotency_key <> '';

CREATE TABLE IF NOT EXISTS kids_approvals(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    subject_type TEXT NOT NULL DEFAULT 'episode',
    subject_id TEXT NOT NULL DEFAULT '',
    subject_version INTEGER NOT NULL DEFAULT 1,
    state TEXT NOT NULL DEFAULT 'pending',
    reviewer TEXT NOT NULL DEFAULT '',
    comment TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    decided_at TEXT NULL
);
CREATE INDEX IF NOT EXISTS idx_kids_approvals_ep ON kids_approvals(tenant_id,episode_id,state);

CREATE TABLE IF NOT EXISTS kids_moderation(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    scene_id TEXT NOT NULL DEFAULT '',
    checklist_json TEXT NOT NULL DEFAULT '[]',
    passed INTEGER NOT NULL DEFAULT 0,
    findings_json TEXT NOT NULL DEFAULT '[]',
    reviewer TEXT NOT NULL DEFAULT 'quality-agent',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kids_publishing_jobs(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    render_job_id TEXT NOT NULL DEFAULT '',
    channel_id TEXT NOT NULL DEFAULT '',
    platform TEXT NOT NULL DEFAULT 'youtube_mock',
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    audience TEXT NOT NULL DEFAULT 'madeForKids',
    visibility TEXT NOT NULL DEFAULT 'private',
    status TEXT NOT NULL DEFAULT 'prepared',
    external_id TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    approval_id TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_kids_pub_idem ON kids_publishing_jobs(tenant_id,idempotency_key) WHERE idempotency_key <> '';
CREATE INDEX IF NOT EXISTS idx_kids_pub_ep ON kids_publishing_jobs(tenant_id,episode_id,status);

CREATE TABLE IF NOT EXISTS kids_analytics(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    channel_id TEXT NOT NULL DEFAULT '',
    episode_id TEXT NOT NULL DEFAULT '',
    period TEXT NOT NULL DEFAULT '7d',
    metrics_json TEXT NOT NULL DEFAULT '{}',
    synthetic INTEGER NOT NULL DEFAULT 1,
    captured_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kids_analytics_ch ON kids_analytics(tenant_id,channel_id,captured_at);

CREATE TABLE IF NOT EXISTS kids_usage(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT 'mock',
    capability TEXT NOT NULL DEFAULT 'llm',
    quantity REAL NOT NULL DEFAULT 0,
    cost_credits REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kids_usage_tenant ON kids_usage(tenant_id,created_at DESC);

CREATE TABLE IF NOT EXISTS kids_campaigns(
    tenant_id TEXT NOT NULL,
    id TEXT NOT NULL,
    brand_id TEXT NOT NULL,
    name TEXT NOT NULL,
    topic TEXT NOT NULL DEFAULT '',
    curriculum_json TEXT NOT NULL DEFAULT '{}',
    playlist_json TEXT NOT NULL DEFAULT '[]',
    calendar_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'planned',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id,id)
);
CREATE INDEX IF NOT EXISTS idx_kids_campaigns_brand ON kids_campaigns(tenant_id,brand_id,status);

CREATE TABLE IF NOT EXISTS kids_agent_runs(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    step TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'succeeded',
    input_json TEXT NOT NULL DEFAULT '{}',
    output_json TEXT NOT NULL DEFAULT '{}',
    attempts INTEGER NOT NULL DEFAULT 1,
    error TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_kids_agent_runs_idem ON kids_agent_runs(tenant_id,idempotency_key) WHERE idempotency_key <> '';
CREATE INDEX IF NOT EXISTS idx_kids_agent_runs_ep ON kids_agent_runs(tenant_id,episode_id,agent);

CREATE TABLE IF NOT EXISTS kids_derivations(
    tenant_id TEXT NOT NULL,
    parent_episode_id TEXT NOT NULL,
    child_episode_id TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'shorts',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id,child_episode_id)
);
CREATE INDEX IF NOT EXISTS idx_kids_deriv_parent ON kids_derivations(tenant_id,parent_episode_id);

CREATE TABLE IF NOT EXISTS kids_voice_profiles(
    tenant_id TEXT NOT NULL,
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'mock',
    model TEXT NOT NULL DEFAULT 'mock-tts-1',
    voice_id TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'en',
    style TEXT NOT NULL DEFAULT 'cheerful',
    speed REAL NOT NULL DEFAULT 1.0,
    rights_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id,id)
);

CREATE TABLE IF NOT EXISTS kids_music_tracks(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT 'mock',
    license TEXT NOT NULL DEFAULT '',
    provenance_json TEXT NOT NULL DEFAULT '{}',
    duration_seconds REAL NOT NULL DEFAULT 0,
    asset_id TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kids_music_ep ON kids_music_tracks(tenant_id,episode_id);
"""
