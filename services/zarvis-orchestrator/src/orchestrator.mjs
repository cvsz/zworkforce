import { createHash, randomUUID } from 'node:crypto';
import {
  COMMAND_COMPLETED_SCHEMA,
  createSessionEvent,
  createToolAuditEvent,
  IdempotencyConflictError,
  normalizeActorContext,
  normalizeCommandRequest,
  resolveCommandIntent,
} from './contracts.mjs';
import {
  executeGitHubRepositoryStatus,
  GITHUB_REPOSITORY_STATUS_TOOL,
} from './github-status-tool.mjs';
import { createMemorySessionStore } from './session-store.mjs';

export const AVAILABLE_TOOLS = Object.freeze([GITHUB_REPOSITORY_STATUS_TOOL]);

function formatDate(value, locale) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat(locale, {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'UTC',
  }).format(date);
}

function commandFingerprint(command) {
  return createHash('sha256').update(JSON.stringify(command)).digest('hex');
}

function assertMatchingFingerprint(envelope, fingerprint) {
  if (envelope.fingerprint !== fingerprint) throw new IdempotencyConflictError();
}

export function createRepositoryStatusSpeech(repository, locale = 'th-TH') {
  const isThai = locale.toLowerCase().startsWith('th');
  const lastPush = formatDate(repository.pushed_at, locale);

  if (isThai) {
    const visibility = repository.private ? 'ส่วนตัว' : 'สาธารณะ';
    const lifecycle = repository.archived ? 'และถูกเก็บถาวรแล้ว' : 'และยังเปิดใช้งานอยู่';
    return `คลัง ${repository.full_name} เป็นคลัง${visibility} ${lifecycle} ใช้สาขาหลัก ${repository.default_branch} มี issues และ pull requests ที่เปิดรวม ${repository.open_issues_count} รายการ และมีการ push ล่าสุดเมื่อ ${lastPush} ตามเวลา UTC`;
  }

  const visibility = repository.private ? 'private' : 'public';
  const lifecycle = repository.archived ? 'archived' : 'active';
  return `${repository.full_name} is a ${visibility}, ${lifecycle} repository. Its default branch is ${repository.default_branch}. It has ${repository.open_issues_count} open issues and pull requests, and the latest push was ${lastPush} UTC.`;
}

export class ZarvisOrchestrator {
  constructor({
    githubStatusExecutor = executeGitHubRepositoryStatus,
    auditSink = async () => {},
    sessionStore = createMemorySessionStore(),
    now = () => new Date(),
    idFactory = randomUUID,
  } = {}) {
    this.githubStatusExecutor = githubStatusExecutor;
    this.auditSink = auditSink;
    this.sessionStore = sessionStore;
    this.now = now;
    this.idFactory = idFactory;
    this.inflight = new Map();
  }

  async execute(rawCommand, rawContext = {}) {
    const command = normalizeCommandRequest(rawCommand);
    const actor = normalizeActorContext(rawContext);
    const fingerprint = commandFingerprint(command);

    const cached = await this.sessionStore.getCommandResult(command.command_id);
    if (cached) {
      assertMatchingFingerprint(cached, fingerprint);
      return { ...cached.result, replayed: true };
    }

    const pending = this.inflight.get(command.command_id);
    if (pending) {
      const envelope = await pending;
      assertMatchingFingerprint(envelope, fingerprint);
      return { ...envelope.result, replayed: true };
    }

    const execution = this.executeNew(command, actor, fingerprint).then(
      (envelope) => envelope,
      (error) => { throw error; },
    );
    this.inflight.set(command.command_id, execution);
    try {
      const envelope = await execution;
      return envelope.result;
    } finally {
      if (this.inflight.get(command.command_id) === execution) {
        this.inflight.delete(command.command_id);
      }
    }
  }

  async executeNew(command, actor, fingerprint) {
    const intent = resolveCommandIntent(command);
    const startedAt = performance.now();

    await this.sessionStore.appendEvent(createSessionEvent({
      eventType: 'command.accepted',
      command,
      actor,
      payload: {
        input: command.input,
        ...(command.tool ? { tool: command.tool } : {}),
      },
      now: this.now,
      eventId: this.idFactory(),
    }));

    try {
      let toolResult;
      if (intent.name === 'github.repository.status') {
        toolResult = await this.githubStatusExecutor(intent.arguments);
      } else {
        throw new Error(`Unregistered tool: ${intent.name}`);
      }

      const durationMs = performance.now() - startedAt;
      const audit = createToolAuditEvent({
        command,
        actor,
        intent,
        outcome: 'succeeded',
        durationMs,
        resultSummary: {
          repository: toolResult.full_name,
          visibility: toolResult.visibility,
          default_branch: toolResult.default_branch,
          open_issues_count: toolResult.open_issues_count,
        },
        now: this.now,
        eventId: this.idFactory(),
      });
      await this.auditSink(audit);

      const result = {
        schema_version: COMMAND_COMPLETED_SCHEMA,
        command_id: command.command_id,
        session_id: command.session_id,
        completed_at: this.now().toISOString(),
        status: 'completed',
        replayed: false,
        intent: {
          name: intent.name,
          source: intent.source,
        },
        result: toolResult,
        speech: {
          locale: command.input.locale,
          text: createRepositoryStatusSpeech(toolResult, command.input.locale),
        },
        audit: {
          event_id: audit.event_id,
          schema_version: audit.schema_version,
        },
      };

      await this.sessionStore.appendEvent(createSessionEvent({
        eventType: 'command.completed',
        command,
        actor,
        payload: {
          status: result.status,
          intent: result.intent,
          speech: result.speech,
          audit: result.audit,
          result_summary: audit.result_summary,
        },
        now: this.now,
        eventId: this.idFactory(),
      }));

      const envelope = { fingerprint, result };
      const stored = await this.sessionStore.putCommandResult(command.command_id, envelope);
      assertMatchingFingerprint(stored, fingerprint);
      return stored;
    } catch (error) {
      const durationMs = performance.now() - startedAt;
      const audit = createToolAuditEvent({
        command,
        actor,
        intent,
        outcome: 'failed',
        durationMs,
        errorCode: error?.code ?? 'tool_execution_failed',
        now: this.now,
        eventId: this.idFactory(),
      });

      try {
        await this.auditSink(audit);
      } catch {
        // Preserve the original tool failure. Audit sink failures are reported by the sink itself.
      }

      try {
        await this.sessionStore.appendEvent(createSessionEvent({
          eventType: 'command.failed',
          command,
          actor,
          payload: {
            status: 'failed',
            intent: { name: intent.name, source: intent.source },
            error: { code: error?.code ?? 'tool_execution_failed' },
            audit: { event_id: audit.event_id, schema_version: audit.schema_version },
          },
          now: this.now,
          eventId: this.idFactory(),
        }));
      } catch {
        // Preserve the original tool failure.
      }
      throw error;
    }
  }

  async getSession(sessionId, options = {}) {
    return this.sessionStore.readSession(sessionId, options);
  }

  async deleteSession(sessionId) {
    return this.sessionStore.deleteSession(sessionId);
  }
}
