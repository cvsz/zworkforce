import { createCipheriv, createDecipheriv, randomBytes, randomUUID } from "node:crypto";
import { createReadStream } from "node:fs";
import { mkdir, rename, rm, stat, writeFile } from "node:fs/promises";
import { createInterface } from "node:readline";
import { resolve } from "node:path";

const AAD = Buffer.from("z-platform:zarvis-perception:v1", "utf8");
const ENVELOPE_VERSION = "zarvis.perception.encrypted.v1";
const MAX_EVENT_BYTES = 512 * 1024;

function isNotFound(error) { return error?.code === "ENOENT"; }

async function exists(path) {
  try { await stat(path); return true; }
  catch (error) { if (isNotFound(error)) return false; throw error; }
}

export function parsePerceptionKey(value) {
  if (typeof value !== "string" || !/^[A-Za-z0-9+/]+={0,2}$/.test(value.trim())) {
    throw new Error("ZARVIS_PERCEPTION_MASTER_KEY_B64 must be valid base64");
  }
  const key = Buffer.from(value.trim(), "base64");
  if (key.length !== 32) throw new Error("ZARVIS_PERCEPTION_MASTER_KEY_B64 must decode to exactly 32 bytes");
  return key;
}

function validateEvent(event) {
  if (!event || typeof event !== "object" || Array.isArray(event)) throw new Error("Perception event is invalid");
  if (typeof event.event_id !== "string" || typeof event.event_type !== "string") throw new Error("Perception event envelope is invalid");
  return event;
}

function encrypt(event, key) {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  cipher.setAAD(AAD);
  const ciphertext = Buffer.concat([cipher.update(Buffer.from(JSON.stringify(validateEvent(event)))), cipher.final()]);
  const line = `${JSON.stringify({
    version: ENVELOPE_VERSION,
    iv: iv.toString("base64"),
    ciphertext: ciphertext.toString("base64"),
    auth_tag: cipher.getAuthTag().toString("base64"),
  })}\n`;
  if (Buffer.byteLength(line) > MAX_EVENT_BYTES) throw new Error("Encrypted perception event is too large");
  return line;
}

function decrypt(envelope, key) {
  if (!envelope || envelope.version !== ENVELOPE_VERSION) throw new Error("Encrypted perception envelope is invalid");
  const decipher = createDecipheriv("aes-256-gcm", key, Buffer.from(envelope.iv, "base64"));
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
    await writeFile(temporary, content, { encoding: "utf8", flag: "wx", mode: 0o600 });
    await rename(temporary, path);
  } finally { await rm(temporary, { force: true }); }
}

export class EncryptedPerceptionStore {
  constructor({
    rootDir = process.env.ZARVIS_PERCEPTION_DATA_DIR ?? "./data/zarvis-perception",
    masterKey = parsePerceptionKey(process.env.ZARVIS_PERCEPTION_MASTER_KEY_B64),
  } = {}) {
    this.rootDir = resolve(rootDir);
    this.path = resolve(this.rootDir, "perception-events.enc.jsonl");
    this.key = Buffer.from(masterKey);
    if (this.key.length !== 32) throw new Error("Perception master key must contain 32 bytes");
    this.chain = Promise.resolve();
  }

  run(operation) {
    const result = this.chain.then(operation);
    this.chain = result.then(() => undefined, () => undefined);
    return result;
  }

  async readUnlocked() {
    if (!await exists(this.path)) return [];
    const events = [];
    const reader = createInterface({ input: createReadStream(this.path, { encoding: "utf8" }), crlfDelay: Infinity });
    for await (const line of reader) {
      if (!line.trim()) continue;
      if (Buffer.byteLength(line) > MAX_EVENT_BYTES) throw new Error("Encrypted perception envelope is too large");
      events.push(decrypt(JSON.parse(line), this.key));
    }
    return events;
  }

  async readEvents() { await this.chain; return this.readUnlocked(); }

  async append(event) {
    const line = encrypt(event, this.key);
    return this.run(async () => {
      await mkdir(this.rootDir, { recursive: true, mode: 0o700 });
      await writeFile(this.path, line, { encoding: "utf8", flag: "a", mode: 0o600 });
      return structuredClone(event);
    });
  }

  async compact(predicate) {
    return this.run(async () => {
      await mkdir(this.rootDir, { recursive: true, mode: 0o700 });
      const events = await this.readUnlocked();
      const kept = events.filter(predicate);
      await atomicReplace(this.path, kept.map((event) => encrypt(event, this.key)).join(""));
      return { removed: events.length - kept.length, kept: kept.length };
    });
  }
}
