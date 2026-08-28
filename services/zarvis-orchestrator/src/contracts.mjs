import { randomUUID } from 'node:crypto';

export const COMMAND_REQUEST_SCHEMA = 'zarvis.command.requested.v1';
export const COMMAND_COMPLETED_SCHEMA = 'zarvis.command.completed.v1';
export const TOOL_AUDIT_SCHEMA = 'zarvis.audit.tool-executed.v1';
export const SESSION_EVENT_SCHEMA = 'zarvis.session.event.v1';

const SESSION_ID_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/;
const SUBJECT_ID_PATTERN = /^[A-Za-z0-9._:@/-]{1,160}$/;
const REPOSITORY_SEGMENT_PATTERN = /^[A-Za-z0-9_.-]+$/;
const SUPPORTED_MODALITIES = new Set(['text', 'voice']);
const SESSION_EVENT_TYPES = new Set([
  'command.accepted',
  'command.completed',
  'command.failed',
]);

export class ValidationError extends Error {
  constructor(message, details = undefined) {
    super(message);
    this.name = 'ValidationError';
    this.code = 'invalid_request';
    this.details = details;
  }
}

export class UnsupportedIntentError extends Error {
  constructor(message = 'No supported intent could be resolved from the command.') {
    super(message);
    this.name = 'UnsupportedIntentError';
    this.code = 'unsupported_intent';
  }
}

export class IdempotencyConflictError extends Error {
  constructor() {
    super('command_id was already used with a different command payload.');
    this.name = 'IdempotencyConflictError';
    this.code = 'idempotency_conflict';
    this.status = 409;
  }
}

function requirePlainObject(value, field) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new ValidationError(`${field} must be an object.`);
  }
  return value;
}

function requireBoundedString(value, field, { min = 1, max = 256, pattern } = {}) {
  if (typeof value !== 'string') {
    throw new ValidationError(`${field} must be a string.`);
  }

  const normalized = value.trim();
  if (normalized.length < min || normalized.length > max) {
    throw new ValidationError(`${field} must contain between ${min} and ${max} characters.`);
  }

  if (pattern && !pattern.test(normalized)) {
    throw new ValidationError(`${field} contains unsupported characters.`);
  }

  return normalized;
}

export function normalizeSessionId(value, field = 'session_id') {
  return requireBoundedString(value, field, {
    max: 128,
    pattern: SESSION_ID_PATTERN,
  });
}

export function normalizeCommandId(value, field = 'command_id') {
  return requireBoundedString(value, field, {
    max: 128,
    pattern: SESSION_ID_PATTERN,
  });
}

export function normalizeRepositoryTarget(value) {
  const target = requirePlainObject(value, 'tool.arguments');
  const owner = requireBoundedString(target.owner, 'tool.arguments.owner', {
    max: 39,
    pattern: REPOSITORY_SEGMENT_PATTERN,
  });
  const repo = requireBoundedString(target.repo, 'tool.arguments.repo', {
    max: 100,
    pattern: REPOSITORY_SEGMENT_PATTERN,
  });

  return { owner, repo };
}

export function inferGitHubRepositoryTarget(text) {
  if (typeof text !== 'string') return null;

  const intentSignal = /\b(github|repo(?:sitory)?|คลัง|กิตฮับ|สถานะ)\b/i.test(text);
  const match = text.match(/(?:https?:\/\/github\.com\/)?([A-Za-z0-9_.-]{1,39})\/([A-Za-z0-9_.-]{1,100})(?=$|[\s#?.,;:!])/i);

  if (!intentSignal || !match) return null;
  return normalizeRepositoryTarget({ owner: match[1], repo: match[2] });
}

export function normalizeCommandRequest(value) {
  const request = requirePlainObject(value, 'request');
  const input = requirePlainObject(request.input, 'input');
  const modality = requireBoundedString(input.modality ?? 'text', 'input.modality', { max: 16 });

  if (!SUPPORTED_MODALITIES.has(modality)) {
    throw new ValidationError('input.modality must be either text or voice.');
  }

  const normalized = {
    schema_version: request.schema_version ?? COMMAND_REQUEST_SCHEMA,
    command_id: request.command_id
      ? normalizeCommandId(request.command_id)
      : randomUUID(),
    session_id: normalizeSessionId(request.session_id),
    input: {
      modality,
      text: requireBoundedString(input.text, 'input.text', { max: 2_000 }),
      locale: typeof input.locale === 'string' && input.locale.trim()
        ? requireBoundedString(input.locale, 'input.locale', { max: 32 })
        : 'th-TH',
    },
    tool: null,
  };

  if (normalized.schema_version !== COMMAND_REQUEST_SCHEMA) {
    throw new ValidationError(`schema_version must be ${COMMAND_REQUEST_SCHEMA}.`);
  }

  if (request.tool !== undefined && request.tool !== null) {
    const tool = requirePlainObject(request.tool, 'tool');
    const name = requireBoundedString(tool.name, 'tool.name', { max: 128 });
    if (name !== 'github.repository.status') {
      throw new ValidationError('Only the read-only github.repository.status tool is available in this slice.');
    }
    normalized.tool = {
      name,
      arguments: normalizeRepositoryTarget(tool.arguments),
    };
  }

  return normalized;
}

export function normalizeActorContext(context = {}) {
  const tenantId = context.tenantId ?? 'anonymous';
  const userId = context.userId ?? 'anonymous';
  const requestId = context.requestId ?? randomUUID();

  return {
    tenant_id: requireBoundedString(String(tenantId), 'tenant_id', {
      max: 160,
      pattern: SUBJECT_ID_PATTERN,
    }),
    user_id: requireBoundedString(String(userId), 'user_id', {
      max: 160,
      pattern: SUBJECT_ID_PATTERN,
    }),
    request_id: requireBoundedString(String(requestId), 'request_id', {
      max: 160,
      pattern: SUBJECT_ID_PATTERN,
    }),
  };
}

export function resolveCommandIntent(command) {
  if (command.tool) {
    return {
      name: command.tool.name,
      arguments: command.tool.arguments,
      source: 'explicit',
    };
  }

  const repository = inferGitHubRepositoryTarget(command.input.text);
  if (repository) {
    return {
      name: 'github.repository.status',
      arguments: repository,
      source: 'inferred',
    };
  }

  throw new UnsupportedIntentError();
}

export function createToolAuditEvent({
  command,
  actor,
  intent,
  outcome,
  durationMs,
  resultSummary,
  errorCode,
  now = () => new Date(),
  eventId = randomUUID(),
}) {
  return {
    schema_version: TOOL_AUDIT_SCHEMA,
    event_id: eventId,
    occurred_at: now().toISOString(),
    tenant_id: actor.tenant_id,
    user_id: actor.user_id,
    request_id: actor.request_id,
    command_id: command.command_id,
    session_id: command.session_id,
    tool: {
      name: intent.name,
      access: 'read_only',
      arguments: intent.arguments,
    },
    outcome,
    duration_ms: Math.max(0, Math.round(durationMs)),
    ...(resultSummary ? { result_summary: resultSummary } : {}),
    ...(errorCode ? { error_code: errorCode } : {}),
  };
}

export function createSessionEvent({
  eventType,
  command,
  actor,
  payload,
  now = () => new Date(),
  eventId = randomUUID(),
}) {
  if (!SESSION_EVENT_TYPES.has(eventType)) {
    throw new ValidationError('Unsupported session event type.');
  }

  return {
    schema_version: SESSION_EVENT_SCHEMA,
    event_id: normalizeCommandId(String(eventId), 'event_id'),
    event_type: eventType,
    occurred_at: now().toISOString(),
    session_id: normalizeSessionId(command.session_id),
    command_id: normalizeCommandId(command.command_id),
    actor: {
      tenant_id: actor.tenant_id,
      user_id: actor.user_id,
      request_id: actor.request_id,
    },
    payload: requirePlainObject(payload, 'payload'),
  };
}
