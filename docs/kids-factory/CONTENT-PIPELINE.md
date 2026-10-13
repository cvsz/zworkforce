# Kids Content Pipeline

`Campaign -> Brand -> Character (versioned) -> Episode -> Script (versioned) -> Storyboard (per-scene regen) -> Assets -> Timeline -> Render -> QA -> Approval -> Publishing (mock) -> Analytics (synthetic)`.

- Campaigns group episodes by topic/curriculum/playlist/calendar (`/api/v1/kids/campaigns`).
- Scene regen is per-scene (`POST .../scenes` with scene id); episode unaffected except that scene.
- Timeline versions are immutable with SHA checksum.
- Render is deterministic FFmpeg sample, labeled synthetic; real motion providers PENDING.
- Publishing is blocked until `kids.approvals/{id}/approve` sets state approved.
- One-shot orchestration: `POST /api/v1/kids/episodes/{id}/pipeline` or MCP `kids.run_episode_pipeline` runs research -> script -> storyboard -> assets -> timeline -> render -> qa -> approval_request with durable `kids_agent_runs` checkpoints. Reruns skip succeeded steps (no duplicate renders). Publishing itself is never auto-run.
- Budget gate: when `episode.budget_credits > 0`, the pipeline blocks render if the estimate exceeds budget (`KidsBudgetBlocked`, surfaced as 400 with a clear message). Usage accrues in `kids_usage`.
