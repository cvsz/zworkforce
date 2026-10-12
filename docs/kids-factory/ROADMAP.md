# Kids Factory Roadmap

- COMPLETE (slice 1): domain, persistence, `/api/v1/kids/*`, `kids.*` MCP, Studio panel, FFmpeg sample render, approval-gated mock publishing, synthetic analytics, tests, docs.
- COMPLETE (slice 2): campaign planner, one-shot episode pipeline with durable agent-run checkpoints and idempotent resume, episode budget gate, MCP campaign/pipeline tools, deny-by-default MCP test.
- COMPLETE (slice 3): Shorts derivation (9:16 child episodes with provenance), voice profiles + consent-gated cloning + synthetic WAV previews, licensed music registry, per-brand quotas (max_episodes/max_cost_credits), `kids.derive_shorts` MCP.
- COMPLETE (slice 4): language-variant drafts (machine text flagged needs_review, never final), marketing suggestion drafts (labeled estimates, no engagement automation), analytics summary aggregated from persisted rows only, `kids.create_language_variant|suggest_marketing|get_analytics_summary` MCP.
- COMPLETE (slice 5): async render queue (`queue` + `tick` worker, bounded 3 attempts, dead-letter), shared `execute_render_job` for sync/async parity, human translation completion workflow for variant scenes, `kids.queue_render|tick_render_queue|submit_translation` MCP.
- NEXT: image/video real provider adapters with fallback, calendar/scheduling, real YouTube OAuth adapter, per-brand quota dashboards, backup/restore drills, load/soak baselines.
- NOT STARTED: real provider failover evidence, production hardening gates.
