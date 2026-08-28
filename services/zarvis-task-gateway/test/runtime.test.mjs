import assert from "node:assert/strict";
import { once } from "node:events";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  MemoryAuditSink,
  MemoryJobStore,
  MemoryQueueAdapter,
} from "../../agent-orchestrator/server.mjs";
import {
  normalizePlan,
  ZarvisTaskRuntime,
  ZARVIS_OWNER_TENANT_ID,
  ZARVIS_OWNER_USER_ID,
} from "../runtime.mjs";
import { createZarvisTaskServer } from "../server.mjs";

const EDGE_SECRET = "edge-secret-0123456789-012345678901";
const WORKER_TOKEN = "worker-token-0123456789-012345678901";

const repositoryPayload = {
  full_name: "cvsz/z-platform",
  visibility: "public",
  private: false,
  archived: false,
  disabled: false,
  fork: false,
  default_branch: "main",
  open_issues_count: 4,
  stargazers_count: 1,
  watchers_count: 1,
  forks_count: 0,
  updated_at: "2026-08-06T00:00:00Z",
  pushed_at: "2026-08-06T00:00:00Z",
  web_url: "https://github.com/cvsz/z-platform",
};

function plan(overrides = {}) {
  return {
    schema_version: "zarvis.task.requested.v1",
    idempotency_key: "task-idem-1",
    objective: "Inspect and summarize cvsz/z-platform",
    steps: [
      {
        id: "repository-status",
        tool: "github.repository.status",
        scope: "cvsz/z-platform",
        mutating: false,
        depends_on: [],
        arguments: {},
      },
      {
        id: "repository-summary",
        tool: "zarvis.repository.summary",
        scope: "cvsz/z-platform",
        mutating: false,
        depends_on: ["repository-status"],
        arguments: {},
      },
    ],
    ...overrides,
  };
}

function memoryFixture({ now = () => "2026-08-06T00:00:00.000Z", githubExecutor } = {}) {
  const store = new MemoryJobStore();
  const queue = new MemoryQueueAdapter();
  const audit = new MemoryAuditSink();
  const runtime = new ZarvisTaskRuntime({
    store,
    queue,
    audit,
    now,
    githubExecutor: githubExecutor ?? (async () => repositoryPayload),
    idGenerator: () => "task-1",
  });
  return { store, queue, audit, runtime };
}

function approval(job) {
  return {
    schema_version: "zarvis.task.approval.v1",
    approval_digest: job.approval_digest,
    approval_nonce: job.approval_nonce,
  };
}

function ownerHeaders(extra = {}) {
  return {
    "x-zarvis-owner-id": "4076926",
    "x-zarvis-edge-secret": EDGE_SECRET,
    "content-type": "application/json",
    ...extra,
  };
}

async function listen(server) {
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  return `http://127.0.0.1:${address.port}`;
}

test("plan validation rejects mutation and forward dependencies", () => {
  assert.throws(
    () => normalizePlan(plan({
      steps: [{
        id: "write",
        tool: "github.repository.status",
        scope: "cvsz/z-platform",
        mutating: true,
      }],
    })),
    /Mutating task steps remain blocked/,
  );

  assert.throws(
    () => normalizePlan(plan({
      steps: [{
        id: "summary",
        tool: "zarvis.repository.summary",
        scope: "cvsz/z-platform",
        depends_on: ["missing"],
      }],
    })),
    /may depend only on an earlier step/,
  );
});

test("task submission is owner-bound and produces exact-plan approval proof", async () => {
  const { runtime, audit } = memoryFixture();
  const result = await runtime.submitPlan(plan());

  assert.equal(result.status, 202);
  assert.equal(result.job.tenant_id, ZARVIS_OWNER_TENANT_ID);
  assert.equal(result.job.owner_user_id, ZARVIS_OWNER_USER_ID);
  assert.equal(result.job.status, "pending_approval");
  assert.match(result.job.approval_digest, /^[a-f0-9]{64}$/);
  assert.equal(typeof result.job.approval_nonce, "string");
  assert.equal(result.job.plan.steps.length, 2);
  assert.equal(audit.events.at(-1).event_type, "zarvis.task.plan-created.v1");
});

test("idempotency replays only the identical exact plan", async () => {
  const { runtime } = memoryFixture();
  const first = await runtime.submitPlan(plan());
  const replay = await runtime.submitPlan(plan());

  assert.equal(replay.status, 200);
  assert.equal(replay.job.id, first.job.id);
  await assert.rejects(
    runtime.submitPlan(plan({ objective: "Different objective" })),
    /different exact task plan/,
  );
});

test("approval requires matching digest and one-time nonce", async () => {
  const { runtime, queue } = memoryFixture();
  const task = (await runtime.submitPlan(plan())).job;

  await assert.rejects(
    runtime.approvePlan(task.id, {
      approval_digest: "0".repeat(64),
      approval_nonce: task.approval_nonce,
    }),
    /digest does not match/,
  );

  const approved = await runtime.approvePlan(task.id, approval(task));
  assert.equal(approved.status, "approved");
  assert.equal(approved.approved_by, ZARVIS_OWNER_USER_ID);
  assert.equal(approved.approval_nonce, null);
  assert.equal(queue.size(), 1);

  await assert.rejects(runtime.approvePlan(task.id, approval(task)), /not awaiting approval/);
});

test("approved task can pause, resume, and execute a two-step read-only plan", async () => {
  const { runtime } = memoryFixture();
  const task = (await runtime.submitPlan(plan())).job;
  await runtime.approvePlan(task.id, approval(task));

  const paused = await runtime.pause(task.id);
  assert.equal(paused.status, "paused");
  const consumedWhilePaused = await runtime.runNext();
  assert.equal(consumedWhilePaused.status, "paused");

  const resumed = await runtime.resume(task.id);
  assert.equal(resumed.status, "approved");
  const completed = await runtime.runNext();
  assert.equal(completed.status, "succeeded");
  assert.deepEqual(completed.step_results.map((step) => step.status), ["succeeded", "succeeded"]);
  assert.match(completed.step_results[1].output.text, /cvsz\/z-platform/);
  assert.deepEqual(completed.checkpoint.completed_step_ids, ["repository-status", "repository-summary"]);
});

test("expired approval never invokes a task tool", async () => {
  let current = "2026-08-06T00:00:00.000Z";
  let calls = 0;
  const { runtime } = memoryFixture({
    now: () => current,
    githubExecutor: async () => {
      calls += 1;
      return repositoryPayload;
    },
  });
  const task = (await runtime.submitPlan(plan())).job;
  await runtime.approvePlan(task.id, approval(task));
  current = "2026-08-06T00:16:00.000Z";

  const expired = await runtime.runNext();
  assert.equal(expired.status, "expired");
  assert.equal(calls, 0);
  assert.equal(expired.audit.reason, "approval_expired");
});

test("durable adapters recover approved task, queue, and audit after reconstruction", async (t) => {
  const rootDir = await mkdtemp(join(tmpdir(), "zarvis-task-"));
  t.after(() => rm(rootDir, { recursive: true, force: true }));

  const first = new ZarvisTaskRuntime({
    rootDir,
    now: () => "2026-08-06T00:00:00.000Z",
    githubExecutor: async () => repositoryPayload,
    idGenerator: () => "durable-task-1",
  });
  const task = (await first.submitPlan(plan())).job;
  await first.approvePlan(task.id, approval(task));

  const reconstructed = new ZarvisTaskRuntime({
    rootDir,
    now: () => "2026-08-06T00:01:00.000Z",
    githubExecutor: async () => repositoryPayload,
  });
  assert.equal((await reconstructed.listPlans()).length, 1);
  const completed = await reconstructed.runNext();
  assert.equal(completed.id, "durable-task-1");
  assert.equal(completed.status, "succeeded");
  assert.equal((await reconstructed.get(task.id)).status, "succeeded");
});

test("owner-only HTTP API supports create, approve, list, worker execution, and lookup", async (t) => {
  const { runtime } = memoryFixture();
  const server = createZarvisTaskServer({
    runtime,
    edgeSecret: EDGE_SECRET,
    workerToken: WORKER_TOKEN,
    logger: { error() {} },
  });
  const baseUrl = await listen(server);
  t.after(() => server.close());

  const denied = await fetch(`${baseUrl}/v1/tasks`);
  assert.equal(denied.status, 403);

  const createdResponse = await fetch(`${baseUrl}/v1/tasks`, {
    method: "POST",
    headers: ownerHeaders(),
    body: JSON.stringify(plan()),
  });
  assert.equal(createdResponse.status, 202);
  const task = await createdResponse.json();

  const wrongApproval = await fetch(`${baseUrl}/v1/tasks/${task.id}/approve`, {
    method: "POST",
    headers: ownerHeaders(),
    body: JSON.stringify({
      approval_digest: "0".repeat(64),
      approval_nonce: task.approval_nonce,
    }),
  });
  assert.equal(wrongApproval.status, 409);

  const approved = await fetch(`${baseUrl}/v1/tasks/${task.id}/approve`, {
    method: "POST",
    headers: ownerHeaders(),
    body: JSON.stringify(approval(task)),
  });
  assert.equal(approved.status, 200);

  const deniedWorker = await fetch(`${baseUrl}/v1/internal/worker/run-next`, { method: "POST" });
  assert.equal(deniedWorker.status, 403);
  const executed = await fetch(`${baseUrl}/v1/internal/worker/run-next`, {
    method: "POST",
    headers: { Authorization: `Bearer ${WORKER_TOKEN}` },
  });
  assert.equal((await executed.json()).status, "succeeded");

  const list = await fetch(`${baseUrl}/v1/tasks`, { headers: ownerHeaders() });
  assert.equal((await list.json()).tasks.length, 1);
  const fetched = await fetch(`${baseUrl}/v1/tasks/${task.id}`, { headers: ownerHeaders() });
  assert.equal((await fetched.json()).status, "succeeded");
});

test("server startup fails closed without independent edge and worker secrets", () => {
  assert.throws(
    () => createZarvisTaskServer({ edgeSecret: undefined, workerToken: WORKER_TOKEN }),
    /ZARVIS_EDGE_SHARED_SECRET/,
  );
  assert.throws(
    () => createZarvisTaskServer({ edgeSecret: EDGE_SECRET, workerToken: undefined }),
    /ZARVIS_TASK_WORKER_TOKEN/,
  );
});
