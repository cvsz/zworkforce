# Provider Adapters

Slice defaults to mock/offline:

- LLM/image/video/TTS/music: `mock` (deterministic fixtures, cost recorded, no spend).
- Render: local FFmpeg (`landscape_1080p`, `portrait_1080x1920`), bounded subprocess, `shell=False`, timeouts.
- Publishing: `youtube_mock` (deterministic external id from idempotency key, no network).
- Storage: existing artifact store (content-addressed SHA-256).

Real providers (OpenAI, Gemini, ElevenLabs, Replicate, Runway) are PENDING EXTERNAL EVIDENCE: credentials, routing, failover, cost ceilings must be recorded before use. Never silently swap fidelity tiers.
