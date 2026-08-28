import assert from "node:assert/strict";
import test from "node:test";

import { createZowServer, requestDeploy, requestShell, validateProject } from "../server.mjs";

const env = { Z_PLATFORM_WORKSPACE_RUNTIME_URL: "http://runtime", Z_PLATFORM_SERVICE_TOKEN: "service-token" };

async function request(server, path, options = {}) {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  try {
    return await fetch(`http://127.0.0.1:${port}${path}`, options);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
}

test("health reports runtime configuration", async () => {
  const response = await request(createZowServer({ env }), "/health");
  assert.deepEqual(await response.json(), { status: "ok", service: "zow", runtime_configured: true });
});

test("project validation is forwarded to workspace runtime", async () => {
  const calls = [];
  const result = await validateProject({ project_id: "project-1", files: [] }, env, async (url, options) => {
    calls.push({ url, options });
    return Response.json({ status: "validated" });
  });
  assert.equal(result.status, "validated");
  assert.equal(calls[0].url, "http://runtime/v1/projects/validate");
  assert.equal(calls[0].options.headers.Authorization, "Bearer service-token");
});

test("shell and deploy are only requests to runtime with approval payloads", async () => {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    return Response.json({ status: "accepted" }, { status: 202 });
  };
  await requestShell({ command: "npm test", approval: { state: "approved", grants: ["shell"] } }, env, fetchImpl);
  await requestDeploy({ target: "staging", approval: { state: "approved", grants: ["deploy"] } }, env, fetchImpl);
  assert.ok(calls[0].url.endsWith("/v1/shell"));
  assert.ok(calls[1].url.endsWith("/v1/deploy"));
});

test("API propagates runtime rejection without local execution", async () => {
  const server = createZowServer({
    env,
    fetchImpl: async () => Response.json({ error: "shell requires explicit approval" }, { status: 403 }),
  });
  const response = await request(server, "/api/shell", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command: "npm test" }),
  });
  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { error: "shell requires explicit approval" });
});
