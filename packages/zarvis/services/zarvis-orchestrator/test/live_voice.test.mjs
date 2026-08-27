import assert from "node:assert/strict";
import test from "node:test";
import { LiveVoiceSession, VOICE_PROVIDERS, AUDIO_FORMATS } from "../src/live_voice.mjs";

test("LiveVoiceSession requires tenantId and subjectId", () => {
  assert.throws(() => new LiveVoiceSession({ tenantId: "", subjectId: "user-1" }), /tenantId is required/);
  assert.throws(() => new LiveVoiceSession({ tenantId: "tenant-1", subjectId: "" }), /subjectId is required/);
});

test("LiveVoiceSession initializes with default provider and model", () => {
  const session = new LiveVoiceSession({ tenantId: "tenant-1", subjectId: "user-1" });
  assert.equal(session.provider, VOICE_PROVIDERS.GEMINI_LIVE);
  assert.equal(session.model, "gemini-3.1-flash-live-preview");
  assert.equal(session.audioFormat, AUDIO_FORMATS.PCM16_24KHZ);
  assert.equal(session.state, "idle");
});

test("LiveVoiceSession handles inbound audio and detects barge-in", () => {
  const session = new LiveVoiceSession({
    tenantId: "tenant-1",
    subjectId: "user-1",
    vadConfig: { energyThreshold: 0.05, bargeInEnabled: true },
  });

  // 1. Silent audio chunk
  const silentChunk = new Uint8Array(480 * 2);
  const res1 = session.handleInboundAudio(silentChunk);
  assert.equal(res1.speechDetected, false);
  assert.equal(res1.bargeInTriggered, false);
  assert.equal(session.state, "idle");

  // 2. Mark session speaking (agent is responding)
  session.markSpeaking();
  assert.equal(session.state, "speaking");

  // 3. User speaks over agent (barge-in triggered)
  const voiceChunk = new Uint8Array(480 * 2);
  const view = new DataView(voiceChunk.buffer);
  for (let i = 0; i < 480; i++) view.setInt16(i * 2, 8000, true);

  const res2 = session.handleInboundAudio(voiceChunk);
  assert.equal(res2.speechDetected, true);
  assert.equal(res2.bargeInTriggered, true);
  assert.equal(session.state, "interrupted");

  // 4. Check telemetry
  const telem = session.getTelemetry();
  assert.equal(telem.chunksProcessed, 2);
  assert.equal(telem.totalBytes, 480 * 2 * 2);
});

test("LiveVoiceSession closes properly", () => {
  const session = new LiveVoiceSession({ tenantId: "tenant-1", subjectId: "user-1" });
  session.close();
  assert.equal(session.state, "closed");
  assert.throws(() => session.handleInboundAudio(new Uint8Array(10)), /cannot send audio to a closed session/);
});
