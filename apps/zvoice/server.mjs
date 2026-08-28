import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { randomUUID, timingSafeEqual } from "node:crypto";
import { fileURLToPath } from "node:url";
import {
  executeLocalConversation,
  LocalConversationError,
  validateLocalLlmBaseUrl,
} from "./local-conversation.mjs";

export const ZARVIS_OWNER_GITHUB_ID = "4076926";

const MIN_SECRET_BYTES = 32;
const ID_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/;
const staticAssets = {
  "/": { file: "index.html", type: "text/html; charset=utf-8" },
  "/app.js": { file: "app.js", type: "text/javascript; charset=utf-8" },
  "/humanoid-view.js": { file: "humanoid-view.js", type: "text/javascript; charset=utf-8" },
  "/voice-worklet.js": { file: "voice-worklet.js", type: "text/javascript; charset=utf-8" },
  "/styles.css": { file: "styles.css", type: "text/css; charset=utf-8" },
  "/humanoid.css": { file: "humanoid.css", type: "text/css; charset=utf-8" },
};

const SECURITY_HEADERS = {
  "Cache-Control": "no-store",
  "Content-Security-Policy": [
    "default-src 'self'",
    "connect-src 'self' ws: wss:",
    "media-src 'self' blob:",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    "object-src 'none'",
    "base-uri 'none'",
    "frame-ancestors 'none'",
  ].join("; "),
  "Cross-Origin-Opener-Policy": "same-origin",
  "Permissions-Policy": "camera=(), geolocation=(), microphone=(self)",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
};

class HttpError extends Error {
  constructor(message, { status = 400, code = "invalid_request" } = {}) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function send(response, status, body, type = "application/json; charset=utf-8", headers = {}) {
  response.writeHead(status, {
    "Content-Type": type,
    "Content-Length": Buffer.byteLength(body),
    ...SECURITY_HEADERS,
    ...headers,
  });
  response.end(body);
}

async function json(request) {
  let size = 0;
  const chunks = [];
  for await (const chunk of request) {
    size += chunk.length;
    if (size > 32 * 1024) throw new HttpError("Request body is too large", { status: 413 });
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new HttpError("Request body must contain valid JSON");
  }
}

function cleanText(value, fallback, maxLength) {
  if (value == null || value === "") return fallback;
  if (typeof value !== "string") throw new HttpError("Expected text value");
  const text = value.trim();
  if (!text || text.length > maxLength) throw new HttpError("Invalid text value");
  return text;
}

function requiredText(value, field, maxLength) {
  const text = cleanText(value, undefined, maxLength);
  if (!text) throw new HttpError(`${field} is required`);
  return text;
}

function cleanId(value, fallback = randomUUID()) {
  const id = cleanText(value, fallback, 128);
  if (!ID_PATTERN.test(id)) throw new HttpError("Invalid identifier");
  return id;
}

function ownerMode(env) {
  return String(env.ZVOICE_ZARVIS_MODE || "false").toLowerCase() === "true";
}

function requireSecret(value, name) {
  if (typeof value !== "string" || Buffer.byteLength(value.trim()) < MIN_SECRET_BYTES) {
    throw new HttpError(`${name} must contain at least ${MIN_SECRET_BYTES} bytes.`, {
      status: 503,
      code: "service_not_configured",
    });
  }
  return value.trim();
}

function secretsMatch(actual, expected) {
  if (typeof actual !== "string") return false;
  const actualBuffer = Buffer.from(actual);
  const expectedBuffer = Buffer.from(expected);
  return actualBuffer.length === expectedBuffer.length && timingSafeEqual(actualBuffer, expectedBuffer);
}

function assertOwnerEdgeRequest(request, env) {
  const expectedSecret = requireSecret(env.ZARVIS_EDGE_SHARED_SECRET, "ZARVIS_EDGE_SHARED_SECRET");
  const ownerId = request.headers["x-zarvis-owner-id"]?.toString();
  const presentedSecret = request.headers["x-zarvis-edge-secret"]?.toString();
  if (ownerId !== ZARVIS_OWNER_GITHUB_ID || !secretsMatch(presentedSecret, expectedSecret)) {
    throw new HttpError("This private voice assistant is restricted to its owner.", {
      status: 403,
      code: "owner_access_denied",
    });
  }
}

function identity(request, env) {
  if (ownerMode(env)) {
    assertOwnerEdgeRequest(request, env);
    return {
      tenantId: `owner-${ZARVIS_OWNER_GITHUB_ID}`,
      subjectId: `github:${ZARVIS_OWNER_GITHUB_ID}`,
    };
  }

  const tenantId = String(request.headers["x-tenant-id"] || "").trim();
  const subjectId = String(
    request.headers["x-subject-id"] || request.headers["cf-access-authenticated-user-email"] || "",
  ).trim();
  const allowAnonymous = String(env.ZVOICE_ALLOW_ANONYMOUS || "false").toLowerCase() === "true";
  if (tenantId && subjectId) return { tenantId, subjectId };
  if (allowAnonymous) {
    return {
      tenantId: tenantId || "anonymous",
      subjectId: subjectId || "anonymous",
    };
  }
  throw new HttpError("Authenticated tenant and subject are required", {
    status: 401,
    code: "authentication_required",
  });
}

function localLlmSnapshot(env) {
  try {
    const endpoint = validateLocalLlmBaseUrl(env.ZARVIS_LOCAL_LLM_BASE_URL);
    return {
      configured: true,
      local_only: true,
      endpoint_host: endpoint.hostname,
      model: env.ZARVIS_LOCAL_LLM_MODEL || "qwen3:8b",
    };
  } catch {
    return {
      configured: false,
      local_only: false,
      endpoint_host: null,
      model: null,
    };
  }
}

export function healthSnapshot(env = process.env) {
  const isOwnerMode = ownerMode(env);
  const localLlm = localLlmSnapshot(env);
  return {
    status: "ok",
    service: "zvoice",
    voice_gateway_configured: Boolean(
      env.Z_PLATFORM_VOICE_GATEWAY_URL && env.Z_PLATFORM_SERVICE_TOKEN,
    ),
    anonymous_access: !isOwnerMode
      && String(env.ZVOICE_ALLOW_ANONYMOUS || "false").toLowerCase() === "true",
    zarvis_owner_mode: isOwnerMode,
    zarvis_bridge_configured: Boolean(
      isOwnerMode
      && env.ZARVIS_ORCHESTRATOR_URL
      && env.ZARVIS_ORCHESTRATOR_SERVICE_TOKEN
      && env.ZARVIS_EDGE_SHARED_SECRET,
    ),
    local_conversation_configured: localLlm.configured,
    local_llm_only: localLlm.local_only,
    local_llm_model: localLlm.model,
  };
}

export async function createVoiceSession(
  body,
  request,
  env = process.env,
  fetchImpl = fetch,
) {
  const gatewayUrl = env.Z_PLATFORM_VOICE_GATEWAY_URL?.replace(/\/$/, "");
  const serviceToken = env.Z_PLATFORM_SERVICE_TOKEN;
  if (!gatewayUrl || !serviceToken) {
    throw new HttpError("Voice gateway is not configured", {
      status: 503,
      code: "voice_gateway_not_configured",
    });
  }

  const { tenantId, subjectId } = identity(request, env);
  const instructions = cleanText(
    body.instructions,
    "You are a concise, helpful voice assistant. Reply in the user's language.",
    8000,
  );
  const model = cleanText(env.VOICE_LLM_MODEL, "default", 256);
  const requestId = request.headers["x-request-id"] || randomUUID();

  const result = await fetchImpl(`${gatewayUrl}/v1/voice/tickets`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${serviceToken}`,
      "Content-Type": "application/json",
      "X-Tenant-Id": tenantId,
      "X-Subject-Id": subjectId,
      "X-Request-Id": requestId,
    },
    body: JSON.stringify({ model }),
    signal: AbortSignal.timeout(5000),
  });

  const payload = await result.json().catch(() => ({}));
  if (!result.ok) {
    throw new HttpError(payload?.error?.message || "Voice gateway rejected the session request", {
      status: 502,
      code: "voice_gateway_rejected",
    });
  }

  const isOwnerMode = ownerMode(env);
  return {
    ...payload,
    model,
    instructions,
    ...(isOwnerMode ? {
      zarvis_mode: true,
      zarvis_session_id: cleanId(body.session_id),
    } : {}),
  };
}

async function localConversationFallback({
  commandId,
  sessionId,
  transcript,
  locale,
  env,
  fetchImpl,
}) {
  try {
    return await executeLocalConversation({
      commandId,
      sessionId,
      text: transcript,
      locale,
    }, {
      baseUrl: env.ZARVIS_LOCAL_LLM_BASE_URL,
      model: env.ZARVIS_LOCAL_LLM_MODEL || env.VOICE_LLM_MODEL || "qwen3:8b",
      apiKey: env.ZARVIS_LOCAL_LLM_API_KEY || "",
      fetchImpl,
      timeoutMs: Number(env.ZARVIS_LOCAL_LLM_TIMEOUT_MS || 45_000),
    });
  } catch (error) {
    if (error instanceof LocalConversationError) {
      throw new HttpError(error.message, { status: error.status, code: error.code });
    }
    throw error;
  }
}

export async function createZarvisCommand(
  body,
  request,
  env = process.env,
  fetchImpl = fetch,
) {
  if (!ownerMode(env)) {
    throw new HttpError("ZARVIS bridge is not enabled", {
      status: 404,
      code: "zarvis_bridge_disabled",
    });
  }
  assertOwnerEdgeRequest(request, env);

  const orchestratorUrl = env.ZARVIS_ORCHESTRATOR_URL?.replace(/\/$/, "");
  if (!orchestratorUrl) {
    throw new HttpError("ZARVIS orchestrator is not configured", {
      status: 503,
      code: "service_not_configured",
    });
  }
  const serviceToken = requireSecret(
    env.ZARVIS_ORCHESTRATOR_SERVICE_TOKEN,
    "ZARVIS_ORCHESTRATOR_SERVICE_TOKEN",
  );
  const transcript = requiredText(body.transcript, "transcript", 2000);
  const sessionId = cleanId(body.session_id);
  const commandId = cleanId(body.command_id);
  const locale = cleanText(body.locale, "th-TH", 32);
  const requestId = request.headers["x-request-id"] || randomUUID();

  const upstream = await fetchImpl(`${orchestratorUrl}/v1/commands`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Request-Id": requestId,
      "X-Zarvis-Owner-Id": ZARVIS_OWNER_GITHUB_ID,
      "X-Zarvis-Service-Token": serviceToken,
    },
    body: JSON.stringify({
      schema_version: "zarvis.command.requested.v1",
      command_id: commandId,
      session_id: sessionId,
      input: {
        modality: "voice",
        text: transcript,
        locale,
      },
    }),
    redirect: "error",
    signal: AbortSignal.timeout(10_000),
  });

  const payload = await upstream.json().catch(() => ({}));
  if (upstream.ok) return payload;

  if (
    payload?.error?.code === "unsupported_intent"
    && env.ZARVIS_LOCAL_LLM_BASE_URL
  ) {
    return localConversationFallback({
      commandId,
      sessionId,
      transcript,
      locale,
      env,
      fetchImpl,
    });
  }

  throw new HttpError(payload?.error?.message || "ZARVIS command failed", {
    status: upstream.status >= 400 && upstream.status < 500 ? upstream.status : 502,
    code: payload?.error?.code || "zarvis_command_failed",
  });
}

export function createZVoiceRequestHandler({ env = process.env, fetchImpl = fetch } = {}) {
  return async (request, response) => {
    try {
      const url = new URL(request.url || "/", "http://zvoice.local");
      if (request.method === "GET" && url.pathname === "/health/live") {
        return send(response, 200, JSON.stringify({ status: "ok", service: "zvoice" }));
      }
      if (request.method === "GET" && url.pathname === "/health") {
        return send(response, 200, JSON.stringify(healthSnapshot(env)));
      }

      if (ownerMode(env)) assertOwnerEdgeRequest(request, env);

      if (request.method === "POST" && url.pathname === "/api/voice/session") {
        const body = await json(request);
        const session = await createVoiceSession(body, request, env, fetchImpl);
        return send(response, 201, JSON.stringify(session));
      }
      if (request.method === "POST" && url.pathname === "/api/zarvis/command") {
        const body = await json(request);
        const result = await createZarvisCommand(body, request, env, fetchImpl);
        return send(response, 200, JSON.stringify(result));
      }

      const asset = staticAssets[url.pathname];
      if (request.method === "GET" && asset) {
        const content = await readFile(new URL(`./public/${asset.file}`, import.meta.url));
        return send(response, 200, content, asset.type, {
          "Cache-Control": asset.file === "index.html" ? "no-store" : "public, max-age=300",
        });
      }
      return send(response, 404, JSON.stringify({ error: { code: "not_found", message: "Not found" } }));
    } catch (error) {
      const status = Number.isInteger(error?.status) ? error.status : 400;
      return send(
        response,
        status,
        JSON.stringify({
          error: {
            code: error?.code || "request_failed",
            message: error instanceof Error ? error.message : "Request failed",
          },
        }),
      );
    }
  };
}

export function createZVoiceServer(options = {}) {
  return createServer(createZVoiceRequestHandler(options));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const host = process.env.HOST || "127.0.0.1";
  const port = Number(process.env.PORT || 3022);
  createZVoiceServer().listen(port, host, () => {
    process.stdout.write(`${JSON.stringify({
      timestamp: new Date().toISOString(),
      level: "info",
      service: "zvoice",
      event: "listening",
      host,
      port,
    })}\n`);
  });
}
