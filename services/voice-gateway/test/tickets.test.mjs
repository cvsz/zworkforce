import assert from "node:assert/strict";
import test from "node:test";
import { createTicketCodec, createVoiceGateway, parseBearer } from "../index.mjs";

const TEST_ENV = {
  Z_PLATFORM_SERVICE_TOKEN: "service-token",
  VOICE_TICKET_SECRET: "a".repeat(64),
  VOICE_AGENT_URL: "http://127.0.0.1:65534",
  VOICE_PUBLIC_WS_URL: "ws://127.0.0.1:8450/v1/realtime",
  VOICE_ALLOW_ANONYMOUS: "false",
};

test("parseBearer accepts a bearer token", () => {
  assert.equal(parseBearer("Bearer secret"), "secret");
  assert.equal(parseBearer("basic secret"), null);
});

test("ticket is signed, expires, and is single-use", () => {
  let now = 1_700_000_000_000;
  const codec = createTicketCodec("a".repeat(64), { now: () => now });
  const issued = codec.issue({ tenantId: "tenant-1", subjectId: "user-1", ttlSeconds: 60 });

  const claims = codec.verify(issued.ticket);
  assert.equal(claims.tenant_id, "tenant-1");
  assert.equal(claims.subject_id, "user-1");
  assert.throws(() => codec.verify(issued.ticket), /already used/);

  const second = codec.issue({ tenantId: "tenant-1", subjectId: "user-1", ttlSeconds: 10 });
  now += 11_000;
  assert.throws(() => codec.verify(second.ticket), /Expired/);
});

test("tampered tickets are rejected", () => {
  const codec = createTicketCodec("b".repeat(64));
  const issued = codec.issue({ tenantId: "tenant-1", subjectId: "user-1" });
  assert.throws(() => codec.verify(`${issued.ticket}x`), /signature/);
});

test("ticket endpoint requires service authentication and returns browser-safe fields", async (t) => {
  const { server, codec } = createVoiceGateway({ env: TEST_ENV });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(() => new Promise((resolve) => server.close(resolve)));
  const address = server.address();
  const endpoint = `http://127.0.0.1:${address.port}/v1/voice/tickets`;

  const unauthorized = await fetch(endpoint, { method: "POST", body: "{}" });
  assert.equal(unauthorized.status, 401);

  const authorized = await fetch(endpoint, {
    method: "POST",
    headers: {
      Authorization: "Bearer service-token",
      "Content-Type": "application/json",
      "X-Tenant-Id": "tenant-1",
      "X-Subject-Id": "user-1",
    },
    body: "{}",
  });
  assert.equal(authorized.status, 201);
  const payload = await authorized.json();
  assert.equal(payload.websocket_url, TEST_ENV.VOICE_PUBLIC_WS_URL);
  assert.equal(payload.ticket_transport, "sec-websocket-protocol");
  assert.equal(JSON.stringify(payload).includes(TEST_ENV.Z_PLATFORM_SERVICE_TOKEN), false);

  const claims = codec.verify(payload.ticket, { consume: false });
  assert.equal(claims.tenant_id, "tenant-1");
  assert.equal(claims.subject_id, "user-1");
});
