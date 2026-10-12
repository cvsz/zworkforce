# Video Rendering

- Timeline tracks: video, overlay, voice, music, sfx, captions, branding.
- FFmpeg assembles deterministic color+ ducking tone per scene, then concat, H.264/AAC.
- Output verified by SHA-256; artifact registered via `app.artifacts` when available.
- CPU-only deployments support scripting, planning, assembly, control plane.
- Concurrency: synchronous per-request in slice; queue/worker fan-out is roadmap.
- Mock image sequences are labeled synthetic, never presented as cinematic AI animation.

- Async queue: `POST /api/v1/kids/render-jobs/queue` stages a job as `queued`; `POST /api/v1/kids/render-jobs/tick` executes the oldest queued job once via the same `execute_render_job` path as synchronous renders. Attempts are bounded at 3, then the job is marked `failed` (dead-letter) with the error preserved.
