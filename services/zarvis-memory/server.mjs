import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { randomUUID, timingSafeEqual } from "node:crypto";
import { fileURLToPath } from "node:url";
import { EncryptedMemoryStore, parseMemoryMasterKey } from "./crypto-store.mjs";
import {
  MemoryValidationError,
  ZarvisMemoryRuntime,
  ZARVIS_OWNER_GITHUB_ID,
} from "./runtime.mjs";

const MAX_BODY_BYTES = 64 * 1024;
const MIN_SECRET_BYTES = 32;
const PROPOSAL_CONFIRM = /^\/v1\/memory\/proposals\/([A-Za-z0-9._:-]{1,128})\/confirm$/;
const MEMORY_PATH = /^\/v1\/memories\/([A-Za-z0-9._:-]{1,128})$/;
const CORRECTION_PATH = /^\/v1\/memories\/([A-Za-z0-9._:-]{1,128})\/corrections$/;
const STATIC = new Map([
  ["/", ["index.html", "text/html; charset=utf-8"]],
  ["/app.js", ["app.js", "text/javascript; charset=utf-8"]],
  ["/styles.css", ["styles.css", "text/css; charset=utf-8"]],
]);

class MemoryAccessError extends Error {
  constructor(message = "This private Z.A.R.V.I.S. memory service is restricted to its owner.") {
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
  const ownerId = request.headers["x-zarvis-owner-id"]?.toString();
  const secret = request.headers["x-zarvis-edge-secret"]?.toString();
  if (ownerId !== ZARVIS_OWNER_GITHUB_ID || !secretsMatch(secret, edgeSecret)) {
    throw new MemoryAccessError();
  }
}

function assertWorker(request, workerToken) {
  const token = request.headers.authorization?.replace(/^Bearer\s+/i, "");
  if (!secretsMatch(token, workerToken)) {
    throw new MemoryAccessError("Memory worker authentication failed.");
  }
}

function write(response, status, body, contentType = "application/json; charset=utf-8") {
  response.writeHead(status, {
    "Content-Type": contentType,
    "Content-Length": Buffer.byteLength(body),
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
  });
  response.end(body);
}

function writeJson(response, status, payload) {
  write(response, status, JSON.stringify(payload));
}

async function readJson(request) {
  const contentType = request.headers["content-type"] ?? "";
  if (!contentType.toLowerCase().startsWith("application/json")) {
    throw new MemoryValidationError("Content-Type must be application/json", 415);
  }
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) throw new MemoryValidationError("Request body is too large", 413);
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new MemoryValidationError("Request body must contain valid JSON");
  }
}

export function createZarvisMemoryServer({
  env = process.env,
  runtime,
  edgeSecret = env.ZARVIS_EDGE_SHARED_SECRET,
  workerToken = env.ZARVIS_MEMORY_WORKER_TOKEN,
  masterKey = env.ZARVIS_MEMORY_MASTER_KEY_B64,
  rootDir = env.ZARVIS_MEMORY_DATA_DIR ?? "./data/zarvis-memory",
  logger = console,
} = {}) {
  const trustedEdgeSecret = requireSecret(edgeSecret, "ZARVIS_EDGE_SHARED_SECRET");
  const trustedWorkerToken = requireSecret(workerToken, "ZARVIS_MEMORY_WORKER_TOKEN");
  const memory = runtime ?? new ZarvisMemoryRuntime({
    store: new EncryptedMemoryStore({
      rootDir,
      masterKey: parseMemoryMasterKey(masterKey),
    }),
  });

  return createServer(async (request, response) => {
    const requestId = request.headers["x-request-id"]?.toString().slice(0, 160) || randomUUID();
    response.setHeader("X-Request-Id", requestId);
    try {
      const url = new URL(request.url ?? "/", "http://localhost");
      if (request.method === "GET" && url.pathname === "/healthz") {
        writeJson(response, 200, {
          status: "ok",
          service: "zarvis-memory",
          version: "0.1.0",
          owner_only: true,
          encrypted_at_rest: true,
          silent_long_term_writes: false,
        });
        return;
      }

      if (request.method === "POST" && url.pathname === "/v1/internal/memory/purge-expired") {
        assertWorker(request, trustedWorkerToken);
        writeJson(response, 200, await memory.purgeExpired());
        return;
      }

      assertOwner(request, trustedEdgeSecret);

      if (request.method === "POST" && url.pathname === "/v1/memory/proposals") {
        writeJson(response, 202, await memory.createProposal(await readJson(request)));
        return;
      }

      const confirmMatch = url.pathname.match(PROPOSAL_CONFIRM);
      if (request.method === "POST" && confirmMatch) {
        writeJson(response, 200, await memory.confirmProposal(confirmMatch[1], await readJson(request)));
        return;
      }

      if (request.method === "GET" && url.pathname === "/v1/memories") {
        writeJson(response, 200, {
          memories: await memory.listMemories({
            query: url.searchParams.get("q") ?? "",
            classification: url.searchParams.get("classification"),
          }),
        });
        return;
      }

      if (request.method === "GET" && url.pathname === "/v1/memories/export") {
        writeJson(response, 200, await memory.exportMemories());
        return;
      }

      const correctionMatch = url.pathname.match(CORRECTION_PATH);
      if (request.method === "POST" && correctionMatch) {
        writeJson(response, 202, await memory.proposeCorrection(correctionMatch[1], await readJson(request)));
        return;
      }

      const memoryMatch = url.pathname.match(MEMORY_PATH);
      if (request.method === "GET" && memoryMatch) {
        writeJson(response, 200, await memory.getMemory(memoryMatch[1]));
        return;
      }
      if (request.method === "DELETE" && memoryMatch) {
        if (request.headers["x-zarvis-confirm-delete"]?.toString() !== memoryMatch[1]) {
          throw new MemoryValidationError(
            `Set x-zarvis-confirm-delete to ${memoryMatch[1]} to delete this memory`,
            428,
            "confirmation_required",
          );
        }
        writeJson(response, 200, await memory.deleteMemory(memoryMatch[1]));
        return;
      }

      const asset = STATIC.get(url.pathname);
      if (request.method === "GET" && asset) {
        const content = await readFile(new URL(`./public/${asset[0]}`, import.meta.url));
        write(response, 200, content, asset[1]);
        return;
      }

      writeJson(response, 404, {
        error: { code: "route_not_found", message: "Route not found", request_id: requestId },
      });
    } catch (error) {
      const status = error instanceof MemoryValidationError || error instanceof MemoryAccessError
        ? error.status
        : 500;
      if (status >= 500) {
        logger.error("zarvis memory request failed", {
          request_id: requestId,
          message: error?.message,
        });
      }
      writeJson(response, status, {
        error: {
          code: error?.code ?? (status === 500 ? "internal_error" : "memory_request_failed"),
          message: status >= 500 ? "The memory request could not be completed." : error.message,
          request_id: requestId,
        },
      });
    }
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const host = process.env.HOST ?? "127.0.0.1";
  const port = Number(process.env.PORT ?? 8097);
  createZarvisMemoryServer().listen(port, host, () => {
    console.info(`zarvis-memory listening on http://${host}:${port}`);
  });
}
