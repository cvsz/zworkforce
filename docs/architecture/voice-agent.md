# Local Realtime Voice Agent Architecture

## Status

Initial production-oriented vertical slice. External traffic remains disabled by default; published ports bind to loopback.

## Goals

- Real-time speech conversation with interruption handling.
- Local VAD, STT, and TTS, with a local or hosted OpenAI-compatible LLM.
- Keep model/provider credentials and platform service tokens out of the browser.
- Preserve `apps -> services -> packages/contracts` dependency direction.
- Route all LLM traffic through `services/ai-gateway`.
- Support Ollama, llama.cpp, and vLLM without coupling the speech pipeline to one runtime.

## Components

```text
Browser / ZVoice
  │ POST /api/voice/session
  ▼
apps/zvoice (server-side)
  │ service-token authenticated ticket request
  ▼
services/voice-gateway :8450
  │ signed one-time ticket + WebSocket tunnel
  ▼
services/voice-agent :8765 (internal only)
  │ VAD -> STT -> LLM -> TTS
  │             │
  │             ▼
  │      services/ai-gateway :8400
  │             │
  │             ├─ Ollama :11434/v1
  │             ├─ llama.cpp :8080/v1
  │             ├─ vLLM :8000/v1
  │             └─ hosted OpenAI-compatible provider
  ▼
PCM audio events returned to the browser
```

## Security boundary

1. `zvoice` holds `Z_PLATFORM_SERVICE_TOKEN` server-side.
2. The browser requests a voice session from `zvoice`; it never receives the service token.
3. `voice-gateway` issues a signed ticket with a 10–300 second lifetime.
4. The browser sends the ticket through `Sec-WebSocket-Protocol` as `zticket.<ticket>`.
5. The gateway validates the HMAC, expiry, tenant, subject, and nonce, then consumes the nonce.
6. The speech runtime has no published host port and only accepts traffic from the internal Compose network.
7. The speech runtime calls `ai-gateway`; provider credentials remain in gateway/secret storage.

The first slice keeps consumed ticket nonces in memory and therefore runs `voice-gateway` as a single replica. Before horizontal scaling, move nonce consumption and active-session admission to Redis using an atomic `SET NX EX` operation.

## Realtime protocol

The speech runtime exposes the OpenAI Realtime-compatible `/v1/realtime` WebSocket endpoint. The ZVoice client sends 16 kHz mono PCM16 audio with `input_audio_buffer.append` and handles:

- `input_audio_buffer.speech_started`
- `input_audio_buffer.speech_stopped`
- live/final transcription events
- `response.output_audio.delta`
- `response.output_audio_transcript.done`
- `response.done`
- `error`

New user speech stops queued playback immediately, enabling barge-in behavior.

## Model/runtime profiles

| Profile | Best fit | AI Gateway upstream |
|---|---|---|
| `voice-ollama` | Simple local setup, CPU/GPU, easy model management | `http://ollama:11434/v1` |
| `voice-llamacpp` | GGUF models, CPU/Metal/CUDA/Vulkan, tight memory control | `http://llama-cpp:8080/v1` |
| `voice-vllm` | NVIDIA GPU throughput, continuous batching, multi-session workloads | `http://vllm:8000/v1` |

Only one LLM profile should be selected per local deployment unless a separate provider router is configured.

## Capacity model

- `VOICE_NUM_PIPELINES` controls concurrent Hugging Face realtime pipelines. Each pipeline loads its own conversation handlers and can materially increase VRAM/RAM.
- `VOICE_MAX_SESSIONS` is enforced at `voice-gateway`.
- Start with one pipeline/session on CPU and two only after measuring memory and latency.
- The browser sends approximately 32 KB/s of uncompressed 16 kHz mono PCM16 before WebSocket framing.

## Target SLOs

These are engineering targets, not guarantees:

- Ticket issuance p95: under 100 ms on the local network.
- VAD end-of-turn decision: 300–600 ms after speech ends.
- First partial transcript: under 700 ms where the STT backend supports streaming.
- First synthesized audio: under 1.5 seconds after end-of-turn on a suitable GPU.
- Session setup success: at least 99.5% in a healthy single-node deployment.

Record actual values before enabling external production traffic.
