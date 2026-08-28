import { randomUUID } from "node:crypto";
import {
  mkdir,
  readFile,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { resolve } from "node:path";

const MAX_RECORD_BYTES = 1024 * 1024;
const MAX_QUEUE_BYTES = 4 * 1024 * 1024;

function isNotFound(error) {
  return error?.code === "ENOENT";
}

function serializeLine(value, description) {
  const serialized = JSON.stringify(value);
  if (Buffer.byteLength(serialized) > MAX_RECORD_BYTES) {
    throw new Error(`${description} exceeds ${MAX_RECORD_BYTES} bytes`);
  }
  return `${serialized}\n`;
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

async function atomicWrite(path, value) {
  const serialized = JSON.stringify(value);
  if (Buffer.byteLength(serialized) > MAX_QUEUE_BYTES) {
    throw new Error(`Durable queue state exceeds ${MAX_QUEUE_BYTES} bytes`);
  }
  const temporary = `${path}.${process.pid}.${randomUUID()}.tmp`;
  try {
    await writeFile(temporary, serialized, {
      encoding: "utf8",
      flag: "wx",
      mode: 0o600,
    });
    await rename(temporary, path);
  } finally {
    await rm(temporary, { force: true });
  }
}

class SerializedWrites {
  constructor() {
    this.chain = Promise.resolve();
  }

  run(operation) {
    const result = this.chain.then(operation);
    this.chain = result.then(() => undefined, () => undefined);
    return result;
  }

  async settled() {
    await this.chain;
  }
}

export class FileJobStore {
  constructor({ rootDir = process.env.AGENT_DATA_DIR ?? "./data/agent-orchestrator" } = {}) {
    this.rootDir = resolve(rootDir);
    this.path = resolve(this.rootDir, "jobs.jsonl");
    this.writes = new SerializedWrites();
  }

  async ensureDirectory() {
    await mkdir(this.rootDir, { recursive: true, mode: 0o700 });
  }

  async snapshots() {
    await this.writes.settled();
    if (!await fileExists(this.path)) return new Map();
    const text = await readFile(this.path, "utf8");
    const jobs = new Map();
    for (const line of text.split("\n")) {
      if (!line.trim()) continue;
      if (Buffer.byteLength(line) > MAX_RECORD_BYTES) {
        throw new Error(`Stored job record exceeds ${MAX_RECORD_BYTES} bytes`);
      }
      const job = JSON.parse(line);
      if (!job || typeof job.id !== "string" || typeof job.tenant_id !== "string") {
        throw new Error("Stored job record is invalid");
      }
      jobs.set(job.id, job);
    }
    return jobs;
  }

  async findById(id) {
    return structuredClone((await this.snapshots()).get(id) ?? null);
  }

  async findByIdempotency(tenantId, idempotencyKey) {
    const jobs = await this.snapshots();
    const found = [...jobs.values()].find(
      (job) => job.tenant_id === tenantId && job.idempotency_key === idempotencyKey,
    );
    return structuredClone(found ?? null);
  }

  async listByTenant(tenantId) {
    const jobs = [...(await this.snapshots()).values()]
      .filter((job) => job.tenant_id === tenantId)
      .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
    return structuredClone(jobs);
  }

  async save(job) {
    const line = serializeLine(job, "Job record");
    return this.writes.run(async () => {
      await this.ensureDirectory();
      await writeFile(this.path, line, {
        encoding: "utf8",
        flag: "a",
        mode: 0o600,
      });
      return structuredClone(job);
    });
  }
}

export class FileQueueAdapter {
  constructor({ rootDir = process.env.AGENT_DATA_DIR ?? "./data/agent-orchestrator" } = {}) {
    this.rootDir = resolve(rootDir);
    this.path = resolve(this.rootDir, "queue.json");
    this.writes = new SerializedWrites();
  }

  async ensureDirectory() {
    await mkdir(this.rootDir, { recursive: true, mode: 0o700 });
  }

  async readQueue() {
    if (!await fileExists(this.path)) return [];
    const text = await readFile(this.path, "utf8");
    if (Buffer.byteLength(text) > MAX_QUEUE_BYTES) {
      throw new Error(`Durable queue state exceeds ${MAX_QUEUE_BYTES} bytes`);
    }
    const value = JSON.parse(text);
    if (!Array.isArray(value)) throw new Error("Durable queue state is invalid");
    return value;
  }

  async enqueue(item) {
    return this.writes.run(async () => {
      await this.ensureDirectory();
      const queue = await this.readQueue();
      if (!queue.some((queued) => queued.job_id === item.job_id && queued.attempt === item.attempt)) {
        queue.push(structuredClone(item));
        await atomicWrite(this.path, queue);
      }
      return structuredClone(item);
    });
  }

  async dequeue() {
    return this.writes.run(async () => {
      await this.ensureDirectory();
      const queue = await this.readQueue();
      const item = queue.shift() ?? null;
      await atomicWrite(this.path, queue);
      return structuredClone(item);
    });
  }

  async size() {
    await this.writes.settled();
    return (await this.readQueue()).length;
  }
}

export class FileAuditSink {
  constructor({ rootDir = process.env.AGENT_DATA_DIR ?? "./data/agent-orchestrator" } = {}) {
    this.rootDir = resolve(rootDir);
    this.path = resolve(this.rootDir, "audit-events.jsonl");
    this.writes = new SerializedWrites();
  }

  async emit(event) {
    const line = serializeLine(event, "Audit event");
    return this.writes.run(async () => {
      await mkdir(this.rootDir, { recursive: true, mode: 0o700 });
      await writeFile(this.path, line, {
        encoding: "utf8",
        flag: "a",
        mode: 0o600,
      });
      return structuredClone(event);
    });
  }

  async list() {
    await this.writes.settled();
    if (!await fileExists(this.path)) return [];
    const text = await readFile(this.path, "utf8");
    return text.split("\n").filter(Boolean).map((line) => JSON.parse(line));
  }
}

export function createDurableFileProviders({
  rootDir = process.env.AGENT_DATA_DIR ?? "./data/agent-orchestrator",
} = {}) {
  return {
    store: new FileJobStore({ rootDir }),
    queue: new FileQueueAdapter({ rootDir }),
    audit: new FileAuditSink({ rootDir }),
  };
}
