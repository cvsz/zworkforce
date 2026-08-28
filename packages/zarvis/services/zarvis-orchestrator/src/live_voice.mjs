/**
 * live_voice.mjs
 *
 * Realtime Audio Streaming & Bidirectional Voice Session Orchestrator
 * supporting Gemini Live API and OpenAI Realtime WebSocket protocols.
 */

import { randomUUID } from "node:crypto";
import { parseVadConfig, isSpeechDetected } from "../../voice-gateway/vad_config.mjs";

export const VOICE_PROVIDERS = Object.freeze({
  GEMINI_LIVE: "gemini-live",
  OPENAI_REALTIME: "openai-realtime",
  MOCK: "mock",
});

export const AUDIO_FORMATS = Object.freeze({
  PCM16_24KHZ: "audio/pcm;rate=24000",
  PCM16_16KHZ: "audio/pcm;rate=16000",
});

export class LiveVoiceSession {
  constructor(options = {}) {
    if (!options.tenantId) throw new Error("tenantId is required");
    if (!options.subjectId) throw new Error("subjectId is required");

    this.id = options.sessionId || randomUUID();
    this.tenantId = options.tenantId;
    this.subjectId = options.subjectId;
    this.provider = options.provider || VOICE_PROVIDERS.GEMINI_LIVE;
    this.model = options.model || (this.provider === VOICE_PROVIDERS.GEMINI_LIVE ? "gemini-3.1-flash-live-preview" : "gpt-4o-realtime-preview");
    this.systemPrompt = options.systemPrompt || "You are Z.A.R.V.I.S., a voice assistant for zWorkforce.";
    this.vad = parseVadConfig(options.vadConfig || {});
    this.audioFormat = options.audioFormat || AUDIO_FORMATS.PCM16_24KHZ;
    this.state = "idle";
    
    this.audioChunkCount = 0;
    this.totalAudioBytes = 0;
  }

  handleInboundAudio(chunk) {
    if (this.state === "closed") throw new Error("cannot send audio to a closed session");

    this.audioChunkCount += 1;
    this.totalAudioBytes += chunk.length;

    const speechDetected = isSpeechDetected(chunk, this.vad);
    let bargeInTriggered = false;

    if (speechDetected) {
      if (this.state === "speaking" && this.vad.bargeInEnabled) {
        this.state = "interrupted";
        bargeInTriggered = true;
      } else if (this.state === "idle") {
        this.state = "listening";
      }
    } else if (this.state === "interrupted") {
      this.state = "listening";
    }

    return {
      speechDetected,
      bargeInTriggered,
      chunkIndex: this.audioChunkCount,
    };
  }

  markSpeaking() {
    if (this.state !== "closed") {
      this.state = "speaking";
    }
  }

  markIdle() {
    if (this.state !== "closed") {
      this.state = "idle";
    }
  }

  close() {
    this.state = "closed";
  }

  getTelemetry() {
    return {
      sessionId: this.id,
      chunksProcessed: this.audioChunkCount,
      totalBytes: this.totalAudioBytes,
      state: this.state,
      provider: this.provider,
    };
  }
}
