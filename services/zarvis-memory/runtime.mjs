import { createHash, randomUUID } from "node:crypto";
import { EncryptedMemoryStore } from "./crypto-store.mjs";

export const ZARVIS_OWNER_GITHUB_ID = "4076926";
export const ZARVIS_OWNER_USER_ID = `github:${ZARVIS_OWNER_GITHUB_ID}`;
export const ZARVIS_OWNER_TENANT_ID = `owner-${ZARVIS_OWNER_GITHUB_ID}`;

const ID_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/;
const MEMORY_CLASSES = new Set(["working", "episodic", "semantic", "procedural"]);
const PROPOSAL_TTL_MS = 15 * 60 * 1000;
const RETENTION_LIMITS = Object.freeze({
  working: { default_days: 1, max_days: 7 },
  episodic: { default_days: 90, max_days: 365 },
  semantic: { default_days: 365, max_days: 3650 },
  procedural: { default_days: 365, max_days: 3650 },
});

export class MemoryValidationError extends Error {
  constructor(message, status = 400, code = "invalid_memory_request") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function requireString(value, field, max = 4000) {
  if (typeof value !== "string") throw new MemoryValidationError(`${field} is required`);
  const normalized = value.trim();
  if (!normalized || normalized.length > max) {
    throw new MemoryValidationError(`${field} is invalid`);
  }
  return normalized;
}

function optionalString(value, field, max = 1000) {
  if (value == null || value === "") return null;
  return requireString(value, field, max);
}

function requireId(value, field) {
  const normalized = requireString(value, field, 128);
  if (!ID_PATTERN.test(normalized)) throw new MemoryValidationError(`${field} is invalid`);
  return normalized;
}

function normalizeConfidence(value) {
  const confidence = value == null ? 1 : Number(value);
  if (!Number.isFinite(confidence) || confidence < 0 || confidence > 1) {
    throw new MemoryValidationError("confidence must be between 0 and 1");
  }
  return confidence;
}

function normalizeClassification(value) {
  const classification = requireString(value, "classification", 32).toLowerCase();
  if (!MEMORY_CLASSES.has(classification)) {
    throw new MemoryValidationError("classification is unsupported");
  }
  return classification;
}

function normalizeRetentionDays(value, classification) {
  const policy = RETENTION_LIMITS[classification];
  const days = value == null ? policy.default_days : Number(value);
  if (!Number.isInteger(days) || days < 1 || days > policy.max_days) {
    throw new MemoryValidationError(
      `retention_days for ${classification} must be between 1 and ${policy.max_days}`,
    );
  }
  return days;
}

function normalizeProvenance(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new MemoryValidationError("provenance is required");
  }
  const sourceType = requireString(value.source_type, "provenance.source_type", 64);
  if (!["owner", "session", "task", "document", "integration"].includes(sourceType)) {
    throw new MemoryValidationError("provenance.source_type is unsupported");
  }
  return {
    source_type: sourceType,
    source_id: requireString(value.source_id, "provenance.source_id", 256),
    source_uri: optionalString(value.source_uri, "provenance.source_uri", 1000),
    captured_at: optionalString(value.captured_at, "provenance.captured_at", 64),
  };
}

const SECRET_PATTERNS = [
  /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/i,
  /\b(?:sk|pk)-[A-Za-z0-9_-]{16,}\b/,
  /\bgh[pousr]_[A-Za-z0-9]{20,}\b/,
  /\bgithub_pat_[A-Za-z0-9_]{20,}\b/,
  /\bAKIA[0-9A-Z]{16}\b/,
  /\bBearer\s+[A-Za-z0-9._~+/=-]{16,}/i,
  /\b(?:password|passwd|secret|api[_-]?key|private[_-]?key)\s*[:=]\s*\S+/i,
  /\b(?:\d[ -]*?){13,19}\b/,
];

export function assertMemorySafe(content) {
  for (const pattern of SECRET_PATTERNS) {
    if (pattern.test(content)) {
      throw new MemoryValidationError(
        "Raw secrets, private keys, credentials, or payment card data cannot be stored in memory",
        422,
        "sensitive_content_rejected",
      );
    }
  }
}

function canonicalProposal(value) {
  return {
    memory_id: value.memory_id,
    revision: value.revision,
    content: value.content,
    classification: value.classification,
    reason: value.reason,
    confidence: value.confidence,
    retention_days: value.retention_days,
    expires_at: value.expires_at,
    provenance: value.provenance,
  };
}

function proposalDigest(value) {
  return createHash("sha256").update(JSON.stringify(canonicalProposal(value))).digest("hex");
}

function addDays(iso, days) {
  const timestamp = Date.parse(iso);
  if (!Number.isFinite(timestamp)) throw new MemoryValidationError("Runtime clock is invalid", 500);
  return new Date(timestamp + days * 24 * 60 * 60 * 1000).toISOString();
}

function addMilliseconds(iso, milliseconds) {
  const timestamp = Date.parse(iso);
  if (!Number.isFinite(timestamp)) throw new MemoryValidationError("Runtime clock is invalid", 500);
  return new Date(timestamp + milliseconds).toISOString();
}

function latestState(events) {
  const proposals = new Map();
  const memories = new Map();
  for (const event of events) {
    if (event.event_type === "memory.proposal-created.v1") {
      proposals.set(event.proposal_id, event);
    } else if (event.event_type === "memory.confirmed.v1") {
      memories.set(event.memory.memory_id, event.memory);
    } else if (event.event_type === "memory.deleted.v1") {
      memories.delete(event.memory_id);
    }
  }
  return { proposals, memories };
}

function isExpired(memory, now) {
  return Date.parse(memory.expires_at) <= Date.parse(now);
}

function publicProposal(proposal) {
  return {
    schema_version: "zarvis.memory.proposal.v1",
    proposal_id: proposal.proposal_id,
    memory_id: proposal.memory_id,
    revision: proposal.revision,
    content: proposal.content,
    classification: proposal.classification,
    reason: proposal.reason,
    confidence: proposal.confidence,
    retention_days: proposal.retention_days,
    expires_at: proposal.expires_at,
    provenance: proposal.provenance,
    approval_digest: proposal.approval_digest,
    approval_nonce: proposal.approval_nonce,
    approval_expires_at: proposal.approval_expires_at,
    created_at: proposal.created_at,
  };
}

function publicMemory(memory) {
  return structuredClone(memory);
}

function tokenize(value) {
  return new Set(String(value).toLowerCase().match(/[\p{L}\p{N}_-]+/gu) ?? []);
}

function lexicalScore(memory, queryTokens) {
  if (!queryTokens.size) return 1;
  const haystack = tokenize([
    memory.content,
    memory.classification,
    memory.reason,
    memory.provenance.source_type,
    memory.provenance.source_id,
  ].join(" "));
  let matches = 0;
  for (const token of queryTokens) if (haystack.has(token)) matches += 1;
  return matches / queryTokens.size;
}

export class ZarvisMemoryRuntime {
  constructor({
    store = new EncryptedMemoryStore(),
    now = () => new Date().toISOString(),
    idFactory = randomUUID,
  } = {}) {
    this.store = store;
    this.now = now;
    this.idFactory = idFactory;
  }

  async createProposal(input, { memoryId, revision } = {}) {
    if (input.schema_version && input.schema_version !== "zarvis.memory.proposal-requested.v1") {
      throw new MemoryValidationError("schema_version is unsupported");
    }
    const now = this.now();
    const classification = normalizeClassification(input.classification);
    const content = requireString(input.content, "content");
    assertMemorySafe(content);
    const retentionDays = normalizeRetentionDays(input.retention_days, classification);
    const proposal = {
      event_id: this.idFactory(),
      event_type: "memory.proposal-created.v1",
      occurred_at: now,
      proposal_id: this.idFactory(),
      memory_id: memoryId ?? this.idFactory(),
      revision: revision ?? 1,
      content,
      classification,
      reason: requireString(input.reason, "reason", 1000),
      confidence: normalizeConfidence(input.confidence),
      retention_days: retentionDays,
      expires_at: addDays(now, retentionDays),
      provenance: normalizeProvenance(input.provenance),
      approval_nonce: this.idFactory(),
      approval_expires_at: addMilliseconds(now, PROPOSAL_TTL_MS),
      created_at: now,
      owner_user_id: ZARVIS_OWNER_USER_ID,
      tenant_id: ZARVIS_OWNER_TENANT_ID,
    };
    proposal.approval_digest = proposalDigest(proposal);
    await this.store.append(proposal);
    return publicProposal(proposal);
  }

  async proposeCorrection(memoryId, input) {
    const current = await this.getMemory(memoryId);
    return this.createProposal(input, {
      memoryId: current.memory_id,
      revision: current.revision + 1,
    });
  }

  async confirmProposal(proposalId, input) {
    requireId(proposalId, "proposal_id");
    const events = await this.store.readEvents();
    const { proposals, memories } = latestState(events);
    const proposal = proposals.get(proposalId);
    if (!proposal) throw new MemoryValidationError("Memory proposal was not found", 404, "proposal_not_found");

    const existing = [...events].reverse().find(
      (event) => event.event_type === "memory.confirmed.v1" && event.proposal_id === proposalId,
    );
    if (existing) return { ...publicMemory(existing.memory), replayed: true };

    const now = this.now();
    if (Date.parse(now) > Date.parse(proposal.approval_expires_at)) {
      throw new MemoryValidationError("Memory proposal approval has expired", 409, "proposal_expired");
    }
    if (input.approval_digest !== proposal.approval_digest) {
      throw new MemoryValidationError("Approval digest does not match the exact memory proposal", 409, "approval_mismatch");
    }
    if (input.approval_nonce !== proposal.approval_nonce) {
      throw new MemoryValidationError("Approval nonce is invalid", 409, "approval_mismatch");
    }

    const previous = memories.get(proposal.memory_id);
    if (previous && previous.revision >= proposal.revision) {
      throw new MemoryValidationError("Memory proposal revision is stale", 409, "stale_revision");
    }

    const memory = {
      schema_version: "zarvis.memory.snapshot.v1",
      memory_id: proposal.memory_id,
      revision: proposal.revision,
      content: proposal.content,
      classification: proposal.classification,
      reason: proposal.reason,
      confidence: proposal.confidence,
      retention_days: proposal.retention_days,
      expires_at: proposal.expires_at,
      provenance: proposal.provenance,
      owner_user_id: ZARVIS_OWNER_USER_ID,
      tenant_id: ZARVIS_OWNER_TENANT_ID,
      created_at: previous?.created_at ?? now,
      updated_at: now,
      confirmed_at: now,
      proposal_id: proposal.proposal_id,
    };
    await this.store.append({
      event_id: this.idFactory(),
      event_type: "memory.confirmed.v1",
      occurred_at: now,
      proposal_id: proposalId,
      memory,
    });
    return { ...publicMemory(memory), replayed: false };
  }

  async listMemories({ query = "", classification = null, includeExpired = false } = {}) {
    const now = this.now();
    const { memories } = latestState(await this.store.readEvents());
    const queryTokens = tokenize(query);
    const normalizedClass = classification ? normalizeClassification(classification) : null;
    return [...memories.values()]
      .filter((memory) => includeExpired || !isExpired(memory, now))
      .filter((memory) => !normalizedClass || memory.classification === normalizedClass)
      .map((memory) => ({ memory, score: lexicalScore(memory, queryTokens) }))
      .filter(({ score }) => !queryTokens.size || score > 0)
      .sort((a, b) => b.score - a.score || String(b.memory.updated_at).localeCompare(String(a.memory.updated_at)))
      .map(({ memory, score }) => ({ ...publicMemory(memory), retrieval_score: score }));
  }

  async getMemory(memoryId) {
    requireId(memoryId, "memory_id");
    const { memories } = latestState(await this.store.readEvents());
    const memory = memories.get(memoryId);
    if (!memory) throw new MemoryValidationError("Memory was not found", 404, "memory_not_found");
    return publicMemory(memory);
  }

  async deleteMemory(memoryId) {
    const memory = await this.getMemory(memoryId);
    const result = await this.store.compact((event) => event.memory_id !== memory.memory_id
      && event.memory?.memory_id !== memory.memory_id);
    return {
      memory_id: memory.memory_id,
      deleted: result.removed > 0,
      encrypted_events_removed: result.removed,
      index_derivatives_removed: 0,
      deleted_at: this.now(),
    };
  }

  async exportMemories() {
    const memories = await this.listMemories({ includeExpired: false });
    return {
      schema_version: "zarvis.memory.export.v1",
      exported_at: this.now(),
      owner_user_id: ZARVIS_OWNER_USER_ID,
      tenant_id: ZARVIS_OWNER_TENANT_ID,
      memories: memories.map(({ retrieval_score, ...memory }) => memory),
    };
  }

  async purgeExpired() {
    const now = this.now();
    const events = await this.store.readEvents();
    const { memories } = latestState(events);
    const expiredIds = new Set(
      [...memories.values()].filter((memory) => isExpired(memory, now)).map((memory) => memory.memory_id),
    );
    if (!expiredIds.size) return { purged_memories: 0, encrypted_events_removed: 0 };
    const result = await this.store.compact((event) => {
      const memoryId = event.memory_id ?? event.memory?.memory_id;
      return !expiredIds.has(memoryId);
    });
    return {
      purged_memories: expiredIds.size,
      encrypted_events_removed: result.removed,
      purged_at: now,
    };
  }
}
