import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createAgentProviderServer } from "../server.mjs";

const token = "test-service-token";

async function withServer(fn) {
  const dir = await mkdtemp(join(tmpdir(), "z-agent-provider-"));
  const server = await createAgentProviderServer({ env: { Z_PLATFORM_SERVICE_TOKEN: token, DATA_DIR: dir } });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  try { await fn({ base, dir }); } finally { await new Promise((resolve) => server.close(resolve)); }
}

function request(base, path, options = {}) {
  return fetch(base + path, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers },
  });
}

test("persists jobs, idempotency, queue and audit", async () => {
  await withServer(async ({ base, dir }) => {
    const job = { id: "job-1", tenant_id: "tenant-a", idempotency_key: "idem-1", approval_state: "approved", approved_tool_grants: [], attempt: 1 };
    assert.equal((await request(base, "/jobs/job-1", { method: "PUT", body: JSON.stringify(job) })).status, 200);
    assert.equal((await request(base, "/jobs/by-idempotency/tenant-a/idem-1")).status, 200);
    assert.equal((await request(base, "/queue", { method: "POST", body: JSON.stringify({ job_id: "job-1", attempt: 1 }) })).status, 202);
    assert.equal((await request(base, "/queue/next", { method: "POST" })).status, 200);
    assert.equal((await request(base, "/events", { method: "POST", body: JSON.stringify({ event_type: "test" }) })).status, 202);
    const snapshot = await (await request(base, "/backup/export")).json();
    assert.equal(snapshot.jobs["job-1"].id, "job-1");
    assert.equal(snapshot.audit.length, 1);
    const persisted = JSON.parse(await readFile(join(dir, "state.json"), "utf8"));
    assert.equal(persisted.jobs["job-1"].tenant_id, "tenant-a");
  });
});

test("enforces identity and sandbox approval", async () => {
  await withServer(async ({ base }) => {
    const auth = await request(base, "/authorize-approval", { method: "POST", body: JSON.stringify({ actor: { type: "user", id: "reviewer" }, job: {} }) });
    assert.deepEqual(await auth.json(), { allowed: true, policy: "authenticated-user-separation-of-duties" });

    const denied = await request(base, "/execute", { method: "POST", body: JSON.stringify({ id: "job-2" }) });
    assert.equal(denied.status, 403);

    const accepted = await request(base, "/execute", { method: "POST", body: JSON.stringify({ id: "job-2", attempt: 1, approval_state: "approved", approved_tool_grants: [], constraints: { sandbox: "restricted" } }) });
    assert.equal(accepted.status, 200);
    assert.equal((await accepted.json()).status, "succeeded");
  });
});

test("restores backups into an isolated namespace without mutating primary state", async () => {
  await withServer(async ({ base }) => {
    await request(base, "/workspaces/ws-1", { method: "PUT", body: JSON.stringify({ project: "demo" }) });
    const snapshot = await (await request(base, "/backup/export")).json();
    await request(base, "/workspaces/cleanup", { method: "POST", body: JSON.stringify({ before: "2999-01-01T00:00:00Z" }) });
    assert.equal((await request(base, "/workspaces/ws-1")).status, 404);
    const restore = await request(base, "/backup/restore", { method: "POST", body: JSON.stringify({ namespace: "readiness-run-1", snapshot }) });
    assert.equal(restore.status, 200);
    assert.equal((await restore.json()).isolated, true);
    assert.equal((await request(base, "/workspaces/ws-1")).status, 404);
    const verify = await request(base, "/backup/verify?object=backup-1&namespace=readiness-run-1");
    assert.equal(verify.status, 200);
    const evidence = await verify.json();
    assert.equal(evidence.verified, true);
    assert.equal(evidence.isolated, true);
    assert.equal(evidence.workspaces, 1);
    assert.match(evidence.digest, /^[0-9a-f]{64}$/);
  });
});

test("rejects primary and unnamed backup restores", async () => {
  await withServer(async ({ base }) => {
    const response = await request(base, "/backup/restore", { method: "POST", body: JSON.stringify({ snapshot: {} }) });
    assert.equal(response.status, 400);
    assert.equal((await request(base, "/backup/verify?object=backup-1")).status, 400);
  });
});
