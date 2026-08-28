import assert from "node:assert/strict";
import test from "node:test";

import {
  AgentOrchestrator,
  MemoryAuditSink,
  MemoryJobStore,
  MemoryQueueAdapter,
  HttpAuditSink,
  HttpIdentityProvider,
  HttpJobStore,
  HttpQueueAdapter,
  HttpSandboxRuntime,
  SandboxedWorkerRuntime,
  createAgentOrchestratorServer,
} from "../server.mjs";

const env = { Z_PLATFORM_SERVICE_TOKEN: "service-token" };

async function request(server, path, options = {}) {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  try {
    return await fetch(`http://127.0.0.1:${port}${path}`, options);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
}

function authHeaders(extra = {}) {
  return { Authorization: "Bearer service-token", "Content-Type": "application/json", ...extra };
}

function orchestratorFixture({ worker } = {}) {
  let nextId = 1;
  const store = new MemoryJobStore();
  const queue = new MemoryQueueAdapter();
  const audit = new MemoryAuditSink();
  const orchestrator = new AgentOrchestrator({
    store,
    queue,
    audit,
    worker,
    idGenerator: () => `job-${nextId++}`,
    now: () => "2026-07-13T00:00:00.000Z",
  });
  return { store, queue, audit, orchestrator };
}

function testServer() {
  return createAgentOrchestratorServer({
    env,
    orchestrator: orchestratorFixture().orchestrator,
  });
}

async function submit(orchestrator, overrides = {}) {
  return (await orchestrator.submit({
    tenant_id: "tenant-1",
    task: "run migration check",
    tool_grants: [{ tool: "repo.read", scope: "cvsz/z-platform", mutating: false }],
    idempotency_key: "idem-1",
    ...overrides,
  })).job;
}

test("health reports execution runtime without auth", async () => {
  const response = await request(testServer(), "/health");

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {
    status: "ok",
    service: "agent-orchestrator",
    storage: "memory",
    execution_enabled: true,
    external_traffic_enabled: false,
  });
});

test("job routes require service token", async () => {
  const response = await request(testServer(), "/v1/jobs", {
    method: "POST",
    body: JSON.stringify({}),
  });

  assert.equal(response.status, 401);
  assert.deepEqual(await response.json(), { error: "Unauthorized" });
});

test("creates pending approval jobs and emits requested audit event", async () => {
  const { orchestrator, audit } = orchestratorFixture();
  const result = await orchestrator.submit({
    tenant_id: "tenant-1",
    task: "run migration check",
    tool_grants: [{ tool: "repo.read", scope: "cvsz/z-platform", mutating: false }],
    idempotency_key: "idem-1",
  });

  assert.equal(result.status, 202);
  assert.equal(result.job.id, "job-1");
  assert.equal(result.job.status, "pending_approval");
  assert.equal(result.job.approval_state, "pending");
  assert.deepEqual(result.job.requested_tool_grants, [{ tool: "repo.read", scope: "cvsz/z-platform", mutating: false }]);
  assert.equal(audit.events[0].event_type, "agent.job.requested.v1");
});

test("returns duplicate job for same tenant and idempotency key", async () => {
  const { orchestrator } = orchestratorFixture();
  const first = await submit(orchestrator);
  const duplicate = await orchestrator.submit({
    tenant_id: "tenant-1",
    task: "different task",
    tool_grants: [{ tool: "repo.read", scope: "cvsz/z-platform", mutating: false }],
    idempotency_key: "idem-1",
  });

  assert.equal(duplicate.status, 200);
  assert.deepEqual(duplicate.job, first);
});

test("approves pending jobs with scoped grants and enqueues execution", async () => {
  const { orchestrator, queue, audit } = orchestratorFixture();
  const job = await submit(orchestrator);

  const approved = await orchestrator.approve(job.id, {
    approved_by: "operator-1",
    tool_grants: [{ tool: "repo.read", scope: "cvsz/z-platform", mutating: false }],
  });

  assert.equal(approved.status, "approved");
  assert.equal(approved.approval_state, "approved");
  assert.equal(approved.approved_by, "operator-1");
  assert.equal(queue.size(), 1);
  assert.equal(audit.events.at(-1).event_type, "agent.job.approved.v1");
});

test("rejects approval grants that were not requested", async () => {
  const { orchestrator } = orchestratorFixture();
  const job = await submit(orchestrator);

  await assert.rejects(
    orchestrator.approve(job.id, {
      approved_by: "operator-1",
      tool_grants: [{ tool: "repo.write", scope: "cvsz/z-platform", mutating: true }],
    }),
    /approved tool grant was not requested/,
  );
});

test("runs approved jobs in sandboxed runtime and audits completion", async () => {
  const calls = [];
  const worker = new SandboxedWorkerRuntime({
    allowedTools: {
      "repo.read": async ({ job, grant }) => calls.push({ job: job.id, grant }),
    },
    now: () => "2026-07-13T00:00:00.000Z",
  });
  const { orchestrator, audit } = orchestratorFixture({ worker });
  const job = await submit(orchestrator);
  await orchestrator.approve(job.id, {
    approved_by: "operator-1",
    tool_grants: [{ tool: "repo.read", scope: "cvsz/z-platform", mutating: false }],
  });

  const completed = await orchestrator.runNext();

  assert.equal(completed.status, "succeeded");
  assert.equal(completed.attempt, 1);
  assert.deepEqual(calls, [{ job: job.id, grant: { tool: "repo.read", scope: "cvsz/z-platform", mutating: false } }]);
  assert.equal(audit.events.at(-1).event_type, "agent.job.completed.v1");
  assert.equal(audit.events.at(-1).status, "succeeded");
});

test("cancels non-terminal jobs and emits terminal audit event", async () => {
  const { orchestrator, audit } = orchestratorFixture();
  const job = await submit(orchestrator);

  const cancelled = await orchestrator.cancel(job.id, { cancelled_by: "operator-1" });

  assert.equal(cancelled.status, "cancelled");
  assert.equal(cancelled.cancelled_by, "operator-1");
  assert.equal(audit.events.at(-1).event_type, "agent.job.completed.v1");
  assert.equal(audit.events.at(-1).status, "cancelled");
});

test("records worker failures and retries idempotently within retry limit", async () => {
  const worker = { execute: async () => { throw new Error("boom"); } };
  const { orchestrator, queue, audit } = orchestratorFixture({ worker });
  const job = await submit(orchestrator, { max_retries: 1 });
  await orchestrator.approve(job.id, {
    approved_by: "operator-1",
    tool_grants: [{ tool: "repo.read", scope: "cvsz/z-platform", mutating: false }],
  });

  const failed = await orchestrator.runNext();
  assert.equal(failed.status, "failed");
  assert.equal(failed.error.code, "WORKER_FAILED");
  assert.equal(audit.events.at(-1).status, "failed");

  const retried = await orchestrator.retry(job.id);
  assert.equal(retried.status, "approved");
  assert.equal(queue.size(), 1);
});

test("HTTP API supports submit, approve, execute, cancel, retry, and lookup", async () => {
  const { orchestrator } = orchestratorFixture({
    worker: new SandboxedWorkerRuntime({
      allowedTools: { "repo.read": async () => {} },
      now: () => "2026-07-13T00:00:00.000Z",
    }),
  });
  const server = createAgentOrchestratorServer({ env, orchestrator });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  try {
    const created = await fetch(`http://127.0.0.1:${port}/v1/jobs`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        tenant_id: "tenant-1",
        task: "run migration check",
        tool_grants: [{ tool: "repo.read", scope: "cvsz/z-platform", mutating: false }],
        idempotency_key: "idem-1",
      }),
    });
    const job = await created.json();
    assert.equal(created.status, 202);

    const approved = await fetch(`http://127.0.0.1:${port}/v1/jobs/${job.id}/approve`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ approved_by: "operator-1" }),
    });
    assert.equal(approved.status, 200);

    const executed = await fetch(`http://127.0.0.1:${port}/v1/worker/run-next`, { method: "POST", headers: authHeaders() });
    assert.equal((await executed.json()).status, "succeeded");

    const fetched = await fetch(`http://127.0.0.1:${port}/v1/jobs/${job.id}`, { headers: authHeaders() });
    assert.equal((await fetched.json()).status, "succeeded");
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
});


test("HTTP production providers persist, queue, authorize, execute, and emit audit events", async () => {
  const requests = [];
  const jobs = new Map();
  const queued = [];
  const fetchFn = async (url, options = {}) => {
    const body = options.body ? JSON.parse(options.body) : undefined;
    requests.push({ url, method: options.method || "GET", body, auth: options.headers?.Authorization });

    if (url.includes("/store/jobs/by-idempotency/")) {
      const found = [...jobs.values()].find((job) => job.tenant_id === "tenant-1" && job.idempotency_key === "idem-1");
      return found ? Response.json(found) : new Response(JSON.stringify({ error: "not found" }), { status: 404 });
    }
    if (url.includes("/store/jobs/") && options.method === "PUT") {
      jobs.set(body.id, body);
      return Response.json(body);
    }
    if (url.includes("/store/jobs/")) {
      const id = decodeURIComponent(url.split("/store/jobs/")[1]);
      const job = jobs.get(id);
      return job ? Response.json(job) : new Response(JSON.stringify({ error: "not found" }), { status: 404 });
    }
    if (url.endsWith("/queue")) {
      queued.push(body);
      return Response.json(body);
    }
    if (url.endsWith("/queue/next")) {
      return queued.length ? Response.json(queued.shift()) : new Response(null, { status: 204 });
    }
    if (url.endsWith("/audit/events")) {
      return Response.json({ accepted: true });
    }
    if (url.endsWith("/identity/authorize-approval")) {
      return Response.json({ allowed: true });
    }
    if (url.endsWith("/sandbox/execute")) {
      return Response.json({
        status: "succeeded",
        result_refs: [{ type: "artifact", id: "result-1" }],
        usage: { input_tokens: 1, output_tokens: 1, runtime_ms: 5 },
        audit: { worker_id: "sandbox-1", attempt: body.attempt, tool_calls: [{ tool: "repo.read", scope: "cvsz/z-platform", mutating: false, status: "succeeded" }] },
      });
    }
    return new Response(JSON.stringify({ error: "unhandled" }), { status: 500 });
  };

  let nextId = 1;
  const orchestrator = new AgentOrchestrator({
    store: new HttpJobStore({ baseUrl: "https://providers.internal/store", token: "service-token", fetchFn }),
    queue: new HttpQueueAdapter({ baseUrl: "https://providers.internal/queue", token: "service-token", fetchFn }),
    audit: new HttpAuditSink({ baseUrl: "https://providers.internal/audit", token: "service-token", fetchFn }),
    identity: new HttpIdentityProvider({ baseUrl: "https://providers.internal/identity", token: "service-token", fetchFn }),
    worker: new HttpSandboxRuntime({ baseUrl: "https://providers.internal/sandbox", token: "service-token", fetchFn }),
    idGenerator: () => `job-${nextId++}`,
    now: () => "2026-07-13T00:00:00.000Z",
  });

  const submitted = await submit(orchestrator);
  await orchestrator.approve(submitted.id, { approved_by: "operator-1" });
  const completed = await orchestrator.runNext();

  assert.equal(completed.status, "succeeded");
  assert.equal(completed.audit.worker_id, "sandbox-1");
  assert.ok(requests.some((request) => request.url.endsWith("/identity/authorize-approval")));
  assert.ok(requests.some((request) => request.url.endsWith("/sandbox/execute")));
  assert.ok(requests.every((request) => request.auth === "Bearer service-token"));
});

test("production provider mode requires operator-approved provider URLs", () => {
  assert.throws(
    () => createAgentOrchestratorServer({ env: { Z_PLATFORM_SERVICE_TOKEN: "service-token", AGENT_ORCHESTRATOR_PROVIDER_MODE: "production" } }),
    /missing production provider config/,
  );
});
