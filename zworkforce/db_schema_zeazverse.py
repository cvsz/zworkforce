"""ZEAZVERSE Idol Studio persistence schema (SQLite + PostgreSQL compatible)."""

from __future__ import annotations

ZEAZVERSE_SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS zeazverse_channels(
    tenant_id TEXT NOT NULL,
    id TEXT NOT NULL,
    brand_name TEXT NOT NULL DEFAULT 'ZEAZVERSE',
    tagline TEXT NOT NULL DEFAULT 'Four Souls. One Universe.',
    preferred_handle TEXT NOT NULL DEFAULT '@ZEAZVERSE',
    actual_handle TEXT NOT NULL DEFAULT '',
    youtube_channel_id TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    primary_language TEXT NOT NULL DEFAULT 'en',
    default_visibility TEXT NOT NULL DEFAULT 'private',
    setup_status TEXT NOT NULL DEFAULT 'pending',
    setup_checklist_json TEXT NOT NULL DEFAULT '{}',
    branding_assets_json TEXT NOT NULL DEFAULT '{}',
    feature_eligibility_json TEXT NOT NULL DEFAULT '{}',
    publishing_settings_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id, id)
);
CREATE INDEX IF NOT EXISTS idx_zv_channels_tenant ON zeazverse_channels(tenant_id, setup_status);

CREATE TABLE IF NOT EXISTS zeazverse_characters(
    tenant_id TEXT NOT NULL,
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    archetype TEXT NOT NULL,
    age INTEGER NOT NULL DEFAULT 21,
    nationality TEXT NOT NULL DEFAULT 'Thai',
    appearance_json TEXT NOT NULL DEFAULT '{}',
    personality_json TEXT NOT NULL DEFAULT '{}',
    story_themes_json TEXT NOT NULL DEFAULT '[]',
    dialogue_style_json TEXT NOT NULL DEFAULT '{}',
    voice_profile_json TEXT NOT NULL DEFAULT '{}',
    costume_config_json TEXT NOT NULL DEFAULT '{}',
    accessories_json TEXT NOT NULL DEFAULT '[]',
    consistency_rules_json TEXT NOT NULL DEFAULT '{}',
    reference_turnaround_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'canonical',
    version INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id, id)
);
CREATE INDEX IF NOT EXISTS idx_zv_chars_tenant ON zeazverse_characters(tenant_id, status);

CREATE TABLE IF NOT EXISTS zeazverse_character_versions(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    character_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(tenant_id, character_id, version)
);

CREATE TABLE IF NOT EXISTS zeazverse_series(
    tenant_id TEXT NOT NULL,
    id TEXT NOT NULL,
    title TEXT NOT NULL,
    synopsis TEXT NOT NULL DEFAULT '',
    content_class TEXT NOT NULL DEFAULT 'Cyberpunk Stories',
    target_format TEXT NOT NULL DEFAULT '9:16',
    status TEXT NOT NULL DEFAULT 'active',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id, id)
);

CREATE TABLE IF NOT EXISTS zeazverse_episodes(
    tenant_id TEXT NOT NULL,
    id TEXT NOT NULL,
    series_id TEXT NOT NULL,
    channel_id TEXT NOT NULL DEFAULT '',
    story_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    content_class TEXT NOT NULL DEFAULT 'Cyberpunk Stories',
    canvas_format TEXT NOT NULL DEFAULT '1080x1920',
    fps INTEGER NOT NULL DEFAULT 30,
    target_duration_seconds REAL NOT NULL DEFAULT 30.0,
    status TEXT NOT NULL DEFAULT 'IDEA',
    story_concept_json TEXT NOT NULL DEFAULT '{}',
    characters_json TEXT NOT NULL DEFAULT '[]',
    script_json TEXT NOT NULL DEFAULT '{}',
    storyboard_json TEXT NOT NULL DEFAULT '{}',
    asset_manifest_json TEXT NOT NULL DEFAULT '{}',
    render_manifest_json TEXT NOT NULL DEFAULT '{}',
    audio_plan_json TEXT NOT NULL DEFAULT '{}',
    editing_plan_json TEXT NOT NULL DEFAULT '{}',
    qa_report_json TEXT NOT NULL DEFAULT '{}',
    publishing_metadata_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1,
    idempotency_key TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id, id)
);
CREATE INDEX IF NOT EXISTS idx_zv_episodes_series ON zeazverse_episodes(tenant_id, series_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_zv_episodes_idem ON zeazverse_episodes(tenant_id, idempotency_key) WHERE idempotency_key <> '';

CREATE TABLE IF NOT EXISTS zeazverse_scenes(
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    id TEXT NOT NULL,
    ordering INTEGER NOT NULL DEFAULT 0,
    time_start_seconds REAL NOT NULL DEFAULT 0.0,
    time_end_seconds REAL NOT NULL DEFAULT 5.0,
    characters_json TEXT NOT NULL DEFAULT '[]',
    character_ref_ids_json TEXT NOT NULL DEFAULT '[]',
    environment TEXT NOT NULL DEFAULT '',
    subject_action TEXT NOT NULL DEFAULT '',
    camera_framing TEXT NOT NULL DEFAULT '',
    camera_movement TEXT NOT NULL DEFAULT '',
    lighting TEXT NOT NULL DEFAULT '',
    physical_interaction TEXT NOT NULL DEFAULT '',
    dialogue_json TEXT NOT NULL DEFAULT '{}',
    audio_json TEXT NOT NULL DEFAULT '{}',
    positive_prompt TEXT NOT NULL DEFAULT '',
    negative_prompt TEXT NOT NULL DEFAULT '',
    first_frame_continuity TEXT NOT NULL DEFAULT '',
    last_frame_continuity TEXT NOT NULL DEFAULT '',
    generation_model TEXT NOT NULL DEFAULT 'mock-video-v1',
    model_settings_json TEXT NOT NULL DEFAULT '{}',
    expected_output TEXT NOT NULL DEFAULT '',
    qa_checks_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending',
    output_artifact_uri TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id, episode_id, id)
);
CREATE INDEX IF NOT EXISTS idx_zv_scenes_order ON zeazverse_scenes(tenant_id, episode_id, ordering);

CREATE TABLE IF NOT EXISTS zeazverse_generation_jobs(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    scene_id TEXT NOT NULL DEFAULT '',
    capability TEXT NOT NULL DEFAULT 'video',
    provider TEXT NOT NULL DEFAULT 'mock',
    model TEXT NOT NULL DEFAULT '',
    parameters_json TEXT NOT NULL DEFAULT '{}',
    prompt TEXT NOT NULL DEFAULT '',
    negative_prompt TEXT NOT NULL DEFAULT '',
    reference_images_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'queued',
    external_job_id TEXT NOT NULL DEFAULT '',
    output_artifacts_json TEXT NOT NULL DEFAULT '[]',
    cost_credits REAL NOT NULL DEFAULT 0.0,
    error TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    attempts INTEGER NOT NULL DEFAULT 0,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finished_at TEXT NULL
);
CREATE INDEX IF NOT EXISTS idx_zv_gen_jobs ON zeazverse_generation_jobs(tenant_id, episode_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_zv_gen_idem ON zeazverse_generation_jobs(tenant_id, idempotency_key) WHERE idempotency_key <> '';

CREATE TABLE IF NOT EXISTS zeazverse_render_jobs(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    format TEXT NOT NULL DEFAULT '1080x1920',
    fps INTEGER NOT NULL DEFAULT 30,
    codec TEXT NOT NULL DEFAULT 'h264',
    status TEXT NOT NULL DEFAULT 'queued',
    output_video_uri TEXT NOT NULL DEFAULT '',
    output_sha256 TEXT NOT NULL DEFAULT '',
    subtitles_vtt_uri TEXT NOT NULL DEFAULT '',
    thumbnail_uri TEXT NOT NULL DEFAULT '',
    duration_seconds REAL NOT NULL DEFAULT 0.0,
    validation_status TEXT NOT NULL DEFAULT 'unverified',
    validation_report_json TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finished_at TEXT NULL
);
CREATE INDEX IF NOT EXISTS idx_zv_render_jobs ON zeazverse_render_jobs(tenant_id, episode_id, status);

CREATE TABLE IF NOT EXISTS zeazverse_qa_reports(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    reviewer_agent TEXT NOT NULL DEFAULT 'Continuity QA',
    passed INTEGER NOT NULL DEFAULT 0,
    identity_consistency_score REAL NOT NULL DEFAULT 1.0,
    anatomy_score REAL NOT NULL DEFAULT 1.0,
    temporal_continuity_score REAL NOT NULL DEFAULT 1.0,
    policy_compliance_passed INTEGER NOT NULL DEFAULT 1,
    defects_json TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_zv_qa_reports ON zeazverse_qa_reports(tenant_id, episode_id, passed);

CREATE TABLE IF NOT EXISTS zeazverse_approval_requests(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    action TEXT NOT NULL DEFAULT 'publish',
    target_visibility TEXT NOT NULL DEFAULT 'private',
    expected_etag TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'pending',
    reviewer TEXT NOT NULL DEFAULT '',
    comment TEXT NOT NULL DEFAULT '',
    decided_at TEXT NULL,
    consumed_at TEXT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_zv_approvals ON zeazverse_approval_requests(tenant_id, episode_id, state);

CREATE TABLE IF NOT EXISTS zeazverse_publications(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'youtube',
    youtube_video_id TEXT NOT NULL DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'private',
    made_for_kids INTEGER NOT NULL DEFAULT 0,
    contains_synthetic_media INTEGER NOT NULL DEFAULT 1,
    approval_request_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'prepared',
    upload_etag TEXT NOT NULL DEFAULT '',
    upload_metadata_json TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_zv_pub_idem ON zeazverse_publications(tenant_id, idempotency_key) WHERE idempotency_key <> '';
CREATE INDEX IF NOT EXISTS idx_zv_pub_ep ON zeazverse_publications(tenant_id, episode_id, status);

CREATE TABLE IF NOT EXISTS zeazverse_analytics_snapshots(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    episode_id TEXT NOT NULL DEFAULT '',
    period TEXT NOT NULL DEFAULT '7d',
    metrics_json TEXT NOT NULL DEFAULT '{}',
    synthetic INTEGER NOT NULL DEFAULT 1,
    captured_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_zv_analytics ON zeazverse_analytics_snapshots(tenant_id, channel_id, captured_at);

CREATE TABLE IF NOT EXISTS zeazverse_growth_experiments(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    title TEXT NOT NULL,
    hypothesis TEXT NOT NULL DEFAULT '',
    variant_a_json TEXT NOT NULL DEFAULT '{}',
    variant_b_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft',
    winner TEXT NOT NULL DEFAULT '',
    results_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS zeazverse_audit_events(
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_zv_audit ON zeazverse_audit_events(tenant_id, event_type, created_at DESC);
"""
