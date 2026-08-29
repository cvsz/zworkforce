# Voice Agent Operations Runbook

## Prerequisites

- Docker Engine and Docker Compose.
- A microphone-capable browser served from `localhost` or HTTPS.
- Sufficient disk for model caches.
- NVIDIA Container Toolkit only for the vLLM profile or a CUDA-enabled custom voice-agent image.

## Configure

```bash
cp configs/voice-agent.env.example .env.voice
openssl rand -hex 32
```

Set the generated values as `Z_PLATFORM_SERVICE_TOKEN` and `VOICE_TICKET_SECRET` in the environment file. Keep `.env.voice` outside version control.

## Ollama path

```bash
docker compose --env-file .env.voice   -f compose.yml -f compose.voice.yml   --profile voice-ollama up -d --build

docker compose --env-file .env.voice   -f compose.yml -f compose.voice.yml   exec ollama ollama pull qwen3:8b
```

## llama.cpp path

Place a GGUF model at `./models/llama.cpp/model.gguf`, select the llama.cpp block in `.env.voice`, then run:

```bash
docker compose --env-file .env.voice   -f compose.yml -f compose.voice.yml   --profile voice-llamacpp up -d --build
```

## vLLM path

Select the vLLM block in `.env.voice`, verify the NVIDIA runtime, then run:

```bash
docker compose --env-file .env.voice   -f compose.yml -f compose.voice.yml   --profile voice-vllm up -d --build
```

## Validate

```bash
set -a
source .env.voice
set +a
bash scripts/voice-agent-smoke.sh
```

Open `http://127.0.0.1:3022`, allow microphone access, and use the Voice panel.

Validate all of the following:

- microphone permission and capture;
- final transcription quality for the target language;
- response audio playback;
- barge-in while the assistant is speaking;
- ticket expiry and replay rejection;
- model/provider failure behavior;
- browser reconnect behavior;
- CPU, RAM, VRAM, and disk-cache growth.

## Observability

- `GET /health` on port 8450 reports active and maximum sessions.
- `GET /metrics` exposes Prometheus text metrics.
- Structured gateway logs include ticket/session lifecycle events but never ticket values or audio.
- Add the voice gateway metrics endpoint to the platform Prometheus scrape configuration before staging.

## Failure modes

| Symptom | Likely cause | Action |
|---|---|---|
| Voice ticket returns 401 | Service token mismatch | Verify the same `Z_PLATFORM_SERVICE_TOKEN` reaches ZVoice and voice-gateway |
| WebSocket returns 401 | Ticket expired, replayed, or malformed | Request a new session; inspect gateway rejection logs |
| Voice agent unhealthy for several minutes | Initial model download or insufficient RAM/disk | Inspect `voice-agent` logs and model-cache volume |
| No transcription | Wrong STT model/language or no microphone frames | Confirm browser permission and test a smaller Whisper model |
| LLM 503 from AI Gateway | Provider key pool not seeded | Verify `AI_PROVIDER_KEYS_JSON`, `AI_DEFAULT_PROVIDER`, and upstream URL |
| High response latency | CPU-only STT/TTS/LLM or oversized model | Move one stage to GPU, reduce model size, and benchmark stages separately |
| Audio overlaps after interruption | Client did not stop queued sources | Confirm `speech_started` events reach the browser and clear playback queue |

## Production gate

Do not expose the port publicly until:

- Cloudflare/OIDC identity supplies stable tenant and subject headers;
- `VOICE_ALLOW_ANONYMOUS=false`;
- TLS terminates at a reviewed reverse proxy;
- ticket replay state is moved to Redis for multi-replica operation;
- rate limits and concurrency limits match hardware capacity;
- privacy notice, retention policy, and consent flow cover microphone/audio processing;
- load, interruption, recovery, and data-boundary tests pass;
- a human release owner signs off.
