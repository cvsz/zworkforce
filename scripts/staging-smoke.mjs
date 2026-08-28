import assert from "node:assert/strict";

const token = process.env.Z_PLATFORM_SERVICE_TOKEN;
if (!token) throw new Error("Z_PLATFORM_SERVICE_TOKEN is required");

const bases = {
  gateway: process.env.STAGING_SMOKE_AI_GATEWAY_URL || "http://127.0.0.1:8400",
  agent: process.env.STAGING_SMOKE_AGENT_ORCHESTRATOR_URL || "http://127.0.0.1:8500",
  workspace: process.env.STAGING_SMOKE_WORKSPACE_RUNTIME_URL || "http://127.0.0.1:8600",
  billing: process.env.STAGING_SMOKE_BILLING_LEDGER_URL || "http://127.0.0.1:8700",
  provider: process.env.STAGING_SMOKE_AGENT_PROVIDER_URL || "http://127.0.0.1:8800",
  zwallet: process.env.STAGING_SMOKE_ZWALLET_URL || "http://127.0.0.1:3040",
  zchat: process.env.STAGING_SMOKE_ZCHAT_URL || "http://127.0.0.1:3021",
};

const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function request(base, path, {
  method = "GET",
  body,
  auth = true,
  expected,
  headers = {},
  networkRetries = method === "GET" ? 4 : 0,
  retryDelayMs = 500,
} = {}) {
  const requestHeaders = { "Content-Type": "application/json", ...headers };
  if (auth) requestHeaders.Authorization = `Bearer ${token}`;

  let lastError;
  for (let attempt = 0; attempt <= networkRetries; attempt += 1) {
    try {
      const response = await fetch(`${base}${path}`, {
        method,
        headers: requestHeaders,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const text = await response.text();
      let payload = null;
      if (text) {
        try { payload = JSON.parse(text); } catch { payload = text; }
      }
      if (expected !== undefined) assert.equal(response.status, expected, `${method} ${path}: ${response.status} ${text}`);
      return { status: response.status, payload, headers: response.headers };
    } catch (error) {
      lastError = error;
      if (attempt >= networkRetries) throw error;
      await sleep(retryDelayMs * (attempt + 1));
    }
  }
  throw lastError;
}

for (const [name, base] of Object.entries(bases)) {
  const { payload } = await request(base, "/health", {
    auth: false,
    expected: 200,
    networkRetries: 20,
    retryDelayMs: 500,
  });
  assert.equal(payload.status, "ok", `${name} health must be ok`);
}

await request(bases.workspace, "/v1/shell", { method: "POST", auth: false, body: {}, expected: 401 });
await request(bases.workspace, "/v1/shell", { method: "POST", body: { command: "pwd" }, expected: 403 });
await request(bases.workspace, "/v1/deploy", { method: "POST", body: { target: "staging" }, expected: 403 });
const shell = await request(bases.workspace, "/v1/shell", {
  method: "POST",
  body: { command: "pwd", approval: { state: "approved", grants: ["shell"] } },
  expected: 202,
});
assert.equal(shell.payload.status, "accepted");

const usageKey = `smoke-${Date.now()}`;
const usage = {
  usage_id: usageKey,
  idempotency_key: usageKey,
  tenant_id: "readiness-smoke",
  subject_id: "ci",
  model: "smoke/model",
  input_tokens: 1,
  output_tokens: 1,
};
const firstUsage = await request(bases.billing, "/v1/usage", { method: "POST", body: usage, expected: 201 });
assert.equal(firstUsage.payload.duplicate, false);
const duplicateUsage = await request(bases.billing, "/v1/usage", { method: "POST", body: usage, expected: 200 });
assert.equal(duplicateUsage.payload.duplicate, true);
assert.equal(duplicateUsage.payload.record.usage_id, usageKey);

const idempotencyKey = `agent-${Date.now()}`;
const submitted = await request(bases.agent, "/v1/jobs", {
  method: "POST",
  body: {
    tenant_id: "readiness-smoke",
    task: "Validate readiness lifecycle",
    idempotency_key: idempotencyKey,
    tool_grants: [{ tool: "workspace.read", scope: "*", mutating: false }],
    requested_by: { type: "service", id: "readiness-smoke" },
  },
  expected: 202,
});
assert.equal(submitted.payload.status, "pending_approval");
const jobId = submitted.payload.id;

const duplicateSubmit = await request(bases.agent, "/v1/jobs", {
  method: "POST",
  body: {
    tenant_id: "readiness-smoke",
    task: "Validate readiness lifecycle",
    idempotency_key: idempotencyKey,
    tool_grants: [{ tool: "workspace.read", scope: "*", mutating: false }],
  },
  expected: 200,
});
assert.equal(duplicateSubmit.payload.id, jobId);

await request(bases.agent, `/v1/jobs/${jobId}/approve`, {
  method: "POST",
  body: {
    approved_by: "readiness-reviewer",
    tool_grants: [{ tool: "workspace.read", scope: "*", mutating: false }],
    constraints: { sandbox: "restricted", network: "deny-by-default" },
  },
  expected: 200,
});
const executed = await request(bases.agent, "/v1/worker/run-next", { method: "POST", body: {}, expected: 200 });
assert.equal(executed.payload.id, jobId);
assert.equal(executed.payload.status, "succeeded");

const cancelSubmitted = await request(bases.agent, "/v1/jobs", {
  method: "POST",
  body: {
    tenant_id: "readiness-smoke",
    task: "Validate cancellation",
    idempotency_key: `cancel-${Date.now()}`,
    tool_grants: [{ tool: "workspace.read", scope: "*", mutating: false }],
  },
  expected: 202,
});
const cancelled = await request(bases.agent, `/v1/jobs/${cancelSubmitted.payload.id}/cancel`, {
  method: "POST",
  body: { cancelled_by: "readiness-reviewer" },
  expected: 200,
});
assert.equal(cancelled.payload.status, "cancelled");

let retryJobId = null;
if (process.env.STAGING_SMOKE_TEST_FAILURE_RETRY === "true") {
  const failureSubmitted = await request(bases.agent, "/v1/jobs", {
    method: "POST",
    body: {
      tenant_id: "readiness-smoke",
      task: "readiness:fail-first-attempt",
      idempotency_key: `retry-${Date.now()}`,
      max_retries: 1,
      tool_grants: [{ tool: "workspace.read", scope: "*", mutating: false }],
    },
    expected: 202,
  });
  retryJobId = failureSubmitted.payload.id;
  await request(bases.agent, `/v1/jobs/${retryJobId}/approve`, {
    method: "POST",
    body: {
      approved_by: "readiness-reviewer",
      tool_grants: [{ tool: "workspace.read", scope: "*", mutating: false }],
      constraints: { sandbox: "restricted", network: "deny-by-default", max_retries: 1 },
    },
    expected: 200,
  });
  const failed = await request(bases.agent, "/v1/worker/run-next", { method: "POST", body: {}, expected: 200 });
  assert.equal(failed.payload.id, retryJobId);
  assert.equal(failed.payload.status, "failed");
  const retried = await request(bases.agent, `/v1/jobs/${retryJobId}/retry`, { method: "POST", body: {}, expected: 200 });
  assert.equal(retried.payload.status, "approved");
  const retrySucceeded = await request(bases.agent, "/v1/worker/run-next", { method: "POST", body: {}, expected: 200 });
  assert.equal(retrySucceeded.payload.id, retryJobId);
  assert.equal(retrySucceeded.payload.status, "succeeded");
  assert.equal(retrySucceeded.payload.attempt, 2);
}

const events = await request(bases.provider, "/events", { expected: 200 });
const jobEvents = events.payload.events.filter((event) => event.job_id === jobId).map((event) => event.event_type);
assert.deepEqual(jobEvents, ["agent.job.requested.v1", "agent.job.approved.v1", "agent.job.completed.v1"]);
assert.ok(events.payload.events.some((event) => event.job_id === cancelSubmitted.payload.id && event.status === "cancelled"));
if (retryJobId) {
  const retryStatuses = events.payload.events.filter((event) => event.job_id === retryJobId && event.event_type === "agent.job.completed.v1").map((event) => event.status);
  assert.deepEqual(retryStatuses, ["failed", "succeeded"]);
}

const workspaceId = `workspace-${Date.now()}`;
await request(bases.provider, `/workspaces/${workspaceId}`, {
  method: "PUT",
  body: { tenant_id: "readiness-smoke", status: "active" },
  expected: 200,
});
const workspace = await request(bases.provider, `/workspaces/${workspaceId}`, { expected: 200 });
assert.equal(workspace.payload.tenant_id, "readiness-smoke");
const backup = await request(bases.provider, "/backup/export", { expected: 200 });
assert.ok(backup.payload.workspaces[workspaceId]);
await request(bases.provider, "/backup/restore", { method: "POST", body: backup.payload, expected: 200 });
const restored = await request(bases.provider, `/workspaces/${workspaceId}`, { expected: 200 });
assert.equal(restored.payload.status, "active");

const metrics = await request(bases.provider, "/metrics", { auth: false, expected: 200 });
assert.match(metrics.payload, /z_platform_agent_jobs_total/);
assert.match(metrics.payload, /z_platform_agent_audit_events_total/);

for (const forbidden of ["wallet_signature", "card_number", "kyc_payload", "mpc_share", "swap_route"]) {
  const rejected = await request(bases.zwallet, "/api/invoice-intents", {
    method: "POST",
    auth: false,
    body: { tenant_id: "readiness-smoke", amount: 1, currency: "USD", [forbidden]: "forbidden-test-value" },
    expected: 400,
  });
  assert.match(rejected.payload.error, /is not accepted/);
}
const walletHealth = await request(bases.zwallet, "/health", { auth: false, expected: 200 });
assert.equal(walletHealth.payload.wallet_authority, false);
assert.equal(walletHealth.payload.card_data, false);

const zchatPage = await request(bases.zchat, "/", { auth: false, expected: 200 });
assert.match(zchatPage.payload, /<html lang="en">/);
assert.match(zchatPage.payload, /name="viewport"/);
assert.match(zchatPage.payload, /<main\b/);
assert.match(zchatPage.payload, /role="status"/);
assert.match(zchatPage.payload, /aria-live="polite"/);
assert.match(zchatPage.payload, /<label for="model">/);
assert.match(zchatPage.payload, /<label for="prompt">/);
const zchatCss = await request(bases.zchat, "/styles.css", { auth: false, expected: 200 });
assert.match(zchatCss.payload, /@media\s*\(max-width:\s*720px\)/);
const logout = await request(bases.zchat, "/api/logout", { method: "POST", auth: false, body: {}, expected: 200 });
assert.equal(logout.payload.status, "logged_out");
assert.match(logout.headers.get("clear-site-data") || "", /storage/);

console.log(JSON.stringify({
  status: "passed",
  services: Object.keys(bases),
  checks: [
    "health",
    "authentication",
    "workspace-approval-denial",
    "billing-idempotency",
    "agent-submit-idempotency-approve-execute-audit",
    "agent-cancellation",
    ...(retryJobId ? ["agent-real-failure-retry-success"] : []),
    "workspace-metadata",
    "backup-export-restore",
    "metrics",
    "zwallet-prohibited-capability-rejection",
    "zchat-accessibility-mobile-session-static-qa",
  ],
  job_id: jobId,
  retry_job_id: retryJobId,
  workspace_id: workspaceId,
}, null, 2));
