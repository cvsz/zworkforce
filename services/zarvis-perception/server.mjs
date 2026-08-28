import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { randomUUID, timingSafeEqual } from "node:crypto";
import { fileURLToPath } from "node:url";
import { EncryptedPerceptionStore, parsePerceptionKey } from "./crypto-store.mjs";
import {
  PerceptionValidationError,
  ZarvisPerceptionRuntime,
  ZARVIS_OWNER_GITHUB_ID,
} from "./runtime.mjs";

const MAX_BODY_BYTES = 8 * 1024 * 1024;
const MIN_SECRET_BYTES = 32;
const SESSION_PATH = /^\/v1\/perception\/sessions\/([A-Za-z0-9._:-]{1,128})$/;
const SESSION_ACTION = /^\/v1\/perception\/sessions\/([A-Za-z0-9._:-]{1,128})\/(activate|stop|media)$/;
const STATIC = new Map([
  ["/", ["index.html", "text/html; charset=utf-8"]],
  ["/app.js", ["app.js", "text/javascript; charset=utf-8"]],
  ["/styles.css", ["styles.css", "text/css; charset=utf-8"]],
]);

class PerceptionAccessError extends Error {
  constructor(message = "This private Z.A.R.V.I.S. perception service is restricted to its owner.") {
    super(message);
    this.status = 403;
    this.code = "owner_access_denied";
  }
}

function requireSecret(value, name) {
  if (typeof value !== "string" || Buffer.byteLength(value.trim()) < MIN_SECRET_BYTES) {
    throw new Error(`${name} must contain at least ${MIN_SECRET_BYTES} bytes.`);
  }
  return value.trim();
}

function secretsMatch(actual, expected) {
  if (typeof actual !== "string") return false;
  const a = Buffer.from(actual);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

function assertOwner(request, edgeSecret) {
  if (request.headers["x-zarvis-owner-id"]?.toString() !== ZARVIS_OWNER_GITHUB_ID
    || !secretsMatch(request.headers["x-zarvis-edge-secret"]?.toString(), edgeSecret)) {
    throw new PerceptionAccessError();
  }
}

function assertWorker(request, workerToken) {
  const token = request.headers.authorization?.replace(/^Bearer\s+/i, "");
  if (!secretsMatch(token, workerToken)) throw new PerceptionAccessError("Perception worker authentication failed.");
}

function write(response, status, body, contentType = "application/json; charset=utf-8") {
  response.writeHead(status, {
    "Content-Type": contentType,
    "Content-Length": Buffer.byteLength(body),
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "camera=(self), display-capture=(self), microphone=()",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
  });
  response.end(body);
}

function writeJson(response, status, payload) { write(response, status, JSON.stringify(payload)); }

async function readJson(request) {
  if (!(request.headers["content-type"] ?? "").toLowerCase().startsWith("application/json")) {
    throw new PerceptionValidationError("Content-Type must be application/json", 415);
  }
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) throw new PerceptionValidationError("Request body is too large", 413);
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  try { return JSON.parse(Buffer.concat(chunks).toString("utf8")); }
  catch { throw new PerceptionValidationError("Request body must contain valid JSON"); }
}

export function createZarvisPerceptionServer({
  env = process.env,
  runtime,
  edgeSecret = env.ZARVIS_EDGE_SHARED_SECRET,
  workerToken = env.ZARVIS_PERCEPTION_WORKER_TOKEN,
  masterKey = env.ZARVIS_PERCEPTION_MASTER_KEY_B64,
  rootDir = env.ZARVIS_PERCEPTION_DATA_DIR ?? "./data/zarvis-perception",
  logger = console,
} = {}) {
  const trustedEdgeSecret = requireSecret(edgeSecret, "ZARVIS_EDGE_SHARED_SECRET");
  const trustedWorkerToken = requireSecret(workerToken, "ZARVIS_PERCEPTION_WORKER_TOKEN");
  const perception = runtime ?? new ZarvisPerceptionRuntime({
    store: new EncryptedPerceptionStore({ rootDir, masterKey: parsePerceptionKey(masterKey) }),
  });

  return createServer(async (request, response) => {
    const requestId = request.headers["x-request-id"]?.toString().slice(0, 160) || randomUUID();
    response.setHeader("X-Request-Id", requestId);
    try {
      const url = new URL(request.url ?? "/", "http://localhost");
      if (request.method === "GET" && url.pathname === "/healthz") {
        writeJson(response, 200, {
          status: "ok",
          service: "zarvis-perception",
          version: "0.1.0",
          owner_only: true,
          encrypted_analysis: true,
          raw_media_retained: false,
          continuous_capture: false,
          biometric_identification: false,
        });
        return;
      }

      if (request.method === "POST" && url.pathname === "/v1/internal/perception/purge-expired") {
        assertWorker(request, trustedWorkerToken);
        writeJson(response, 200, await perception.purgeExpired());
        return;
      }

      assertOwner(request, trustedEdgeSecret);

      if (request.method === "GET" && url.pathname === "/v1/perception/sessions") {
        writeJson(response, 200, { sessions: await perception.listSessions() });
        return;
      }
      if (request.method === "POST" && url.pathname === "/v1/perception/sessions") {
        writeJson(response, 202, await perception.createSession(await readJson(request)));
        return;
      }

      const actionMatch = url.pathname.match(SESSION_ACTION);
      if (request.method === "POST" && actionMatch) {
        const [, sessionId, action] = actionMatch;
        let result;
        if (action === "activate") result = await perception.activateSession(sessionId, await readJson(request));
        else if (action === "stop") result = await perception.stopSession(sessionId);
        else result = await perception.analyzeMedia(sessionId, await readJson(request));
        writeJson(response, 200, result);
        return;
      }

      const sessionMatch = url.pathname.match(SESSION_PATH);
      if (request.method === "GET" && sessionMatch) {
        writeJson(response, 200, await perception.getSession(sessionMatch[1]));
        return;
      }
      if (request.method === "DELETE" && sessionMatch) {
        if (request.headers["x-zarvis-confirm-delete"]?.toString() !== sessionMatch[1]) {
          throw new PerceptionValidationError(
            `Set x-zarvis-confirm-delete to ${sessionMatch[1]} to delete this perception session`,
            428,
            "confirmation_required",
          );
        }
        writeJson(response, 200, await perception.deleteSession(sessionMatch[1]));
        return;
      }

      const asset = STATIC.get(url.pathname);
      if (request.method === "GET" && asset) {
        const content = await readFile(new URL(`./public/${asset[0]}`, import.meta.url));
        write(response, 200, content, asset[1]);
        return;
      }

      writeJson(response, 404, { error: { code: "route_not_found", message: "Route not found", request_id: requestId } });
    } catch (error) {
      const status = error instanceof PerceptionValidationError || error instanceof PerceptionAccessError
        ? error.status
        : 500;
      if (status >= 500) logger.error("zarvis perception request failed", { request_id: requestId, message: error?.message });
      writeJson(response, status, {
        error: {
          code: error?.code ?? (status === 500 ? "internal_error" : "perception_request_failed"),
          message: status >= 500 ? "The perception request could not be completed." : error.message,
          request_id: requestId,
        },
      });
    }
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const host = process.env.HOST ?? "127.0.0.1";
  const port = Number(process.env.PORT ?? 8098);
  createZarvisPerceptionServer().listen(port, host, () => console.info(`zarvis-perception listening on http://${host}:${port}`));
}
