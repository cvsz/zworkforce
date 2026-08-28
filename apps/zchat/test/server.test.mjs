import assert from "node:assert/strict";
import { Readable } from "node:stream";
import test from "node:test";

import { chat, chatStream, createZChatRequestHandler, models, platformStatus, zchatHealthSnapshot } from "../server.mjs";

const env = { Z_PLATFORM_AI_GATEWAY_URL: "http://gateway", Z_PLATFORM_SERVICE_TOKEN: "service-token" };

function createMockResponse() {
  const chunks = [];
  const headers = {};
  return {
    statusCode: 0,
    headers,
    writeHead(status, nextHeaders = {}) {
      this.statusCode = status;
      Object.assign(headers, nextHeaders);
    },
    write(chunk) {
      chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    },
    end(chunk) {
      if (chunk) this.write(chunk);
      this.finished = true;
    },
    destroy(error) {
      this.error = error;
    },
    body() {
      return Buffer.concat(chunks).toString("utf8");
    },
  };
}

async function invoke(handler, { method, url, headers = {}, body = "" }) {
  const request = Readable.from(body ? [body] : []);
  request.method = method;
  request.url = url;
  request.headers = headers;
  const response = createMockResponse();
  await handler(request, response);
  const text = response.body();
  return {
    status: response.statusCode,
    headers: new Headers(response.headers),
    text: async () => text,
    json: async () => JSON.parse(text),
  };
}

test("health reports gateway configuration and session policy without auth", { concurrency: false }, async () => {
  assert.deepEqual(zchatHealthSnapshot({ ...env, ZCHAT_SESSION_TTL_SECONDS: "3600", Z_PLATFORM_RELEASE_SHA: "a".repeat(40) }), {
    status: "ok",
    service: "zchat",
    release_sha: "a".repeat(40),
    gateway_configured: true,
    session_ttl_seconds: 3600,
  });
});

test("liveness does not depend on configured upstream backends", { concurrency: false }, async () => {
  const response = await invoke(createZChatRequestHandler({ env: {} }), {
    method: "GET",
    url: "/health/live",
  });

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { status: "ok", service: "zchat", release_sha: "unknown" });
});

test("chat shell exposes accessible history search and shortcut guidance", { concurrency: false }, async () => {
  const response = await invoke(createZChatRequestHandler({ env: {} }), {
    method: "GET",
    url: "/",
  });
  const html = await response.text();

  assert.equal(response.status, 200);
  assert.match(html, /id="history-search"/);
  assert.match(html, /aria-keyshortcuts="Control\+K Meta\+K"/);
  assert.match(html, /Ctrl\/⌘\+K searches chats/);
  assert.match(html, /id="import-json"/);
  assert.match(html, /id="import-json-file"[^>]+accept="application\/json,\.json"/);
  assert.match(html, /id="load-older"[^>]+hidden/);
});

test("platform status keeps api6 and zc as separate backend boundaries", { concurrency: false }, async () => {
  const calls = [];
  const result = await platformStatus({
    PHASE6_API_URL: "http://api6",
    ZC_API_URL: "http://zc",
  }, async (url) => {
    calls.push(url);
    return new Response("ok", { status: 200 });
  });

  assert.equal(result.status, "ok");
  assert.deepEqual(result.backends.map((backend) => backend.service), ["phase6", "zc"]);
  assert.deepEqual(calls.sort(), ["http://api6/health", "http://zc/v1/wire/health/live"]);
});

test("loads model catalog from the AI gateway without exposing provider config", { concurrency: false }, async () => {
  const calls = [];
  const catalog = await models(env, async (url, options) => {
    calls.push({ url, options });
    return Response.json({ object: "list", data: [{ id: "hf:test", object: "model" }] });
  });

  assert.deepEqual(catalog.data.map((item) => item.id), ["hf:test"]);
  assert.equal(calls[0].url, "http://gateway/v1/models");
  assert.equal(calls[0].options.headers.Authorization, "Bearer service-token");
});

test("chat rejects missing prompt before calling the gateway", { concurrency: false }, async () => {
  let called = false;
  await assert.rejects(
    chat({ prompt: "   " }, env, async () => {
      called = true;
      throw new Error("should not call gateway");
    }),
    /Prompt is required/,
  );
  assert.equal(called, false);
});

test("chat forwards prompt through gateway with tenant, conversation, and usage correlation", { concurrency: false }, async () => {
  const calls = [];
  const result = await chat(
    { prompt: "  hello  ", model: "hf:test", conversation_id: "conversation-1", system_prompt: "Be concise." },
    env,
    async (url, options) => {
      calls.push({ url, options });
      return Response.json({ choices: [{ message: { content: "world" } }] });
    },
    { headers: { "x-tenant-id": "tenant-1", "x-usage-correlation-id": "usage-1", "x-request-id": "request-1" } },
  );

  assert.deepEqual(result, { content: "world", conversation_id: "conversation-1" });
  assert.equal(calls[0].url, "http://gateway/v1/chat/completions");
  assert.equal(calls[0].options.headers.Authorization, "Bearer service-token");
  assert.equal(calls[0].options.headers["X-Tenant-Id"], "tenant-1");
  assert.equal(calls[0].options.headers["X-Conversation-Id"], "conversation-1");
  assert.equal(calls[0].options.headers["X-Usage-Correlation-Id"], "usage-1");
  assert.equal(calls[0].options.headers["X-Request-Id"], "request-1");
  assert.deepEqual(JSON.parse(calls[0].options.body), {
    model: "hf:test",
    messages: [
      { role: "system", content: "Be concise." },
      { role: "user", content: "hello" },
    ],
    stream: false,
    metadata: {
      z_platform: {
        tenant_id: "tenant-1",
        conversation_id: "conversation-1",
        usage_correlation_id: "usage-1",
      },
    },
  });
});

test("chat rejects non-string system prompts before calling the gateway", { concurrency: false }, async () => {
  let called = false;
  await assert.rejects(
    chat({ prompt: "hello", system_prompt: 42 }, env, async () => {
      called = true;
      throw new Error("should not call gateway");
    }),
    /System prompt must be a string/,
  );
  assert.equal(called, false);
});

test("chat does not duplicate v1 when gateway url already includes it", { concurrency: false }, async () => {
  const calls = [];
  await chat(
    { prompt: "hello", conversation_id: "conversation-1" },
    { Z_PLATFORM_AI_GATEWAY_URL: "http://gateway/v1", Z_PLATFORM_SERVICE_TOKEN: "service-token" },
    async (url) => {
      calls.push(url);
      return Response.json({ choices: [{ message: { content: "ok" } }] });
    },
  );

  assert.equal(calls[0], "http://gateway/v1/chat/completions");
});

test("chat stream forwards streaming request and returns gateway stream", { concurrency: false }, async () => {
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode("data: hello\\n\\n"));
      controller.close();
    },
  });
  const calls = [];
  const result = await chatStream(
    { prompt: "hello", conversation_id: "conversation-1" },
    env,
    async (url, options) => {
      calls.push({ url, body: JSON.parse(options.body) });
      return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
    },
  );

  assert.equal(calls[0].body.stream, true);
  assert.equal(result.conversation_id, "conversation-1");
  assert.ok(result.stream);
});

test("chat stream links request cancellation to upstream fetch", { concurrency: false }, async () => {
  const controller = new AbortController();
  let observedSignal;
  await chatStream(
    { prompt: "hello", conversation_id: "conversation-1" },
    env,
    async (url, options) => {
      observedSignal = options.signal;
      return Response.json({ choices: [{ message: { content: "ok" } }] }, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      });
    },
    { headers: { "x-usage-correlation-id": "usage-1" }, signal: controller.signal },
  );

  assert.ok(observedSignal);
  assert.equal(observedSignal.aborted, false);
  controller.abort();
  assert.equal(observedSignal.aborted, true);
});

test("chat stream includes the pinned system prompt before the user prompt", { concurrency: false }, async () => {
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode("data: hello\\n\\n"));
      controller.close();
    },
  });
  const calls = [];
  await chatStream(
    { prompt: "hello", conversation_id: "conversation-1", system_prompt: "Be concise." },
    env,
    async (url, options) => {
      calls.push({ url, body: JSON.parse(options.body) });
      return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
    },
  );

  assert.deepEqual(calls[0].body.messages, [
    { role: "system", content: "Be concise." },
    { role: "user", content: "hello" },
  ]);
});

test("session expiry blocks chat before gateway call", { concurrency: false }, async () => {
  let called = false;
  await assert.rejects(
    chat(
      { prompt: "hello" },
      { ...env, ZCHAT_SESSION_TTL_SECONDS: "1" },
      async () => {
        called = true;
        return Response.json({});
      },
      { headers: { "x-session-started-at": String(Date.now() - 2000) } },
    ),
    /Session expired/,
  );
  assert.equal(called, false);
});

test("http routes return gateway content and clear browser storage", { concurrency: false }, async () => {
  const handler = createZChatRequestHandler({
    env,
    fetchImpl: async () => Response.json({ choices: [{ message: { content: "ok" } }] }),
  });

  const chatResponse = await invoke(handler, {
    method: "POST",
    url: "/api/chat",
    headers: { "Content-Type": "application/json", "X-Usage-Correlation-Id": "usage-1" },
    body: JSON.stringify({ prompt: "hi", conversation_id: "conversation-1" }),
  });

  assert.equal(chatResponse.status, 200);
  assert.deepEqual(await chatResponse.json(), { content: "ok", conversation_id: "conversation-1" });

  const logoutResponse = await invoke(createZChatRequestHandler({ env }), {
    method: "POST",
    url: "/api/logout",
  });

  assert.equal(logoutResponse.status, 200);
  assert.equal(logoutResponse.headers.get("clear-site-data"), '"storage"');
  assert.deepEqual(await logoutResponse.json(), { status: "logged_out" });
});
