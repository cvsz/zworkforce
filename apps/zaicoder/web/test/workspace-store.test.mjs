import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { FileWorkspaceAdapter, HttpWorkspaceAdapter, WorkspaceStore, WorkspaceStoreError, createWorkspaceAdapterFromEnv } from "../server/workspace-store.mjs";

test("creates workspace metadata with retention", async () => {
  const root = await mkdtemp(join(tmpdir(), "zaicoder-workspaces-"));
  try {
    const store = new WorkspaceStore({ root, idGenerator: () => "workspace-1", now: () => "2026-07-13T00:00:00.000Z" });
    const workspace = await store.ensure({ owner: "tenant-1", retention_days: 7 });

    assert.equal(workspace.id, "workspace-1");
    assert.equal(workspace.owner, "tenant-1");
    assert.equal(workspace.retention_days, 7);
    assert.equal(workspace.expires_at, "2026-07-20T00:00:00.000Z");
    assert.deepEqual(workspace.files, []);
    assert.deepEqual(await store.read("workspace-1"), workspace);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("adds uploaded files to workspace metadata", async () => {
  const root = await mkdtemp(join(tmpdir(), "zaicoder-workspaces-"));
  try {
    const store = new WorkspaceStore({ root, now: () => "2026-07-13T00:00:00.000Z" });
    const workspace = await store.addFile("workspace-1", { id: "file-1", name: "notes.txt", size_bytes: 3 });

    assert.equal(workspace.id, "workspace-1");
    assert.deepEqual(workspace.files, [{ id: "file-1", name: "notes.txt", size_bytes: 3, added_at: "2026-07-13T00:00:00.000Z" }]);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("rejects unsafe workspace ids and retention", async () => {
  const root = await mkdtemp(join(tmpdir(), "zaicoder-workspaces-"));
  try {
    const store = new WorkspaceStore({ root });
    await assert.rejects(store.ensure({ workspace_id: "../bad" }), WorkspaceStoreError);
    await assert.rejects(store.ensure({ retention_days: 366 }), WorkspaceStoreError);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("resolves workspace files inside the configured root", async () => {
  const root = await mkdtemp(join(tmpdir(), "zaicoder-workspaces-"));
  try {
    const adapter = new FileWorkspaceAdapter({ root: join(root, "nested", "..", "store") });
    assert.equal(adapter.pathFor("workspace-1"), join(root, "store", "workspace-1.json"));
    assert.throws(() => adapter.pathFor("../outside"), WorkspaceStoreError);
    assert.throws(() => adapter.pathFor("/absolute"), WorkspaceStoreError);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("enforces tenant owner when supplied", async () => {
  const root = await mkdtemp(join(tmpdir(), "zaicoder-workspaces-"));
  try {
    const store = new WorkspaceStore({ root, now: () => "2026-07-13T00:00:00.000Z" });
    await store.ensure({ workspace_id: "workspace-1", owner: "tenant-a" });

    assert.equal((await store.read("workspace-1", { owner: "tenant-a" })).owner, "tenant-a");
    await assert.rejects(store.read("workspace-1", { owner: "tenant-b" }), /workspace owner mismatch/);
    await assert.rejects(store.addFile("workspace-1", { id: "file-1", name: "notes.txt" }, { owner: "tenant-b" }), /workspace owner mismatch/);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("supports custom durable workspace adapters", async () => {
  const records = new Map();
  const adapter = {
    async read(id) { return records.get(id) || null; },
    async save(record) { records.set(record.id, record); return record; },
    async delete(id) { records.delete(id); },
  };
  const store = new WorkspaceStore({ adapter, idGenerator: () => "workspace-1", now: () => "2026-07-13T00:00:00.000Z" });

  const workspace = await store.ensure({ owner: "tenant-1", retention_days: 1 });
  assert.equal(workspace.id, "workspace-1");
  assert.equal(records.get("workspace-1").owner, "tenant-1");
});

test("lists valid file-backed workspace ids", async () => {
  const root = await mkdtemp(join(tmpdir(), "zaicoder-workspaces-"));
  try {
    const adapter = new FileWorkspaceAdapter({ root });
    await writeFile(join(root, "alpha.json"), "{}\n", "utf8");
    await writeFile(join(root, "bad..json"), "{}\n", "utf8");
    await writeFile(join(root, "notes.txt"), "ignore\n", "utf8");
    await writeFile(join(root, "zeta.json"), "{}\n", "utf8");

    assert.deepEqual(await adapter.listIds(), ["alpha", "zeta"]);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("cleans up expired workspace metadata through adapter deletion", async () => {
  const root = await mkdtemp(join(tmpdir(), "zaicoder-workspaces-"));
  try {
    const adapter = new FileWorkspaceAdapter({ root });
    const store = new WorkspaceStore({ adapter, now: () => "2026-07-13T00:00:00.000Z" });
    await store.save({ id: "expired", owner: "tenant-1", retention_days: 1, created_at: "2026-07-01T00:00:00.000Z", updated_at: "2026-07-01T00:00:00.000Z", expires_at: "2026-07-02T00:00:00.000Z", files: [] });
    await store.save({ id: "active", owner: "tenant-1", retention_days: 30, created_at: "2026-07-13T00:00:00.000Z", updated_at: "2026-07-13T00:00:00.000Z", expires_at: "2026-08-12T00:00:00.000Z", files: [] });

    assert.deepEqual(await store.cleanupExpired(), ["expired"]);
    assert.equal(await store.read("expired"), null);
    assert.equal((await store.read("active")).id, "active");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("persists workspace metadata through the HTTP durable adapter", async () => {
  const requests = [];
  const adapter = new HttpWorkspaceAdapter({
    baseUrl: "https://metadata.internal/v1/",
    token: "service-token",
    fetchFn: async (url, options = {}) => {
      requests.push({ url, options });
      if (url.endsWith("/workspaces")) {
        return Response.json({ ids: ["zeta", "../bad", "alpha"] });
      }
      if (options.method === "PUT") {
        return Response.json(JSON.parse(options.body));
      }
      if (options.method === "DELETE") {
        return new Response(null, { status: 204 });
      }
      return Response.json({ id: "workspace-1", owner: "tenant-1", retention_days: 30, files: [] });
    },
  });

  assert.deepEqual(await adapter.listIds(), ["alpha", "zeta"]);
  assert.equal((await adapter.read("workspace-1")).id, "workspace-1");
  assert.equal((await adapter.save({ id: "workspace-1", owner: "tenant-1", files: [] })).owner, "tenant-1");
  await adapter.delete("workspace-1");

  assert.equal(requests[0].url, "https://metadata.internal/v1/workspaces");
  assert.equal(requests[0].options.headers.Authorization, "Bearer service-token");
  assert.equal(requests[2].options.method, "PUT");
  assert.equal(requests[3].options.method, "DELETE");
});

test("creates configured workspace adapters from environment", () => {
  assert.ok(createWorkspaceAdapterFromEnv({ ZAICODER_WORKSPACE_ADAPTER: "file", ZAICODER_WORKSPACE_STORE: "/tmp/workspaces" }) instanceof FileWorkspaceAdapter);
  assert.ok(createWorkspaceAdapterFromEnv({ ZAICODER_WORKSPACE_ADAPTER: "http", ZAICODER_WORKSPACE_METADATA_URL: "https://metadata.internal", Z_PLATFORM_SERVICE_TOKEN: "token" }) instanceof HttpWorkspaceAdapter);
  assert.throws(() => createWorkspaceAdapterFromEnv({ ZAICODER_WORKSPACE_ADAPTER: "bogus" }), /unsupported workspace adapter/);
});
