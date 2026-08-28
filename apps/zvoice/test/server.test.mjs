import assert from "node:assert/strict";
import { once } from "node:events";
import test from "node:test";
import {
  createVoiceSession,
  createZarvisCommand,
  createZVoiceServer,
  healthSnapshot,
  ZARVIS_OWNER_GITHUB_ID,
} from "../server.mjs";

const EDGE_SECRET = "edge-secret-0123456789-012345678901";
const ORCHESTRATOR_TOKEN = "orchestrator-token-0123456789-012345";

function ownerHeaders(extra = {}) {
  return {
    "x-zarvis-owner-id": ZARVIS_OWNER_GITHUB_ID,
    "x-zarvis-edge-secret": EDGE_SECRET,
    ...extra,
  };
}

const ownerEnv = {
  Z_PLATFORM_VOICE_GATEWAY_URL: "http://voice-gateway:8450",
  Z_PLATFORM_SERVICE_TOKEN: "voice-service-token",
  ZVOICE_ZARVIS_MODE: "true",
  ZARVIS_EDGE_SHARED_SECRET: EDGE_SECRET,
  ZARVIS_ORCHESTRATOR_URL: "http://zarvis-orchestrator:8094",
  ZARVIS_ORCHESTRATOR_SERVICE_TOKEN: ORCHESTRATOR_TOKEN,
};

async function listen(server) {
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  return `http://127.0.0.1:${address.port}`;
}

test("health snapshot does not disclose secrets", () => {
  const result = healthSnapshot({
    ...ownerEnv,
    ZVOICE_ALLOW_ANONYMOUS: "true",
  });
  assert.equal(result.voice_gateway_configured, true);
  assert.equal(result.zarvis_owner_mode, true);
  assert.equal(result.zarvis_bridge_configured, true);
  assert.equal(result.anonymous_access, false);
  assert.equal(JSON.stringify(result).includes(EDGE_SECRET), false);
  assert.equal(JSON.stringify(result).includes(ORCHESTRATOR_TOKEN), false);
});

test("generic session request preserves backward-compatible identity proxying", async () => {
  let captured;
  const fetchImpl = async (url, options) => {
    captured = { url, options };
    return new Response(JSON.stringify({
      ticket: "signed-ticket",
      websocket_url: "ws://localhost:8450/v1/realtime",
      expires_at: "2030-01-01T00:00:00.000Z",
      ticket_transport: "sec-websocket-protocol",
    }), { status: 201, headers: { "Content-Type": "application/json" } });
  };

  const result = await createVoiceSession(
    { instructions: "Be helpful" },
    { headers: { "x-tenant-id": "tenant-1", "x-subject-id": "user-1" } },
    {
      Z_PLATFORM_VOICE_GATEWAY_URL: "http://voice-gateway:8450",
      Z_PLATFORM_SERVICE_TOKEN: "service-token",
      ZVOICE_ALLOW_ANONYMOUS: "false",
    },
    fetchImpl,
  );

  assert.equal(result.ticket, "signed-ticket");
  assert.equal(result.instructions, "Be helpful");
  assert.equal(result.zarvis_mode, undefined);
  assert.equal(captured.options.headers.Authorization, "Bearer service-token");
  assert.equal(captured.options.headers["X-Tenant-Id"], "tenant-1");
  assert.equal(captured.options.headers["X-Subject-Id"], "user-1");
});

test("owner mode protects static UI and APIs from direct-origin access", async (t) => {
  const server = createZVoiceServer({ env: ownerEnv });
  const baseUrl = await listen(server);
  t.after(() => server.close());

  const direct = await fetch(baseUrl);
  assert.equal(direct.status, 403);
  assert.equal((await direct.json()).error.code, "owner_access_denied");

  const owner = await fetch(baseUrl, { headers: ownerHeaders() });
  assert.equal(owner.status, 200);
  assert.match(await owner.text(), /ZVoice/i);
});

test("owner voice mode rejects a request that bypasses the trusted edge", async () => {
  await assert.rejects(
    createVoiceSession({}, { headers: {} }, ownerEnv, async () => {
      throw new Error("must not reach gateway");
    }),
    (error) => error.status === 403 && error.code === "owner_access_denied",
  );
});

test("owner voice mode replaces caller identity with immutable owner identity", async () => {
  let captured;
  const result = await createVoiceSession(
    { session_id: "voice-session-1" },
    { headers: ownerHeaders({ "x-tenant-id": "attacker", "x-subject-id": "attacker" }) },
    ownerEnv,
    async (url, options) => {
      captured = { url, options };
      return new Response(JSON.stringify({
        ticket: "signed-ticket",
        websocket_url: "ws://localhost:8450/v1/realtime",
      }), { status: 201, headers: { "content-type": "application/json" } });
    },
  );

  assert.equal(result.zarvis_mode, true);
  assert.equal(result.zarvis_session_id, "voice-session-1");
  assert.equal(captured.options.headers["X-Tenant-Id"], `owner-${ZARVIS_OWNER_GITHUB_ID}`);
  assert.equal(captured.options.headers["X-Subject-Id"], `github:${ZARVIS_OWNER_GITHUB_ID}`);
});

test("voice transcript bridge rejects missing transcripts before calling upstream", async () => {
  await assert.rejects(
    createZarvisCommand(
      { command_id: "command-1", session_id: "voice-session-1" },
      { headers: ownerHeaders() },
      ownerEnv,
      async () => {
        throw new Error("must not reach orchestrator");
      },
    ),
    /transcript is required/,
  );
});

test("voice transcript bridge forwards only the owner-bound command contract", async () => {
  let captured;
  const result = await createZarvisCommand(
    {
      command_id: "command-1",
      session_id: "voice-session-1",
      transcript: "ตรวจสถานะ GitHub cvsz/z-platform",
      locale: "th-TH",
    },
    { headers: ownerHeaders({ "x-user-id": "attacker", "x-tenant-id": "attacker" }) },
    ownerEnv,
    async (url, options) => {
      captured = { url, options, body: JSON.parse(options.body) };
      return new Response(JSON.stringify({
        schema_version: "zarvis.command.completed.v1",
        command_id: "command-1",
        session_id: "voice-session-1",
        status: "completed",
        replayed: false,
        speech: { locale: "th-TH", text: "เรียบร้อย" },
      }), { status: 200, headers: { "content-type": "application/json" } });
    },
  );

  assert.equal(result.status, "completed");
  assert.equal(captured.url, "http://zarvis-orchestrator:8094/v1/commands");
  assert.equal(captured.options.headers["X-Zarvis-Owner-Id"], ZARVIS_OWNER_GITHUB_ID);
  assert.equal(captured.options.headers["X-Zarvis-Service-Token"], ORCHESTRATOR_TOKEN);
  assert.equal(captured.options.headers["X-Tenant-Id"], undefined);
  assert.equal(captured.options.headers["X-User-Id"], undefined);
  assert.equal(captured.body.input.modality, "voice");
  assert.equal(captured.body.input.text, "ตรวจสถานะ GitHub cvsz/z-platform");
  assert.equal(JSON.stringify(result).includes(ORCHESTRATOR_TOKEN), false);
});
