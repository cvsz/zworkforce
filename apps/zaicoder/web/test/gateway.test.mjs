import assert from "node:assert/strict";
import test from "node:test";

import {
  ChatRequestError,
  forwardChat,
  forwardChatStream,
  forwardFile,
  validateChatRequest,
} from "../server/gateway.mjs";

test("forwards a validated chat request without exposing the token", async () => {
  let request;
  const result = await forwardChat(
    { model: "coding", prompt: "Explain this" },
    {
      env: { Z_PLATFORM_AI_GATEWAY_URL: "https://gateway.example/v1", Z_PLATFORM_SERVICE_TOKEN: "token" },
      fetchImpl: async (url, options) => {
        request = { url, options };
        return { ok: true, json: async () => ({ choices: [{ message: { content: "answer" } }] }) };
      },
    },
  );
  assert.deepEqual(result, { content: "answer" });
  assert.equal(request.url, "https://gateway.example/v1/chat/completions");
  assert.equal(JSON.parse(request.options.body).messages[0].content, "Explain this");
  assert.equal(request.options.headers.Authorization, "Bearer token");
});

test("normalizes gateway base urls that do not include v1", async () => {
  let request;
  await forwardChat(
    { model: "coding", prompt: "Explain this" },
    {
      env: { Z_PLATFORM_AI_GATEWAY_URL: "https://gateway.example", Z_PLATFORM_SERVICE_TOKEN: "token" },
      fetchImpl: async (url, options) => {
        request = { url, options };
        return { ok: true, json: async () => ({ choices: [{ message: { content: "answer" } }] }) };
      },
    },
  );

  assert.equal(request.url, "https://gateway.example/v1/chat/completions");
});

test("forwards an SSE request with streaming enabled", async () => {
  let request;
  const body = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode("data: [DONE]\n\n"));
      controller.close();
    },
  });
  const result = await forwardChatStream(
    { model: "coding", prompt: "Stream this" },
    {
      env: { Z_PLATFORM_AI_GATEWAY_URL: "https://gateway.example/v1", Z_PLATFORM_SERVICE_TOKEN: "token" },
      fetchImpl: async (url, options) => {
        request = { url, options };
        return { ok: true, body };
      },
    },
  );
  assert.equal(result, body);
  assert.equal(request.url, "https://gateway.example/v1/chat/completions");
  assert.equal(JSON.parse(request.options.body).stream, true);
});

test("forwards file uploads through the gateway", async () => {
  let request;
  const bytes = new Uint8Array([1, 2, 3]);
  const result = await forwardFile(
    { name: "notes.txt", type: "text/plain", bytes },
    {
      env: { Z_PLATFORM_AI_GATEWAY_URL: "https://gateway.example", Z_PLATFORM_SERVICE_TOKEN: "token" },
      fetchImpl: async (url, options) => {
        request = { url, options };
        return { ok: true, json: async () => ({ id: "file-1" }) };
      },
    },
  );

  assert.deepEqual(result, { id: "file-1", name: "notes.txt", size_bytes: 3 });
  assert.equal(request.url, "https://gateway.example/v1/files");
  assert.equal(request.options.headers.Authorization, "Bearer token");
  assert.equal(request.options.headers["Content-Type"], "text/plain");
  assert.equal(request.options.headers["X-Filename"], "notes.txt");
  assert.equal(request.options.body, bytes);
});

test("rejects invalid prompts, files, and missing gateway configuration", async () => {
  assert.throws(() => validateChatRequest({ prompt: "" }), ChatRequestError);
  await assert.rejects(
    forwardChat({ prompt: "hello" }, { env: {} }),
    ChatRequestError,
  );
  await assert.rejects(
    forwardFile({ name: "../secret.txt", type: "text/plain", bytes: new Uint8Array([1]) }, { env: { Z_PLATFORM_AI_GATEWAY_URL: "https://gateway.example", Z_PLATFORM_SERVICE_TOKEN: "token" } }),
    ChatRequestError,
  );
});
