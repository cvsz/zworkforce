import { createReadStream } from 'node:fs';
import {
  mkdir,
  rename,
  rm,
  stat,
  writeFile,
} from 'node:fs/promises';
import { createInterface } from 'node:readline';
import { resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
import { normalizeCommandId, normalizeSessionId } from './contracts.mjs';

const MAX_RESULT_BYTES = 1024 * 1024;
const MAX_EVENT_BYTES = 64 * 1024;

function isNotFound(error) {
  return error?.code === 'ENOENT';
}

function serializeLine(value, maxBytes, description) {
  const serialized = JSON.stringify(value);
  if (Buffer.byteLength(serialized) > maxBytes) {
    throw new Error(`${description} exceeds ${maxBytes} bytes.`);
  }
  return `${serialized}\n`;
}

function safeResultEnvelope(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Stored command result envelope is invalid.');
  }
  if (typeof value.fingerprint !== 'string' || !value.result || typeof value.result !== 'object') {
    throw new Error('Stored command result envelope is invalid.');
  }
  return value;
}

function safeCommandRecord(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Stored command record is invalid.');
  }
  return {
    command_id: normalizeCommandId(value.command_id),
    envelope: safeResultEnvelope(value.envelope),
  };
}

async function fileExists(path) {
  try {
    await stat(path);
    return true;
  } catch (error) {
    if (isNotFound(error)) return false;
    throw error;
  }
}

async function* readJsonLines(path, maxBytes) {
  if (!await fileExists(path)) return;

  const reader = createInterface({
    input: createReadStream(path, { encoding: 'utf8' }),
    crlfDelay: Infinity,
  });

  for await (const line of reader) {
    if (!line.trim()) continue;
    if (Buffer.byteLength(line) > maxBytes) {
      throw new Error(`Stored journal record exceeds ${maxBytes} bytes.`);
    }
    yield JSON.parse(line);
  }
}

async function atomicReplace(path, lines) {
  const temporary = `${path}.${process.pid}.${randomUUID()}.tmp`;
  try {
    await writeFile(temporary, lines.join(''), {
      encoding: 'utf8',
      flag: 'wx',
      mode: 0o600,
    });
    await rename(temporary, path);
  } finally {
    await rm(temporary, { force: true });
  }
}

export class FileSessionStore {
  constructor({ rootDir = process.env.ZARVIS_DATA_DIR ?? './data/zarvis' } = {}) {
    this.rootDir = resolve(rootDir);
    this.sessionJournalPath = resolve(this.rootDir, 'session-events.jsonl');
    this.commandJournalPath = resolve(this.rootDir, 'command-results.jsonl');
    this.writeChain = Promise.resolve();
  }

  async ensureDirectory() {
    await mkdir(this.rootDir, { recursive: true, mode: 0o700 });
  }

  runExclusive(operation) {
    const result = this.writeChain.then(operation);
    this.writeChain = result.then(() => undefined, () => undefined);
    return result;
  }

  async appendEvent(event) {
    const sessionId = normalizeSessionId(event?.session_id);
    const commandId = normalizeCommandId(event?.command_id);
    const normalizedEvent = {
      ...event,
      session_id: sessionId,
      command_id: commandId,
    };
    const line = serializeLine(normalizedEvent, MAX_EVENT_BYTES, 'Session event');

    return this.runExclusive(async () => {
      await this.ensureDirectory();
      await writeFile(this.sessionJournalPath, line, {
        encoding: 'utf8',
        flag: 'a',
        mode: 0o600,
      });
    });
  }

  async findCommandResult(commandId) {
    const normalizedCommandId = normalizeCommandId(commandId);
    let found = null;
    for await (const value of readJsonLines(this.commandJournalPath, MAX_RESULT_BYTES)) {
      const record = safeCommandRecord(value);
      if (record.command_id === normalizedCommandId) found = record.envelope;
    }
    return found;
  }

  async getCommandResult(commandId) {
    await this.writeChain;
    return this.findCommandResult(commandId);
  }

  async putCommandResult(commandId, envelope) {
    const normalizedCommandId = normalizeCommandId(commandId);
    safeResultEnvelope(envelope);

    return this.runExclusive(async () => {
      await this.ensureDirectory();
      const existing = await this.findCommandResult(normalizedCommandId);
      if (existing) return existing;

      const record = { command_id: normalizedCommandId, envelope };
      const line = serializeLine(record, MAX_RESULT_BYTES, 'Command result');
      await writeFile(this.commandJournalPath, line, {
        encoding: 'utf8',
        flag: 'a',
        mode: 0o600,
      });
      return envelope;
    });
  }

  async readSession(sessionId, { limit = 100 } = {}) {
    const normalizedSessionId = normalizeSessionId(sessionId);
    const normalizedLimit = Number(limit);
    if (!Number.isInteger(normalizedLimit) || normalizedLimit < 1 || normalizedLimit > 500) {
      throw new Error('Session event limit must be an integer between 1 and 500.');
    }

    await this.writeChain;
    const events = [];
    for await (const event of readJsonLines(this.sessionJournalPath, MAX_EVENT_BYTES)) {
      if (normalizeSessionId(event?.session_id) !== normalizedSessionId) continue;
      events.push(event);
      if (events.length > normalizedLimit) events.shift();
    }

    return { session_id: normalizedSessionId, events };
  }

  async deleteSession(sessionId) {
    const normalizedSessionId = normalizeSessionId(sessionId);

    return this.runExclusive(async () => {
      await this.ensureDirectory();
      const keptEvents = [];
      const commandIds = new Set();
      let sessionDeleted = false;

      for await (const event of readJsonLines(this.sessionJournalPath, MAX_EVENT_BYTES)) {
        if (normalizeSessionId(event?.session_id) === normalizedSessionId) {
          sessionDeleted = true;
          if (event?.command_id) commandIds.add(normalizeCommandId(event.command_id));
          continue;
        }
        keptEvents.push(serializeLine(event, MAX_EVENT_BYTES, 'Session event'));
      }

      if (!sessionDeleted) {
        return {
          session_id: normalizedSessionId,
          deleted: false,
          command_results_deleted: 0,
        };
      }

      const keptCommands = [];
      let commandResultsDeleted = 0;
      for await (const value of readJsonLines(this.commandJournalPath, MAX_RESULT_BYTES)) {
        const record = safeCommandRecord(value);
        if (commandIds.has(record.command_id)) {
          commandResultsDeleted += 1;
          continue;
        }
        keptCommands.push(serializeLine(record, MAX_RESULT_BYTES, 'Command result'));
      }

      await atomicReplace(this.sessionJournalPath, keptEvents);
      await atomicReplace(this.commandJournalPath, keptCommands);

      return {
        session_id: normalizedSessionId,
        deleted: true,
        command_results_deleted: commandResultsDeleted,
      };
    });
  }
}

export function createMemorySessionStore() {
  const sessions = new Map();
  const commands = new Map();

  return {
    async appendEvent(event) {
      const sessionId = normalizeSessionId(event?.session_id);
      const events = sessions.get(sessionId) ?? [];
      events.push(structuredClone(event));
      sessions.set(sessionId, events);
    },
    async getCommandResult(commandId) {
      const value = commands.get(normalizeCommandId(commandId));
      return value ? structuredClone(value) : null;
    },
    async putCommandResult(commandId, envelope) {
      const id = normalizeCommandId(commandId);
      if (!commands.has(id)) commands.set(id, structuredClone(envelope));
      return structuredClone(commands.get(id));
    },
    async readSession(sessionId, { limit = 100 } = {}) {
      const id = normalizeSessionId(sessionId);
      const normalizedLimit = Number(limit);
      if (!Number.isInteger(normalizedLimit) || normalizedLimit < 1 || normalizedLimit > 500) {
        throw new Error('Session event limit must be an integer between 1 and 500.');
      }
      const events = sessions.get(id) ?? [];
      return { session_id: id, events: structuredClone(events.slice(-normalizedLimit)) };
    },
    async deleteSession(sessionId) {
      const id = normalizeSessionId(sessionId);
      const events = sessions.get(id) ?? [];
      const commandIds = new Set(events.map((event) => event.command_id).filter(Boolean));
      const deleted = sessions.delete(id);
      let commandResultsDeleted = 0;
      for (const commandId of commandIds) {
        if (commands.delete(commandId)) commandResultsDeleted += 1;
      }
      return {
        session_id: id,
        deleted,
        command_results_deleted: commandResultsDeleted,
      };
    },
  };
}
