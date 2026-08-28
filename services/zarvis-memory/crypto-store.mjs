import { createCipheriv, createDecipheriv, randomBytes, randomUUID } from "node:crypto";
import { createReadStream } from "node:fs";
import { mkdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { createInterface } from "node:readline";
import { resolve } from "node:path";

const JOURNAL_VERSION = "zarvis.memory.encrypted.v1";
const AAD = Buffer.from("z-platform:zarvis-memory:v1", "utf8");
const MAX_ENVELOPE_BYTES = 128 * 1024;

function isNotFound(error) {
  return error?.code === "ENOENT";
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

function validateEvent(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Memory event is invalid");
  }
  if (typeof value.event_type !== "string" || typeof value.event_id !== "string") {
    throw new Error("Memory event envelope is invalid");
  }
  return value;
}

export function parseMemoryMasterKey(value) {
  if (typeof value !== "string" || !/^[A-Za-z0-9+/]+={0,2}$/.test(value.trim())) {
    throw new Error("ZARVIS_MEMORY_MASTER_KEY_B64 must be valid base64");
  }
  const key = Buffer.from(value.trim(), "base64");
  if (key.length !== 32) {
    throw new Error("ZARVIS_MEMORY_MASTER_KEY_B64 must decode to exactly 32 bytes");
  }
  return key;
}

function encryptEvent(event, key) {
  const plaintext = Buffer.from(JSON.stringify(validateEvent(event)), "utf8");
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  cipher.setAAD(AAD);
  const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  const envelope = {
    version: JOURNAL_VERSION,
    iv: iv.toString("base64"),
    ciphertext: ciphertext.toString("base64"),
    auth_tag: cipher.getAuthTag().toString("base64"),
  };
  const line = `${JSON.stringify(envelope)}\n`;
  if (Buffer.byteLength(line) > MAX_ENVELOPE_BYTES) {
    throw new Error(`Encrypted memory event exceeds ${MAX_ENVELOPE_BYTES} bytes`);
  }
  return line;
}

function decryptEnvelope(envelope, key) {
  if (!envelope || envelope.version !== JOURNAL_VERSION) {
    throw new Error("Encrypted memory envelope is invalid");
  }
  const decipher = createDecipheriv(
    "aes-256-gcm",
    key,
    Buffer.from(envelope.iv, "base64"),
  );
  decipher.setAAD(AAD);
  decipher.setAuthTag(Buffer.from(envelope.auth_tag, "base64"));
  const plaintext = Buffer.concat([
    decipher.update(Buffer.from(envelope.ciphertext, "base64")),
    decipher.final(),
  ]);
  return validateEvent(JSON.parse(plaintext.toString("utf8")));
}

async function atomicReplace(path, content) {
  const temporary = `${path}.${process.pid}.${randomUUID()}.tmp`;
  try {
    await writeFile(temporary, content, {
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

export class EncryptedMemoryStore {
  constructor({
    rootDir = process.env.ZARVIS_MEMORY_DATA_DIR ?? "./data/zarvis-memory",
    masterKey = parseMemoryMasterKey(process.env.ZARVIS_MEMORY_MASTER_KEY_B64),
  } = {}) {
    this.rootDir = resolve(rootDir);
    this.journalPath = resolve(this.rootDir, "memory-events.enc.jsonl");
    this.masterKey = Buffer.from(masterKey);
    if (this.masterKey.length !== 32) throw new Error("Memory master key must contain 32 bytes");
    this.writes = new SerializedWrites();
  }

  async ensureDirectory() {
    await mkdir(this.rootDir, { recursive: true, mode: 0o700 });
  }

  async readEventsUnlocked() {
    if (!await fileExists(this.journalPath)) return [];
    const events = [];
    const reader = createInterface({
      input: createReadStream(this.journalPath, { encoding: "utf8" }),
      crlfDelay: Infinity,
    });
    for await (const line of reader) {
      if (!line.trim()) continue;
      if (Buffer.byteLength(line) > MAX_ENVELOPE_BYTES) {
        throw new Error("Encrypted memory envelope exceeds the supported size");
      }
      events.push(decryptEnvelope(JSON.parse(line), this.masterKey));
    }
    return events;
  }

  async readEvents() {
    await this.writes.settled();
    return this.readEventsUnlocked();
  }

  async append(event) {
    const line = encryptEvent(event, this.masterKey);
    return this.writes.run(async () => {
      await this.ensureDirectory();
      await writeFile(this.journalPath, line, {
        encoding: "utf8",
        flag: "a",
        mode: 0o600,
      });
      return structuredClone(event);
    });
  }

  async compact(predicate) {
    return this.writes.run(async () => {
      await this.ensureDirectory();
      const events = await this.readEventsUnlocked();
      const kept = events.filter(predicate);
      const content = kept.map((event) => encryptEvent(event, this.masterKey)).join("");
      await atomicReplace(this.journalPath, content);
      return { removed: events.length - kept.length, kept: kept.length };
    });
  }

  async rawJournalTextForTest() {
    await this.writes.settled();
    try {
      return await readFile(this.journalPath, "utf8");
    } catch (error) {
      if (isNotFound(error)) return "";
      throw error;
    }
  }
}
