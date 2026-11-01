import assert from "node:assert/strict";
import { once } from "node:events";
import test from "node:test";

import { createZaiCoderServer } from "../server/http.mjs";

async function startServer(t) {
  const server = createZaiCoderServer();
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  t.after(
    () =>
      new Promise((resolve, reject) => {
        server.close((error) => (error ? reject(error) : resolve()));
      }),
  );

  const address = server.address();
  return "http://127.0.0.1:" + address.port;
}

test("tenant-scoped API routes fail closed despite caller-supplied tenant and owner fields", async (t) => {
  const base = await startServer(t);
  const requests = [
    {
      method: "POST",
      path: "/api/workspaces",
      body: { workspace_id: "victim", owner: "tenant-victim" },
    },
    { method: "GET", path: "/api/workspaces/victim" },
    {
      method: "POST",
      path: "/api/chat",
      body: { prompt: "hello", tenant_id: "tenant-victim" },
    },
    {
      method: "POST",
      path: "/api/chat/stream",
      body: { prompt: "hello", tenant_id: "tenant-victim" },
    },
    {
      method: "POST",
      path: "/api/files",
      body: "untrusted file bytes",
      headers: {
        "X-Filename": "notes.txt",
        "Content-Type": "text/plain",
      },
    },
  ];

  for (const item of requests) {
    const response = await fetch(base + item.path, {
      method: item.method,
      headers: {
        "X-Tenant-Id": "tenant-victim",
        ...(item.headers || {}),
        ...(item.body && typeof item.body === "object"
          ? { "Content-Type": "application/json" }
          : {}),
      },
      ...(item.body === undefined
        ? {}
        : {
            body:
              typeof item.body === "string"
                ? item.body
                : JSON.stringify(item.body),
          }),
    });

    assert.equal(response.status, 503, item.method + " " + item.path);
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.deepEqual(await response.json(), {
      error: "Authenticated tenant identity is not configured",
    });
  }
});

test("static browser shell remains available while tenant API is disabled", async (t) => {
  const base = await startServer(t);
  const response = await fetch(base + "/");

  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type"), /text\/html/);
  assert.match(await response.text(), /ZAI Coder/);
});
