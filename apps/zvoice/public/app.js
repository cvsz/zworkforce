const startButton = document.querySelector("#start");
const muteButton = document.querySelector("#mute");
const stopButton = document.querySelector("#stop");
const cancelButton = document.querySelector("#cancel");
const clearButton = document.querySelector("#clear");
const stateBadge = document.querySelector("#voice-state");
const emptyState = document.querySelector("#empty");
const voiceStatus = document.querySelector("#status");
const voiceTranscript = document.querySelector("#transcript");
const systemPrompt = document.querySelector("#instructions");
const modelField = document.querySelector("#model");

const PIPELINE_SAMPLE_RATE = 16000;
let socket = null;
let audioContext = null;
let mediaStream = null;
let captureNode = null;
let muted = false;
let sessionConfigured = false;
let playhead = 0;
let activeSources = new Set();
let zarvisMode = false;
let zarvisSessionId = null;
let commandInFlight = false;

function setVoiceStatus(message, tone = "idle") {
  voiceStatus.textContent = message;
  voiceStatus.dataset.tone = tone;
  stateBadge.textContent = message;
  stateBadge.dataset.tone = tone;
}

function appendTranscript(role, text) {
  if (!text) return;
  const item = document.createElement("li");
  const label = document.createElement("strong");
  label.textContent = role === "assistant" ? "ZARVIS: " : "You: ";
  item.append(label, document.createTextNode(text));
  item.dataset.role = role;
  voiceTranscript.append(item);
  emptyState.hidden = true;
  voiceTranscript.scrollTop = voiceTranscript.scrollHeight;
}

function bytesToBase64(bytes) {
  let binary = "";
  const chunkSize = 0x8000;
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }
  return btoa(binary);
}

function base64ToBytes(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes;
}

function resampleToPcm16(input, inputRate, outputRate) {
  if (!input.length) return new Uint8Array();
  const ratio = inputRate / outputRate;
  const outputLength = Math.max(1, Math.floor(input.length / ratio));
  const output = new ArrayBuffer(outputLength * 2);
  const view = new DataView(output);

  for (let index = 0; index < outputLength; index += 1) {
    const position = index * ratio;
    const leftIndex = Math.floor(position);
    const rightIndex = Math.min(input.length - 1, leftIndex + 1);
    const fraction = position - leftIndex;
    const sample = input[leftIndex] * (1 - fraction) + input[rightIndex] * fraction;
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(index * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  }
  return new Uint8Array(output);
}

function pcm16ToFloat32(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const samples = new Float32Array(Math.floor(bytes.byteLength / 2));
  for (let index = 0; index < samples.length; index += 1) {
    const value = view.getInt16(index * 2, true);
    samples[index] = value < 0 ? value / 0x8000 : value / 0x7fff;
  }
  return samples;
}

function stopPlayback() {
  for (const source of activeSources) {
    try {
      source.stop();
    } catch {
      // The source may already have ended.
    }
  }
  activeSources = new Set();
  playhead = audioContext?.currentTime || 0;
}

function queueAudio(base64Audio) {
  if (!audioContext || !base64Audio || zarvisMode) return;
  const samples = pcm16ToFloat32(base64ToBytes(base64Audio));
  if (!samples.length) return;
  const buffer = audioContext.createBuffer(1, samples.length, PIPELINE_SAMPLE_RATE);
  buffer.copyToChannel(samples, 0);

  const source = audioContext.createBufferSource();
  source.buffer = buffer;
  source.connect(audioContext.destination);
  const startAt = Math.max(audioContext.currentTime + 0.02, playhead);
  source.start(startAt);
  playhead = startAt + buffer.duration;
  activeSources.add(source);
  source.addEventListener("ended", () => activeSources.delete(source), { once: true });
}

function speakWithBrowser(text, locale) {
  if (!("speechSynthesis" in globalThis) || !text) return;
  globalThis.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = locale || "th-TH";
  globalThis.speechSynthesis.speak(utterance);
}

function sendSessionUpdate(instructions) {
  const effectiveInstructions = zarvisMode
    ? "Transcribe the owner's speech accurately. Do not answer the user; the ZARVIS orchestrator will produce the response."
    : instructions;
  socket.send(JSON.stringify({
    type: "session.update",
    session: {
      type: "realtime",
      instructions: effectiveInstructions,
    },
  }));
  sessionConfigured = true;
}

async function dispatchZarvisTranscript(transcript) {
  if (!zarvisMode || !zarvisSessionId || !transcript || commandInFlight) return;
  commandInFlight = true;
  setVoiceStatus("ZARVIS is reasoning…", "busy");
  try {
    const response = await fetch("/api/zarvis/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        command_id: globalThis.crypto?.randomUUID?.() || `command-${Date.now()}`,
        session_id: zarvisSessionId,
        transcript,
        locale: "th-TH",
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload?.error?.message || "ZARVIS command failed");
    }
    appendTranscript("assistant", payload.speech?.text || "Command completed");
    speakWithBrowser(payload.speech?.text, payload.speech?.locale);
    setVoiceStatus(payload.replayed ? "Replayed safely" : "Connected — speak naturally", "ready");
  } catch (error) {
    setVoiceStatus(error instanceof Error ? error.message : "ZARVIS command failed", "error");
  } finally {
    commandInFlight = false;
  }
}

function handleRealtimeEvent(event) {
  let payload;
  try {
    payload = JSON.parse(event.data);
  } catch {
    return;
  }

  switch (payload.type) {
    case "session.created":
      sendSessionUpdate(systemPrompt?.value || "You are a concise, helpful voice assistant.");
      setVoiceStatus("Connected — speak naturally", "ready");
      break;
    case "input_audio_buffer.speech_started":
      stopPlayback();
      setVoiceStatus("Listening…", "busy");
      break;
    case "input_audio_buffer.speech_stopped":
      setVoiceStatus("Transcribing…", "busy");
      break;
    case "conversation.item.input_audio_transcription.completed": {
      const transcript = payload.transcript || payload.text || "";
      appendTranscript("user", transcript);
      if (zarvisMode) {
        if (socket?.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: "response.cancel" }));
        }
        void dispatchZarvisTranscript(transcript);
      }
      break;
    }
    case "response.audio.delta":
    case "response.output_audio.delta":
      queueAudio(payload.delta);
      if (!zarvisMode) setVoiceStatus("Speaking…", "busy");
      break;
    case "response.audio_transcript.done":
    case "response.output_audio_transcript.done":
      if (!zarvisMode) appendTranscript("assistant", payload.transcript || payload.text || "");
      break;
    case "response.done":
      if (!zarvisMode && !commandInFlight) setVoiceStatus("Connected — speak naturally", "ready");
      break;
    case "error":
      if (!zarvisMode) setVoiceStatus(payload.error?.message || "Voice session error", "error");
      break;
    default:
      break;
  }
}

async function requestVoiceSession() {
  const response = await fetch("/api/voice/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      instructions: systemPrompt?.value || "You are a concise, helpful voice assistant.",
      session_id: zarvisSessionId || undefined,
    }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error?.message || payload.error || "Unable to start voice session");
  }
  return payload;
}

async function startCapture() {
  audioContext = new AudioContext({ latencyHint: "interactive" });
  await audioContext.audioWorklet.addModule("/voice-worklet.js");
  mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      channelCount: 1,
    },
  });

  const source = audioContext.createMediaStreamSource(mediaStream);
  captureNode = new AudioWorkletNode(audioContext, "z-platform-voice-capture");
  captureNode.port.onmessage = ({ data }) => {
    if (muted || !sessionConfigured || socket?.readyState !== WebSocket.OPEN) return;
    const bytes = resampleToPcm16(data, audioContext.sampleRate, PIPELINE_SAMPLE_RATE);
    if (!bytes.length) return;
    socket.send(JSON.stringify({
      type: "input_audio_buffer.append",
      audio: bytesToBase64(bytes),
    }));
  };
  source.connect(captureNode);
  const silent = audioContext.createGain();
  silent.gain.value = 0;
  captureNode.connect(silent).connect(audioContext.destination);
}

async function startVoice() {
  startButton.disabled = true;
  sessionConfigured = false;
  setVoiceStatus("Requesting secure voice ticket…", "busy");
  try {
    const session = await requestVoiceSession();
    zarvisMode = Boolean(session.zarvis_mode);
    zarvisSessionId = session.zarvis_session_id || zarvisSessionId;
    if (modelField) modelField.value = session.model || modelField.value;
    await startCapture();

    socket = new WebSocket(session.websocket_url, [`zticket.${session.ticket}`]);
    socket.addEventListener("message", handleRealtimeEvent);
    socket.addEventListener("open", () => {
      muteButton.disabled = false;
      cancelButton.disabled = false;
      stopButton.disabled = false;
      setVoiceStatus("Configuring realtime session…", "busy");
    });
    socket.addEventListener("close", () => {
      setVoiceStatus("Disconnected", "idle");
      void stopVoice();
    }, { once: true });
    socket.addEventListener("error", () => {
      setVoiceStatus("Unable to connect to the voice gateway", "error");
    });
  } catch (error) {
    setVoiceStatus(error instanceof Error ? error.message : "Unable to start voice", "error");
    await stopVoice();
  }
}

async function stopVoice() {
  sessionConfigured = false;
  if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, "client_stop");
  socket = null;
  stopPlayback();
  captureNode?.disconnect();
  captureNode = null;
  for (const track of mediaStream?.getTracks() || []) track.stop();
  mediaStream = null;
  if (audioContext && audioContext.state !== "closed") await audioContext.close();
  audioContext = null;
  muted = false;
  commandInFlight = false;
  startButton.disabled = false;
  muteButton.disabled = true;
  muteButton.textContent = "Mute";
  cancelButton.disabled = true;
  stopButton.disabled = true;
}

startButton?.addEventListener("click", () => void startVoice());
stopButton?.addEventListener("click", () => void stopVoice());
muteButton?.addEventListener("click", () => {
  muted = !muted;
  muteButton.textContent = muted ? "Unmute" : "Mute";
  setVoiceStatus(muted ? "Microphone muted" : "Connected — speak naturally", muted ? "idle" : "ready");
});

cancelButton?.addEventListener("click", () => {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "response.cancel" }));
    stopPlayback();
    globalThis.speechSynthesis?.cancel?.();
    setVoiceStatus("Response cancelled", "ready");
  }
});

clearButton?.addEventListener("click", () => {
  voiceTranscript.replaceChildren();
  emptyState.hidden = false;
});

window.addEventListener("beforeunload", () => {
  if (socket && socket.readyState < WebSocket.CLOSING) socket.close();
  for (const track of mediaStream?.getTracks() || []) track.stop();
});
