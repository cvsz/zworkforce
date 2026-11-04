import assert from "node:assert/strict";
import test from "node:test";

import { WorkspaceRuntime, computeApprovalSignature, createWorkspaceRuntimeServer } from "../server.mjs";

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

const headers = { Authorization: "Bearer service-token", "Content-Type": "application/json" };

test("validates generated projects with safe owned files", () => {
  const runtime = new WorkspaceRuntime({ idGenerator: () => "validation-1", now: () => "2026-07-13T00:00:00.000Z" });
  assert.deepEqual(runtime.validateGeneratedProject({
    project_id: "project-1",
    files: [{ path: "README.md", owner: "generator" }],
  }), {
    validation_id: "validation-1",
    status: "validated",
    project_id: "project-1",
    file_count: 1,
    checked_at: "2026-07-13T00:00:00.000Z",
  });
});

test("rejects unsafe or secret-bearing generated files", () => {
  const runtime = new WorkspaceRuntime();
  assert.throws(() => runtime.validateGeneratedProject({ project_id: "project-1", files: [{ path: "../bad", owner: "generator" }] }), /unsafe/);
  assert.throws(() => runtime.validateGeneratedProject({ project_id: "project-1", files: [{ path: ".env", owner: "generator" }] }), /secret-bearing/);
});

test("shell and deploy require explicit approval grants", () => {
  const runtime = new WorkspaceRuntime({ idGenerator: () => "request-1", now: () => "2026-07-13T00:00:00.000Z" });
  assert.throws(() => runtime.requestShell({ command: "npm test" }), /requires explicit approval/);
  assert.deepEqual(runtime.requestShell({ command: "npm test", approval: { state: "approved", grants: ["shell"] } }).action, "shell");
  assert.throws(() => runtime.requestDeploy({ target: "staging", approval: { state: "approved", grants: ["shell"] } }), /deploy approval grant is missing/);
});

test("HTTP runtime routes require service token", async () => {
  const response = await request(createWorkspaceRuntimeServer({ env }), "/v1/projects/validate", { method: "POST", body: "{}" });
  assert.equal(response.status, 401);
});

test("HTTP runtime validates and gates actions", async () => {
  const server = createWorkspaceRuntimeServer({ env, runtime: new WorkspaceRuntime({ idGenerator: () => "id-1", now: () => "2026-07-13T00:00:00.000Z" }) });
  const response = await request(server, "/v1/projects/validate", {
    method: "POST",
    headers,
    body: JSON.stringify({ project_id: "project-1", files: [{ path: "README.md", owner: "generator" }] }),
  });
  assert.equal(response.status, 200);
  assert.equal((await response.json()).status, "validated");
});

test("enforces four-eyes separation, expiry, and cryptographic signature when configured", () => {
  const signingSecret = "approval-hmac-secret";
  const runtime = new WorkspaceRuntime({
    idGenerator: () => "req-4eyes",
    now: () => "2026-07-13T12:00:00.000Z",
    env: {
      Z_PLATFORM_REQUIRE_FOUR_EYES: "true",
      Z_PLATFORM_APPROVAL_SIGNING_SECRET: signingSecret,
    },
  });

  // Self-approval must be rejected
  assert.throws(() => runtime.requestShell({
    command: "npm test",
    approval: {
      state: "approved",
      grants: ["shell"],
      requester_id: "alice",
      approver_id: "alice",
    },
  }), /prohibits self-approval/);

  // Expired approval must be rejected
  assert.throws(() => runtime.requestShell({
    command: "npm test",
    approval: {
      state: "approved",
      grants: ["shell"],
      requester_id: "alice",
      approver_id: "bob",
      expires_at: "2026-07-13T11:59:59.000Z",
    },
  }), /expired/);

  // Missing or invalid signature must be rejected
  assert.throws(() => runtime.requestDeploy({
    target: "production",
    approval: {
      state: "approved",
      grants: ["deploy"],
      requester_id: "alice",
      approver_id: "bob",
      expires_at: "2026-07-13T13:00:00.000Z",
      signature: "forged",
    },
  }), /signature is invalid/);

  // Valid four-eyes signed approval succeeds
  const validApproval = {
    state: "approved",
    grants: ["deploy"],
    requester_id: "alice",
    approver_id: "bob",
    expires_at: "2026-07-13T13:00:00.000Z",
  };
  validApproval.signature = computeApprovalSignature("deploy", validApproval, "production", signingSecret);
  const res = runtime.requestDeploy({ target: "production", approval: validApproval });
  assert.equal(res.status, "accepted");
  assert.equal(res.target, "production");
});
