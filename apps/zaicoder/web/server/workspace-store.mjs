import { mkdir, open, readdir, readFile, rm } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { isAbsolute, relative, resolve } from "node:path";

const DEFAULT_RETENTION_DAYS = 30;
const MAX_RETENTION_DAYS = 365;
const WORKSPACE_ID = /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$/;

export class WorkspaceStoreError extends Error {}

function normalizeRetentionDays(value) {
  const days = Number(value ?? DEFAULT_RETENTION_DAYS);
  if (!Number.isInteger(days) || days < 1 || days > MAX_RETENTION_DAYS) {
    throw new WorkspaceStoreError("retention_days must be an integer between 1 and 365");
  }
  return days;
}

function normalizeWorkspaceId(value, idGenerator) {
  const id = typeof value === "string" && value.trim() ? value.trim() : idGenerator();
  if (!WORKSPACE_ID.test(id)) throw new WorkspaceStoreError("workspace_id is invalid");
  return id;
}

function normalizeOwner(value) {
  const owner = typeof value === "string" && value.trim() ? value.trim() : "local";
  if (owner.length > 128) throw new WorkspaceStoreError("workspace owner is too long");
  return owner;
}

function expiresAt(now, retentionDays) {
  return new Date(new Date(now).getTime() + retentionDays * 24 * 60 * 60 * 1000).toISOString();
}

function validateWorkspaceId(id) {
  if (!WORKSPACE_ID.test(id)) throw new WorkspaceStoreError("workspace_id is invalid");
}

function assertOwner(record, owner) {
  if (!owner) return;
  if (record?.owner !== normalizeOwner(owner)) throw new WorkspaceStoreError("workspace owner mismatch");
}

export class FileWorkspaceAdapter {
  constructor({ root = process.env.ZAICODER_WORKSPACE_STORE || ".zaicoder-workspaces" } = {}) {
    this.root = resolve(root);
  }

  pathFor(id) {
    validateWorkspaceId(id);
    const candidate = resolve(this.root, `${id}.json`);
    const relativePath = relative(this.root, candidate);
    if (!relativePath || relativePath.startsWith("..") || isAbsolute(relativePath)) {
      throw new WorkspaceStoreError("workspace path escapes configured root");
    }
    return candidate;
  }

  async listIds() {
    try {
      const entries = await readdir(this.root, { withFileTypes: true });
      return entries
        .filter((entry) => entry.isFile() && entry.name.endsWith(".json"))
        .map((entry) => entry.name.slice(0, -5))
        .filter((id) => WORKSPACE_ID.test(id))
        .sort();
    } catch (error) {
      if (error?.code === "ENOENT") return [];
      throw error;
    }
  }

  async read(id) {
    try {
      return JSON.parse(await readFile(this.pathFor(id), "utf8"));
    } catch (error) {
      if (error?.code === "ENOENT") return null;
      throw error;
    }
  }

  async save(record) {
    await mkdir(this.root, { recursive: true });
    const handle = await open(this.pathFor(record.id), "w", 0o600);
    try {
      await handle.writeFile(JSON.stringify(record, null, 2) + "\n", "utf8");
    } finally {
      await handle.close();
    }
    return record;
  }

  async delete(id) {
    await rm(this.pathFor(id), { force: true });
  }
}

function normalizeBaseUrl(value) {
  if (typeof value !== "string" || !value.trim()) throw new WorkspaceStoreError("workspace metadata url is required");
  const url = new URL(value);
  if (!["http:", "https:"].includes(url.protocol)) throw new WorkspaceStoreError("workspace metadata url must be http or https");
  return url.toString().replace(/\/$/, "");
}

function encodeWorkspaceId(id) {
  validateWorkspaceId(id);
  return encodeURIComponent(id);
}

export class HttpWorkspaceAdapter {
  constructor({ baseUrl = process.env.ZAICODER_WORKSPACE_METADATA_URL, token = process.env.Z_PLATFORM_SERVICE_TOKEN, fetchFn = globalThis.fetch, timeoutMs = Number(process.env.ZAICODER_WORKSPACE_METADATA_TIMEOUT_MS || 5000) } = {}) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    this.token = token;
    this.fetchFn = fetchFn;
    this.timeoutMs = timeoutMs;
    if (typeof this.fetchFn !== "function") throw new WorkspaceStoreError("workspace metadata fetch implementation is unavailable");
  }

  headers(extra = {}) {
    return {
      Accept: "application/json",
      ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
      ...extra,
    };
  }

  async request(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetchFn(`${this.baseUrl}${path}`, { ...options, headers: this.headers(options.headers), signal: controller.signal });
      if (response.status === 404) return null;
      if (!response.ok) {
        let message = `workspace metadata request failed with status ${response.status}`;
        try {
          const body = await response.json();
          if (body?.error) message = body.error;
        } catch {}
        throw new WorkspaceStoreError(message);
      }
      if (response.status === 204) return null;
      return response.json();
    } catch (error) {
      if (error?.name === "AbortError") throw new WorkspaceStoreError("workspace metadata request timed out");
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }

  async listIds() {
    const payload = await this.request("/workspaces");
    if (!Array.isArray(payload?.ids)) throw new WorkspaceStoreError("workspace metadata list response is invalid");
    return payload.ids.filter((id) => WORKSPACE_ID.test(id)).sort();
  }

  async read(id) {
    return this.request(`/workspaces/${encodeWorkspaceId(id)}`);
  }

  async save(record) {
    validateWorkspaceId(record.id);
    return this.request(`/workspaces/${encodeWorkspaceId(record.id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(record),
    });
  }

  async delete(id) {
    await this.request(`/workspaces/${encodeWorkspaceId(id)}`, { method: "DELETE" });
  }
}

export function createWorkspaceAdapterFromEnv(env = process.env) {
  const kind = (env.ZAICODER_WORKSPACE_ADAPTER || "file").toLowerCase();
  if (kind === "file") return new FileWorkspaceAdapter({ root: env.ZAICODER_WORKSPACE_STORE || ".zaicoder-workspaces" });
  if (kind === "http") {
    return new HttpWorkspaceAdapter({
      baseUrl: env.ZAICODER_WORKSPACE_METADATA_URL,
      token: env.Z_PLATFORM_SERVICE_TOKEN,
      timeoutMs: Number(env.ZAICODER_WORKSPACE_METADATA_TIMEOUT_MS || 5000),
    });
  }
  throw new WorkspaceStoreError("unsupported workspace adapter");
}

export function createWorkspaceStoreFromEnv(env = process.env) {
  return new WorkspaceStore({ adapter: createWorkspaceAdapterFromEnv(env) });
}

export class WorkspaceStore {
  constructor({ root = process.env.ZAICODER_WORKSPACE_STORE || ".zaicoder-workspaces", adapter, idGenerator = randomUUID, now = () => new Date().toISOString() } = {}) {
    this.adapter = adapter || new FileWorkspaceAdapter({ root });
    this.idGenerator = idGenerator;
    this.now = now;
  }

  async read(id, options = {}) {
    validateWorkspaceId(id);
    const record = await this.adapter.read(id);
    if (!record) return null;
    assertOwner(record, options.owner);
    return record;
  }

  async save(record) {
    return this.adapter.save(record);
  }

  async ensure(input = {}) {
    const now = this.now();
    const id = normalizeWorkspaceId(input.workspace_id, this.idGenerator);
    const existing = await this.read(id, input.owner ? { owner: input.owner } : {});
    if (existing) {
      const retentionDays = normalizeRetentionDays(input.retention_days ?? existing.retention_days);
      return this.save({
        ...existing,
        owner: normalizeOwner(input.owner ?? existing.owner),
        retention_days: retentionDays,
        expires_at: expiresAt(now, retentionDays),
        updated_at: now,
      });
    }

    const retentionDays = normalizeRetentionDays(input.retention_days);
    return this.save({
      id,
      owner: normalizeOwner(input.owner),
      retention_days: retentionDays,
      created_at: now,
      updated_at: now,
      expires_at: expiresAt(now, retentionDays),
      files: [],
    });
  }

  async addFile(workspaceId, file, options = {}) {
    const workspace = await this.ensure({ workspace_id: workspaceId, owner: options.owner });
    const now = this.now();
    const next = {
      ...workspace,
      files: [...workspace.files.filter((item) => item.id !== file.id), { id: file.id, name: file.name, size_bytes: file.size_bytes, added_at: now }],
      updated_at: now,
    };
    return this.save(next);
  }

  async listIds() {
    if (typeof this.adapter.listIds !== "function") throw new WorkspaceStoreError("workspace adapter does not support listing");
    return this.adapter.listIds();
  }

  async cleanupExpired(ids) {
    const workspaceIds = ids === undefined ? await this.listIds() : ids;
    if (!Array.isArray(workspaceIds)) throw new WorkspaceStoreError("cleanupExpired requires an explicit workspace id list");
    const now = new Date(this.now()).getTime();
    const removed = [];
    for (const id of workspaceIds) {
      validateWorkspaceId(id);
      const record = await this.adapter.read(id);
      if (!record) continue;
      if (new Date(record.expires_at).getTime() <= now) {
        if (typeof this.adapter.delete !== "function") throw new WorkspaceStoreError("workspace adapter does not support deletion");
        await this.adapter.delete(id);
        removed.push(id);
      }
    }
    return removed;
  }
}
