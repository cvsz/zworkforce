import assert from "node:assert/strict";
import test from "node:test";

import { extractDeltaText, readEventStream } from "../public/chat-stream.mjs";

test("extractDeltaText understands both raw and OpenAI-shaped SSE payloads", () => {
  assert.equal(extractDeltaText('data: {"choices":[{"delta":{"content":"hel"}}]}\n\ndata: lo\n\n'), "hello");
  assert.equal(extractDeltaText("data: [DONE]\n\n"), "");
});

test("readEventStream concatenates incremental chunks", async () => {
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode('data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'));
      controller.enqueue(new TextEncoder().encode('data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'));
      controller.close();
    },
  });

  const response = new Response(stream, { headers: { "Content-Type": "text/event-stream" } });
  const seen = [];
  const fullText = await readEventStream(response, (delta, emitted) => {
    seen.push({ delta, emitted });
  });

  assert.equal(fullText, "Hello");
  assert.deepEqual(seen, [
    { delta: "Hel", emitted: "Hel" },
    { delta: "lo", emitted: "Hello" },
  ]);
});

test("readEventStream returns partial text when aborted", async () => {
  const controller = new AbortController();
  const stream = new ReadableStream({
    start(source) {
      source.enqueue(new TextEncoder().encode('data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'));
    },
  });

  const response = new Response(stream, { headers: { "Content-Type": "text/event-stream" } });
  const seen = [];
  const fullText = await readEventStream(response, (delta, emitted) => {
    seen.push({ delta, emitted });
    controller.abort();
  }, controller.signal);

  assert.equal(fullText, "Hel");
  assert.deepEqual(seen, [{ delta: "Hel", emitted: "Hel" }]);
});
