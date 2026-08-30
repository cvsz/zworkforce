import assert from "node:assert/strict";
import { test } from "node:test";

import {
  createRealtimeClient,
  parseSseBlock,
} from "../zworkforce/static/dashboard/core/realtime.js";
import { createPackageRegistry } from "../zworkforce/static/dashboard/core/registry.js";
import { mountRealtimePackage } from "../zworkforce/static/dashboard/packages/realtime/index.js";

const encoder = new TextEncoder();

function responseFor(text) {
  let sent = false;
  return {
    ok: true,
    status: 200,
    body: {
      getReader() {
        return {
          async read() {
            if (sent) return { done: true, value: undefined };
            sent = true;
            return { done: false, value: encoder.encode(text) };
          },
          async cancel() {},
          releaseLock() {},
        };
      },
    },
  };
}

function liveResponseFor(text) {
  let sent = false;
  return {
    ok: true,
    status: 200,
    body: {
      getReader() {
        return {
          async read() {
            if (!sent) {
              sent = true;
              return { done: false, value: encoder.encode(text) };
            }
            return new Promise(() => {});
          },
          async cancel() {},
          releaseLock() {},
        };
      },
    },
  };
}

function hangingResponse() {
  return {
    ok: true,
    status: 200,
    body: {
      getReader() {
        return {
          async read() {
            return new Promise(() => {});
          },
          async cancel() {},
          releaseLock() {},
        };
      },
    },
  };
}

async function waitFor(predicate, timeoutMs = 1000) {
  const deadline = Date.now() + timeoutMs;
  while (!predicate()) {
    if (Date.now() >= deadline) throw new Error("timed out waiting for realtime state");
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
}

function heartbeat(cursor) {
  return `id: ${cursor}\nevent: heartbeat\ndata: {"cursor":${cursor},"server_time":"2026-08-30T00:00:00+00:00"}\n\n`;
}

test("parses SSE ids, events, and multiple data lines", () => {
  assert.deepEqual(
    parseSseBlock('id: 7\nevent: task.changed\ndata: {"a":\ndata: 1}\n'),
    { id: 7, event: "task.changed", data: { a: 1 } },
  );
  assert.equal(parseSseBlock("id: bad\ndata: {}\n"), null);
});

test("authenticated stream sends headers without a URL query and heartbeat becomes LIVE", async () => {
  const calls = [];
  const statuses = [];
  const client = createRealtimeClient({
    getSession: () => ({ key: "session-secret", tenant: "default" }),
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return liveResponseFor(heartbeat(3));
    },
    sleep: async () => {},
  });
  client.subscribeStatus((state) => statuses.push(state));
  client.start();
  await waitFor(() => client.getState() === "LIVE");

  assert.equal(calls[0].url, "/api/v1/dashboard/events");
  assert.equal(calls[0].options.headers.Authorization, "Bearer session-secret");
  assert.equal(calls[0].options.headers["X-Tenant-ID"], "default");
  assert.equal(calls[0].options.headers["X-ZWorkforce-Event-Cursor"], "0");
  assert.equal(client.getCursor(), 3);
  assert.ok(statuses.includes("LIVE"));
  client.stop();
});

test("duplicate task events produce one debounced package invalidation", async () => {
  const invalidations = [];
  const registry = createPackageRegistry(
    [{ id: "workforce", events: ["task.changed"] }],
    (packageId) => invalidations.push(packageId),
  );
  registry.dispatch({ event: "task.changed", id: 1 });
  registry.dispatch({ event: "task.changed", id: 2 });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(invalidations, ["workforce"]);
  registry.destroy();
});

test("resync.required is delivered and its cursor is used for the next request", async () => {
  const calls = [];
  const received = [];
  let responseCount = 0;
  const client = createRealtimeClient({
    getSession: () => ({ key: "session-secret", tenant: "default" }),
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      responseCount += 1;
      return responseCount === 1
        ? responseFor('id: 5\nevent: resync.required\ndata: {"cursor":4,"oldest":5}\n\n')
        : responseFor(heartbeat(4));
    },
    sleep: async () => {},
  });
  client.subscribeEvents((event) => received.push(event));
  client.start();
  await waitFor(() => calls.length >= 2);
  assert.equal(received[0].event, "resync.required");
  assert.equal(calls[1].options.headers["X-ZWorkforce-Event-Cursor"], "4");
  client.stop();
});

test("stop aborts the active request and reports OFFLINE", async () => {
  let signal;
  const statuses = [];
  const client = createRealtimeClient({
    getSession: () => ({ key: "session-secret", tenant: "default" }),
    fetchImpl: async (url, options) => {
      signal = options.signal;
      return hangingResponse();
    },
  });
  client.subscribeStatus((state) => statuses.push(state));
  client.start();
  await waitFor(() => signal !== undefined);
  client.stop();
  assert.equal(signal.aborted, true);
  assert.equal(client.getState(), "OFFLINE");
  assert.equal(statuses.at(-1), "OFFLINE");
});

test("repeated fetch failures expose RECONNECTING then POLLING", async () => {
  const statuses = [];
  let failures = 0;
  const client = createRealtimeClient({
    getSession: () => ({ key: "session-secret", tenant: "default" }),
    fetchImpl: async () => {
      failures += 1;
      throw new Error("offline");
    },
    sleep: async () => {},
  });
  client.subscribeStatus((state) => statuses.push(state));
  client.start();
  await waitFor(() => client.getState() === "POLLING");
  assert.ok(failures >= 3);
  assert.ok(statuses.includes("RECONNECTING"));
  assert.ok(statuses.includes("POLLING"));
  client.stop();
});

test("realtime package exposes safe state labels and only calls the live label in LIVE", () => {
  const values = {
    dot: { dataset: {}, setAttribute() {} },
    text: {},
    region: { dataset: {} },
  };
  const root = {
    querySelector(selector) {
      return selector === "#realtimeDot" ? values.dot : selector === "#realtimeText" ? values.text : values.region;
    },
  };
  let listener;
  const client = { subscribeStatus(callback) { listener = callback; return () => {}; } };
  const mount = mountRealtimePackage({ root, client });
  listener("POLLING");
  assert.equal(values.text.textContent, "POLLING");
  assert.equal(values.region.textContent, "POLLING");
  listener("LIVE");
  assert.equal(values.text.textContent, "Realtime");
  assert.equal(values.dot.dataset.state, "LIVE");
  mount.destroy();
});
