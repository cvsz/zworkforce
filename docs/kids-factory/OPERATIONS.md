# Kids Factory Operations

- Endpoints: `/api/v1/kids/overview|brands|channels|campaigns|characters|episodes|assets|render-jobs|approvals|publishing|analytics|providers|usage|agent-runs|voices|music|derivations` plus `POST .../episodes/{id}/pipeline`, `POST .../episodes/{id}/shorts`, `POST .../episodes/{id}/variants`, `POST .../episodes/{id}/marketing`, `POST /api/v1/kids/voices/preview`, `GET /api/v1/kids/analytics/summary`.
- Writes need `operator` + `automation:write`; reads need `viewer` + `workforce:read`. Use `Idempotency-Key` on creates/renders/publishing.
- MCP: `kids.list_brands|list_campaigns|get_render_status|get_video_analytics` (read), `kids.create_campaign|create_episode_draft|generate_script|create_storyboard|request_character_review|generate_scene_assets|submit_render|run_episode_pipeline|derive_shorts|request_publish_approval` (mutating, deny-by-default).
- Quotas: brand `publishing.max_episodes` / `max_cost_credits` enforced on episode create and pipeline render; voice cloning needs `rights.consent_ref`; music needs `license`.
- Storage: `data/kids-renders/<tenant>/<job>.mp4`; artifacts content-addressed.
- Costs: `kids_usage` ledger per episode/provider/capability; overview exposes totals; episode `budget_credits` gates pipeline render.
- Recovery: failed renders can be retried (`.../retry` resets to queued); pipeline reruns resume from `kids_agent_runs` checkpoints; publishing resume reuses idempotency key.
- Rollback: additive tables only; drop `kids_*` tables to disable slice. No migration rewrites existing data.
