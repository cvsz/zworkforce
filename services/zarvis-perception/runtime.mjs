import { createHash, randomUUID } from "node:crypto";
import { TextDecoder } from "node:util";
import { EncryptedPerceptionStore } from "./crypto-store.mjs";

export const ZARVIS_OWNER_GITHUB_ID = "4076926";
export const ZARVIS_OWNER_USER_ID = `github:${ZARVIS_OWNER_GITHUB_ID}`;
export const ZARVIS_OWNER_TENANT_ID = `owner-${ZARVIS_OWNER_GITHUB_ID}`;

const ID_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/;
const MODALITIES = new Set(["image", "document", "screen", "camera"]);
const MEDIA_TYPES = new Set(["text/plain", "application/pdf", "image/png", "image/jpeg"]);
const MAX_MEDIA_BYTES = 5 * 1024 * 1024;
const MAX_TEXT_CHARS = 20_000;
const CONSENT_TTL_MS = 10 * 60 * 1000;
const ACTIVE_SESSION_TTL_MS = 15 * 60 * 1000;

export class PerceptionValidationError extends Error {
  constructor(message, status = 400, code = "invalid_perception_request") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function requireString(value, field, max = 2000) {
  if (typeof value !== "string") throw new PerceptionValidationError(`${field} is required`);
  const normalized = value.trim();
  if (!normalized || normalized.length > max) {
    throw new PerceptionValidationError(`${field} is invalid`);
  }
  return normalized;
}

function optionalString(value, field, max = 1000) {
  if (value == null || value === "") return null;
  return requireString(value, field, max);
}

function requireId(value, field) {
  const id = requireString(value, field, 128);
  if (!ID_PATTERN.test(id)) throw new PerceptionValidationError(`${field} is invalid`);
  return id;
}

function addMilliseconds(iso, milliseconds) {
  const timestamp = Date.parse(iso);
  if (!Number.isFinite(timestamp)) throw new PerceptionValidationError("Runtime clock is invalid", 500);
  return new Date(timestamp + milliseconds).toISOString();
}

function normalizeModalities(value) {
  if (!Array.isArray(value) || value.length < 1 || value.length > 4) {
    throw new PerceptionValidationError("modalities must contain between 1 and 4 values");
  }
  const unique = [];
  for (const item of value) {
    const modality = requireString(item, "modality", 32).toLowerCase();
    if (!MODALITIES.has(modality)) throw new PerceptionValidationError(`Unsupported modality: ${modality}`);
    if (!unique.includes(modality)) unique.push(modality);
  }
  return unique;
}

function normalizeRetention(value) {
  const minutes = value == null ? 60 : Number(value);
  if (!Number.isInteger(minutes) || minutes < 1 || minutes > 1440) {
    throw new PerceptionValidationError("retention_minutes must be between 1 and 1440");
  }
  return minutes;
}

function canonicalConsent(session) {
  return {
    session_id: session.session_id,
    purpose: session.purpose,
    modalities: [...session.modalities],
    retention_minutes: session.retention_minutes,
    retention_expires_at: session.retention_expires_at,
  };
}

function consentDigest(session) {
  return createHash("sha256").update(JSON.stringify(canonicalConsent(session))).digest("hex");
}

function strictBase64(value) {
  const encoded = requireString(value, "content_base64", Math.ceil(MAX_MEDIA_BYTES * 4 / 3) + 16);
  if (!/^[A-Za-z0-9+/]*={0,2}$/.test(encoded) || encoded.length % 4 !== 0) {
    throw new PerceptionValidationError("content_base64 must be canonical base64");
  }
  const buffer = Buffer.from(encoded, "base64");
  const normalizedInput = encoded.replace(/=+$/, "");
  const normalizedOutput = buffer.toString("base64").replace(/=+$/, "");
  if (normalizedInput !== normalizedOutput) {
    throw new PerceptionValidationError("content_base64 must be canonical base64");
  }
  if (buffer.length < 1 || buffer.length > MAX_MEDIA_BYTES) {
    throw new PerceptionValidationError(`Media must contain between 1 and ${MAX_MEDIA_BYTES} bytes`, 413, "media_size_invalid");
  }
  return buffer;
}

function assertModalityMediaType(modality, mediaType) {
  if (!MEDIA_TYPES.has(mediaType)) throw new PerceptionValidationError(`Unsupported media_type: ${mediaType}`);
  if (["screen", "camera", "image"].includes(modality) && !["image/png", "image/jpeg"].includes(mediaType)) {
    throw new PerceptionValidationError(`${modality} requires image/png or image/jpeg`);
  }
  if (modality === "document" && !["text/plain", "application/pdf"].includes(mediaType)) {
    throw new PerceptionValidationError("document requires text/plain or application/pdf");
  }
}

function replaceCount(text, pattern, replacement) {
  let count = 0;
  return {
    text: text.replace(pattern, () => {
      count += 1;
      return replacement;
    }),
    count,
  };
}

function redactUntrustedText(value) {
  let text = value;
  let redactionCount = 0;
  let injectionCount = 0;
  const redactions = [
    [/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/gi, "[REDACTED_PRIVATE_KEY]"],
    [/\b(?:sk|pk)-[A-Za-z0-9_-]{16,}\b/g, "[REDACTED_SECRET]"],
    [/\bgh[pousr]_[A-Za-z0-9]{20,}\b/g, "[REDACTED_GITHUB_TOKEN]"],
    [/\bgithub_pat_[A-Za-z0-9_]{20,}\b/g, "[REDACTED_GITHUB_TOKEN]"],
    [/\bBearer\s+[A-Za-z0-9._~+/=-]{16,}/gi, "[REDACTED_BEARER_TOKEN]"],
    [/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, "[REDACTED_EMAIL]"],
    [/(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)/g, "[REDACTED_PHONE]"],
  ];
  for (const [pattern, replacement] of redactions) {
    const result = replaceCount(text, pattern, replacement);
    text = result.text;
    redactionCount += result.count;
  }

  const injectionPatterns = [
    /ignore\s+(?:all\s+)?previous\s+(?:instructions?|messages?)/gi,
    /reveal\s+(?:the\s+)?(?:system|developer)\s+(?:prompt|message)/gi,
    /(?:system|developer)\s+(?:prompt|message)/gi,
    /(?:call|invoke|run)\s+(?:a\s+)?tool/gi,
    /execute\s+(?:this\s+)?command/gi,
    /grant\s+(?:me\s+)?(?:access|permission|capability)/gi,
  ];
  for (const pattern of injectionPatterns) {
    const result = replaceCount(text, pattern, "[UNTRUSTED_INSTRUCTION]");
    text = result.text;
    injectionCount += result.count;
  }
  return { text, redactionCount, injectionCount };
}

function textSummary(text) {
  const compact = text.replace(/\s+/g, " ").trim();
  const words = compact ? compact.split(" ").length : 0;
  return {
    kind: "redacted_text",
    summary: compact.slice(0, 280) || "No readable text was found.",
    excerpt: compact.slice(0, 1000),
    word_count: words,
  };
}

function decodeUtf8(buffer) {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(buffer).slice(0, MAX_TEXT_CHARS);
  } catch {
    throw new PerceptionValidationError("text/plain content must be valid UTF-8");
  }
}

function extractPdfText(buffer) {
  if (buffer.subarray(0, 5).toString("ascii") !== "%PDF-") {
    throw new PerceptionValidationError("PDF signature is invalid");
  }
  const source = buffer.toString("latin1");
  const parenthesized = [...source.matchAll(/\(([^()]*)\)/g)].map((match) => match[1]);
  const printable = source.match(/[\x20-\x7E]{4,}/g) ?? [];
  return [...parenthesized, ...printable]
    .join(" ")
    .replace(/\\[nrtbf]/g, " ")
    .slice(0, MAX_TEXT_CHARS);
}

function parsePng(buffer) {
  const signature = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  if (buffer.length < 24 || !buffer.subarray(0, 8).equals(signature) || buffer.subarray(12, 16).toString("ascii") !== "IHDR") {
    throw new PerceptionValidationError("PNG signature or IHDR is invalid");
  }
  const width = buffer.readUInt32BE(16);
  const height = buffer.readUInt32BE(20);
  if (!width || !height || width > 16_384 || height > 16_384) {
    throw new PerceptionValidationError("PNG dimensions are invalid");
  }
  return { kind: "image_metadata", format: "png", width, height, summary: `PNG image ${width}×${height}` };
}

function parseJpeg(buffer) {
  if (buffer.length < 4 || buffer[0] !== 0xff || buffer[1] !== 0xd8) {
    throw new PerceptionValidationError("JPEG signature is invalid");
  }
  const sofMarkers = new Set([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf]);
  let offset = 2;
  while (offset + 4 <= buffer.length) {
    if (buffer[offset] !== 0xff) { offset += 1; continue; }
    while (buffer[offset] === 0xff) offset += 1;
    const marker = buffer[offset++];
    if ([0xd8, 0xd9, 0x01].includes(marker) || (marker >= 0xd0 && marker <= 0xd7)) continue;
    if (offset + 2 > buffer.length) break;
    const length = buffer.readUInt16BE(offset);
    if (length < 2 || offset + length > buffer.length) break;
    if (sofMarkers.has(marker) && length >= 7) {
      const height = buffer.readUInt16BE(offset + 3);
      const width = buffer.readUInt16BE(offset + 5);
      if (!width || !height || width > 16_384 || height > 16_384) {
        throw new PerceptionValidationError("JPEG dimensions are invalid");
      }
      return { kind: "image_metadata", format: "jpeg", width, height, summary: `JPEG image ${width}×${height}` };
    }
    offset += length;
  }
  throw new PerceptionValidationError("JPEG dimensions could not be resolved");
}

function analyzeBuffer(buffer, mediaType) {
  if (mediaType === "image/png") {
    return { analysis: parsePng(buffer), redactionCount: 0, injectionCount: 0 };
  }
  if (mediaType === "image/jpeg") {
    return { analysis: parseJpeg(buffer), redactionCount: 0, injectionCount: 0 };
  }
  const rawText = mediaType === "application/pdf" ? extractPdfText(buffer) : decodeUtf8(buffer);
  const redacted = redactUntrustedText(rawText);
  return {
    analysis: textSummary(redacted.text),
    redactionCount: redacted.redactionCount,
    injectionCount: redacted.injectionCount,
  };
}

function sessionState(events) {
  const sessions = new Map();
  for (const event of events) {
    if (event.event_type === "perception.session-proposed.v1") {
      sessions.set(event.session.session_id, { ...event.session, results: [] });
    } else if (event.event_type === "perception.session-activated.v1") {
      const session = sessions.get(event.session_id);
      if (session) Object.assign(session, { status: "active", activated_at: event.occurred_at, active_expires_at: event.active_expires_at });
    } else if (event.event_type === "perception.media-analyzed.v1") {
      sessions.get(event.result.session_id)?.results.push(event.result);
    } else if (event.event_type === "perception.session-stopped.v1") {
      const session = sessions.get(event.session_id);
      if (session) Object.assign(session, { status: "stopped", stopped_at: event.occurred_at });
    }
  }
  return sessions;
}

function publicSession(session) { return structuredClone(session); }

export class ZarvisPerceptionRuntime {
  constructor({
    store = new EncryptedPerceptionStore(),
    now = () => new Date().toISOString(),
    idFactory = randomUUID,
  } = {}) {
    this.store = store;
    this.now = now;
    this.idFactory = idFactory;
  }

  async createSession(input) {
    const now = this.now();
    const retentionMinutes = normalizeRetention(input.retention_minutes);
    const session = {
      schema_version: "zarvis.perception.session.v1",
      session_id: this.idFactory(),
      purpose: requireString(input.purpose, "purpose", 1000),
      modalities: normalizeModalities(input.modalities),
      retention_minutes: retentionMinutes,
      retention_expires_at: addMilliseconds(now, retentionMinutes * 60 * 1000),
      status: "pending_consent",
      consent_nonce: this.idFactory(),
      consent_expires_at: addMilliseconds(now, CONSENT_TTL_MS),
      created_at: now,
      owner_user_id: ZARVIS_OWNER_USER_ID,
      tenant_id: ZARVIS_OWNER_TENANT_ID,
    };
    session.consent_digest = consentDigest(session);
    await this.store.append({
      event_id: this.idFactory(),
      event_type: "perception.session-proposed.v1",
      occurred_at: now,
      session,
    });
    return publicSession(session);
  }

  async getSession(sessionId) {
    requireId(sessionId, "session_id");
    const session = sessionState(await this.store.readEvents()).get(sessionId);
    if (!session) throw new PerceptionValidationError("Perception session was not found", 404, "session_not_found");
    return publicSession(session);
  }

  async listSessions() {
    return [...sessionState(await this.store.readEvents()).values()]
      .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
      .map(publicSession);
  }

  async activateSession(sessionId, input) {
    const session = await this.getSession(sessionId);
    if (session.status !== "pending_consent") {
      throw new PerceptionValidationError("Perception session is not awaiting consent", 409, "invalid_session_state");
    }
    const now = this.now();
    if (Date.parse(now) > Date.parse(session.consent_expires_at)) {
      throw new PerceptionValidationError("Perception consent has expired", 409, "consent_expired");
    }
    if (input.consent_digest !== session.consent_digest || input.consent_nonce !== session.consent_nonce) {
      throw new PerceptionValidationError("Consent proof does not match the exact perception session", 409, "consent_mismatch");
    }
    const activeExpiresAt = addMilliseconds(now, ACTIVE_SESSION_TTL_MS);
    await this.store.append({
      event_id: this.idFactory(),
      event_type: "perception.session-activated.v1",
      occurred_at: now,
      session_id: session.session_id,
      active_expires_at: activeExpiresAt,
    });
    return this.getSession(session.session_id);
  }

  async stopSession(sessionId) {
    const session = await this.getSession(sessionId);
    if (session.status === "stopped") return session;
    await this.store.append({
      event_id: this.idFactory(),
      event_type: "perception.session-stopped.v1",
      occurred_at: this.now(),
      session_id: session.session_id,
    });
    return this.getSession(session.session_id);
  }

  async analyzeMedia(sessionId, input) {
    const session = await this.getSession(sessionId);
    if (session.status !== "active") {
      throw new PerceptionValidationError("Perception session must be active", 409, "session_not_active");
    }
    const now = this.now();
    if (Date.parse(now) > Date.parse(session.active_expires_at) || Date.parse(now) > Date.parse(session.retention_expires_at)) {
      throw new PerceptionValidationError("Perception session has expired", 409, "session_expired");
    }
    const modality = requireString(input.source_modality, "source_modality", 32).toLowerCase();
    if (!session.modalities.includes(modality)) {
      throw new PerceptionValidationError("Source modality was not included in owner consent", 403, "modality_not_consented");
    }
    const mediaType = requireString(input.media_type, "media_type", 64).toLowerCase();
    assertModalityMediaType(modality, mediaType);
    const buffer = strictBase64(input.content_base64);
    const processed = analyzeBuffer(buffer, mediaType);
    const result = {
      schema_version: "zarvis.perception.result.v1",
      result_id: this.idFactory(),
      session_id: session.session_id,
      source_modality: modality,
      media_type: mediaType,
      analysis: processed.analysis,
      security: {
        untrusted_content: true,
        policy_effect: "none",
        tool_grants: [],
        raw_media_retained: false,
        redaction_count: processed.redactionCount,
        injection_markers_neutralized: processed.injectionCount,
      },
      provenance: {
        schema_version: "zarvis.perception.provenance.v1",
        source_name: requireString(input.source_name, "source_name", 256),
        source_modality: modality,
        media_type: mediaType,
        byte_length: buffer.length,
        sha256: createHash("sha256").update(buffer).digest("hex"),
        captured_at: optionalString(input.captured_at, "captured_at", 64),
        analyzed_at: now,
        analyzer: "zarvis-local-redaction-v1",
        owner_user_id: ZARVIS_OWNER_USER_ID,
        tenant_id: ZARVIS_OWNER_TENANT_ID,
      },
      expires_at: session.retention_expires_at,
      created_at: now,
    };
    buffer.fill(0);
    await this.store.append({
      event_id: this.idFactory(),
      event_type: "perception.media-analyzed.v1",
      occurred_at: now,
      result,
    });
    return structuredClone(result);
  }

  async deleteSession(sessionId) {
    const session = await this.getSession(sessionId);
    const compacted = await this.store.compact((event) => {
      const eventSessionId = event.session?.session_id ?? event.session_id ?? event.result?.session_id;
      return eventSessionId !== session.session_id;
    });
    return {
      session_id: session.session_id,
      deleted: compacted.removed > 0,
      encrypted_events_removed: compacted.removed,
      raw_media_removed: 0,
      deleted_at: this.now(),
    };
  }

  async purgeExpired() {
    const now = this.now();
    const sessions = sessionState(await this.store.readEvents());
    const expiredIds = new Set([...sessions.values()]
      .filter((session) => Date.parse(session.retention_expires_at) <= Date.parse(now))
      .map((session) => session.session_id));
    if (!expiredIds.size) return { purged_sessions: 0, encrypted_events_removed: 0, purged_at: now };
    const compacted = await this.store.compact((event) => {
      const eventSessionId = event.session?.session_id ?? event.session_id ?? event.result?.session_id;
      return !expiredIds.has(eventSessionId);
    });
    return { purged_sessions: expiredIds.size, encrypted_events_removed: compacted.removed, purged_at: now };
  }
}
