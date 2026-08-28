import assert from "node:assert/strict";
import { once } from "node:events";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { EncryptedMemoryStore, parseMemoryMasterKey } from "../crypto-store.mjs";
import {
  assertMemorySafe,
  ZarvisMemoryRuntime,
  ZARVIS_OWNER_TENANT_ID,
  ZARVIS_OWNER_USER_ID,
} from "../runtime.mjs";
import { createZarvisMemoryServer } from "../server.mjs";

const EDGE_SECRET = "edge-secret-0123456789-012345678901";
const WORKER_TOKEN = "memory-worker-0123456789-0123456789";
const MASTER_KEY = Buffer.alloc(32, 7);

function proposal(overrides = {}) {
  return {
    schema_version: "zarvis.memory.proposal-requested.v1",
    content: "The owner prefers concise Thai technical explanations.",
    classification: "semantic",
    reason: "Personalize future technical responses",
    confidence: 1,
    retention_days: 365,
    provenance: {
      source_type: "owner",
      source_id: "privacy-console",
    },
    ...overrides,
  };
}

function confirmation(value) {
  return {
    approval_digest: value.approval_digest,
    approval_nonce: value.approval_nonce,
  };
}

function ownerHeaders(extra = {}) {
  return {
    "x-zarvis-owner-id": "4076926",
    "x-zarvis-edge-secret": EDGE_SECRET,
    ...extra,
  };
}

async function fixture(t, { now } = {}) {
  const rootDir = await mkdtemp(join(tmpdir(), "zarvis-memory-"));
  t.after(() => rm(rootDir, { recursive: true, force: true }));
  const store = new EncryptedMemoryStore({ rootDir, masterKey: MASTER_KEY });
  let id = 0;
  const runtime = new ZarvisMemoryRuntime({
    store,
    now: now ?? (() => "2026-08-06T00:00:00.000Z"),
    idFactory: () => `id-${++id}`,
  });
  return { rootDir, store, runtime };
}

async function listen(server) {
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  return `http://127.0.0.1:${address.port}`;
}

test("master key parser requires exactly 32 base64-decoded bytes", () => {
  const encoded = MASTER_KEY.toString("base64");
  assert.deepEqual(parseMemoryMasterKey(encoded), MASTER_KEY);
  assert.throws(() => parseMemoryMasterKey(Buffer.alloc(31).toString("base64")), /exactly 32 bytes/);
});

test("raw credentials and private keys are rejected before persistence", () => {
  assert.throws(() => assertMemorySafe("api_key=sk-example-12345678901234567890"), /cannot be stored/);
  assert.throws(() => assertMemorySafe("-----BEGIN PRIVATE KEY-----"), /cannot be stored/);
});

test("proposal requires exact digest and nonce before encrypted confirmation", async (t) => {
  const { store, runtime } = await fixture(t);
  const pending = await runtime.createProposal(proposal());
  assert.equal((await runtime.listMemories()).length, 0);

  await assert.rejects(
    runtime.confirmProposal(pending.proposal_id, {
      approval_digest: "0".repeat(64),
      approval_nonce: pending.approval_nonce,
    }),
    /does not match/,
  );

  const confirmed = await runtime.confirmProposal(pending.proposal_id, confirmation(pending));
  assert.equal(confirmed.replayed, false);
  assert.equal(confirmed.owner_user_id, ZARVIS_OWNER_USER_ID);
  assert.equal(confirmed.tenant_id, ZARVIS_OWNER_TENANT_ID);
  assert.equal((await runtime.listMemories()).length, 1);

  const journal = await store.rawJournalTextForTest();
  assert.equal(journal.includes(pending.content), false);
  assert.equal(journal.includes("privacy-console"), false);

  const replay = await runtime.confirmProposal(pending.proposal_id, confirmation(pending));
  assert.equal(replay.replayed, true);
});

test("correction creates a new confirmed revision and lexical retrieval finds it", async (t) => {
  const { runtime } = await fixture(t);
  const firstProposal = await runtime.createProposal(proposal());
  const first = await runtime.confirmProposal(firstProposal.proposal_id, confirmation(firstProposal));
  const correction = await runtime.proposeCorrection(first.memory_id, proposal({
    content: "The owner prefers detailed Thai architecture analysis.",
    reason: "Owner corrected response depth preference",
  }));
  const corrected = await runtime.confirmProposal(correction.proposal_id, confirmation(correction));

  assert.equal(corrected.memory_id, first.memory_id);
  assert.equal(corrected.revision, 2);
  const results = await runtime.listMemories({ query: "architecture detailed" });
  assert.equal(results.length, 1);
  assert.match(results[0].content, /architecture/);
});

test("export contains active owner memories and delete compacts every encrypted revision", async (t) => {
  const { store, runtime } = await fixture(t);
  const pending = await runtime.createProposal(proposal());
  const memory = await runtime.confirmProposal(pending.proposal_id, confirmation(pending));
  const correction = await runtime.proposeCorrection(memory.memory_id, proposal({ content: "Corrected preference" }));
  await runtime.confirmProposal(correction.proposal_id, confirmation(correction));

  const exported = await runtime.exportMemories();
  assert.equal(exported.memories.length, 1);
  assert.equal(exported.memories[0].revision, 2);

  const deleted = await runtime.deleteMemory(memory.memory_id);
  assert.equal(deleted.deleted, true);
  assert.ok(deleted.encrypted_events_removed >= 4);
  assert.equal((await runtime.listMemories()).length, 0);
  assert.equal((await store.rawJournalTextForTest()).trim(), "");
});

test("retention worker purges expired memory without returning plaintext", async (t) => {
  let current = "2026-08-06T00:00:00.000Z";
  const { runtime } = await fixture(t, { now: () => current });
  const pending = await runtime.createProposal(proposal({
    classification: "working",
    retention_days: 1,
  }));
  await runtime.confirmProposal(pending.proposal_id, confirmation(pending));
  current = "2026-08-08T00:00:00.000Z";

  assert.equal((await runtime.listMemories()).length, 0);
  const purged = await runtime.purgeExpired();
  assert.equal(purged.purged_memories, 1);
  assert.ok(purged.encrypted_events_removed >= 2);
});

test("owner-only HTTP privacy console and APIs fail closed", async (t) => {
  const { runtime } = await fixture(t);
  const server = createZarvisMemoryServer({
    runtime,
    edgeSecret: EDGE_SECRET,
    workerToken: WORKER_TOKEN,
    logger: { error() {} },
  });
  const baseUrl = await listen(server);
  t.after(() => server.close());

  const denied = await fetch(baseUrl);
  assert.equal(denied.status, 403);
  const ownerUi = await fetch(baseUrl, { headers: ownerHeaders() });
  assert.equal(ownerUi.status, 200);
  assert.match(await ownerUi.text(), /Memory & Privacy/);

  const createdResponse = await fetch(`${baseUrl}/v1/memory/proposals`, {
    method: "POST",
    headers: ownerHeaders({ "content-type": "application/json" }),
    body: JSON.stringify(proposal()),
  });
  assert.equal(createdResponse.status, 202);
  const pending = await createdResponse.json();

  const confirmedResponse = await fetch(`${baseUrl}/v1/memory/proposals/${pending.proposal_id}/confirm`, {
    method: "POST",
    headers: ownerHeaders({ "content-type": "application/json" }),
    body: JSON.stringify(confirmation(pending)),
  });
  assert.equal(confirmedResponse.status, 200);
  const memory = await confirmedResponse.json();

  const unconfirmedDelete = await fetch(`${baseUrl}/v1/memories/${memory.memory_id}`, {
    method: "DELETE",
    headers: ownerHeaders(),
  });
  assert.equal(unconfirmedDelete.status, 428);

  const confirmedDelete = await fetch(`${baseUrl}/v1/memories/${memory.memory_id}`, {
    method: "DELETE",
    headers: ownerHeaders({ "x-zarvis-confirm-delete": memory.memory_id }),
  });
  assert.equal((await confirmedDelete.json()).deleted, true);

  const deniedWorker = await fetch(`${baseUrl}/v1/internal/memory/purge-expired`, { method: "POST" });
  assert.equal(deniedWorker.status, 403);
});

test("server startup fails without independent edge, worker, and encryption keys", () => {
  assert.throws(
    () => createZarvisMemoryServer({ edgeSecret: undefined, workerToken: WORKER_TOKEN, masterKey: MASTER_KEY.toString("base64") }),
    /ZARVIS_EDGE_SHARED_SECRET/,
  );
  assert.throws(
    () => createZarvisMemoryServer({ edgeSecret: EDGE_SECRET, workerToken: undefined, masterKey: MASTER_KEY.toString("base64") }),
    /ZARVIS_MEMORY_WORKER_TOKEN/,
  );
  assert.throws(
    () => createZarvisMemoryServer({ edgeSecret: EDGE_SECRET, workerToken: WORKER_TOKEN, masterKey: undefined }),
    /valid base64/,
  );
});
