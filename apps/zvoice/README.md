# ZVoice

`apps/zvoice` is the browser voice surface for the Z Platform realtime voice-agent stack.

It requests short-lived signed WebSocket tickets from `services/voice-gateway`, captures microphone audio with an AudioWorklet, sends 16 kHz PCM16 events using the OpenAI Realtime protocol, and stops queued playback when the owner interrupts.

## Z.A.R.V.I.S. owner mode

Set `ZVOICE_ZARVIS_MODE=true` to turn the existing realtime voice surface into the owner-only Z.A.R.V.I.S. bridge.

```text
Owner microphone
      |
      v
voice-gateway transcription
      |
      v
POST /api/zarvis/command
      |
      v
ZARVIS Orchestrator
      |
      v
speech-ready result -> browser TTS
```

In owner mode:

- the trusted edge must inject `x-zarvis-owner-id: 4076926` and `x-zarvis-edge-secret`;
- caller-supplied tenant and subject headers are discarded;
- voice-gateway tickets use `owner-4076926` / `github:4076926`;
- final voice transcripts are converted to `zarvis.command.requested.v1`;
- the browser never receives the edge secret, orchestrator token, voice service token, GitHub token, or provider key;
- duplicate `command_id` values replay the stored result without executing the tool again.

Required owner-mode configuration:

```bash
export ZVOICE_ZARVIS_MODE=true
export ZARVIS_EDGE_SHARED_SECRET='<at-least-32-random-bytes>'
export ZARVIS_ORCHESTRATOR_URL='http://127.0.0.1:8094'
export ZARVIS_ORCHESTRATOR_SERVICE_TOKEN='<independent-32-byte-token>'
export Z_PLATFORM_VOICE_GATEWAY_URL='http://127.0.0.1:8450'
export Z_PLATFORM_SERVICE_TOKEN='<voice-gateway-service-token>'
```

The public origin must remain behind the approved identity-aware edge. Do not expose the ZVoice origin directly to the Internet.

## Backward compatibility

When `ZVOICE_ZARVIS_MODE` is not enabled, the previous generic ZVoice identity behavior remains available. Production Z.A.R.V.I.S. deployments must enable owner mode and keep `ZVOICE_ALLOW_ANONYMOUS=false`.
