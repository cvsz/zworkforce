# Kids Factory Roadmap

- COMPLETE (slice 1): domain, persistence, `/api/v1/kids/*`, `kids.*` MCP, Studio panel, FFmpeg sample render, approval-gated mock publishing, synthetic analytics, tests, docs.
- COMPLETE (slice 2): campaign planner, one-shot episode pipeline with durable agent-run checkpoints and idempotent resume, episode budget gate, MCP campaign/pipeline tools, deny-by-default MCP test.
- COMPLETE (slice 3): Shorts derivation (9:16 child episodes with provenance), voice profiles + consent-gated cloning + synthetic WAV previews, licensed music registry, per-brand quotas (max_episodes/max_cost_credits), `kids.derive_shorts` MCP.
- COMPLETE (slice 4): language-variant drafts (machine text flagged needs_review, never final), marketing suggestion drafts (labeled estimates, no engagement automation), analytics summary aggregated from persisted rows only, `kids.create_language_variant|suggest_marketing|get_analytics_summary` MCP.
- NEXT: human translation workflow for variants, voice/music/image/video real provider adapters with fallback, render queue/workers, calendar/scheduling, real YouTube OAuth adapter, backup/restore drills, load/soak baselines.
- NOT STARTED: real provider failover evidence, production hardening gates.
