import { createServer } from "node:http";
import { randomUUID, timingSafeEqual } from "node:crypto";
import { fileURLToPath } from "node:url";
import { AgentOrchestratorError } from "../agent-orchestrator/server.mjs";
import {
  ZarvisTaskRuntime,
  ZARVIS_OWNER_GITHUB_ID,
} from "./runtime.mjs";

const MAX_BODY_BYTES = 64 * 1024;
const MIN_SECRET_BYTES = 32;
const TASK_PATH = /^\/v1\/tasks\/([A-Za-z0-9._:-]{1,128})$/;
const TASK_ACTION_PATH = /^\/v1\/tasks\/([A-Za-z0-9._:-]{1,128})\/(approve|pause|resume|cancel|retry)$/;

class TaskAccessError extends Error {
  constructor(message = "This private Z.A.R.V.I.S. task runtime is restricted to its owner.") {
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
    throw new TaskAccessError();
  }
}

function assertWorker(request, workerToken) {
  const token = request.headers.authorization?.replace(/^Bearer\s+/i, "");
  if (!secretsMatch(token, workerToken)) {
    throw new TaskAccessError("Worker authentication failed.");
  }
}

function writeJson(response, status, payload) {
  const body = JSON.stringify(payload);
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(body),
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
  });
  response.end(body);
}

async function readJson(request) {
  const contentType = request.headers["content-type"] ?? "";
  if (!contentType.toLowerCase().startsWith("application/json")) {
    throw new AgentOrchestratorError("Content-Type must be application/json", 415);
  }
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) {
      throw new AgentOrchestratorError("Request body is too large", 413);
    }
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new AgentOrchestratorError("Request body must contain valid JSON", 400);
  }
}

export function createZarvisTaskServer({
  env = process.env,
  runtime,
  edgeSecret = env.ZARVIS_EDGE_SHARED_SECRET,
  workerToken = env.ZARVIS_TASK_WORKER_TOKEN,
  rootDir = env.AGENT_DATA_DIR ?? "./data/zarvis-tasks",
  logger = console,
} = {}) {
  const trustedEdgeSecret = requireSecret(edgeSecret, "ZARVIS_EDGE_SHARED_SECRET");
  const trustedWorkerToken = requireSecret(workerToken, "ZARVIS_TASK_WORKER_TOKEN");
  const tasks = runtime ?? new ZarvisTaskRuntime({ rootDir });

  return createServer(async (request, response) => {
    const requestId = request.headers["x-request-id"]?.toString().slice(0, 160) || randomUUID();
    response.setHeader("X-Request-Id", requestId);

    try {
      const url = new URL(request.url ?? "/", "http://localhost");
      if (request.method === "GET" && url.pathname === "/healthz") {
        writeJson(response, 200, {
          status: "ok",
          service: "zarvis-task-gateway",
          version: "0.1.0",
          owner_only: true,
          durable_tasks: true,
          mutating_tools_enabled: false,
        });
        return;
      }

      if (request.method === "POST" && url.pathname === "/v1/internal/worker/run-next") {
        assertWorker(request, trustedWorkerToken);
        const job = await tasks.runNext();
        writeJson(response, 200, job ?? { status: "idle" });
        return;
      }

      assertOwner(request, trustedEdgeSecret);

      if (request.method === "GET" && url.pathname === "/v1/tasks") {
        writeJson(response, 200, { tasks: await tasks.listPlans() });
        return;
      }

      if (request.method === "POST" && url.pathname === "/v1/tasks") {
        const result = await tasks.submitPlan(await readJson(request));
        writeJson(response, result.status, result.job);
        return;
      }

      const taskMatch = url.pathname.match(TASK_PATH);
      if (request.method === "GET" && taskMatch) {
        writeJson(response, 200, await tasks.get(taskMatch[1]));
        return;
      }

      const actionMatch = url.pathname.match(TASK_ACTION_PATH);
      if (request.method === "POST" && actionMatch) {
        const [, taskId, action] = actionMatch;
        const input = await readJson(request);
        let result;
        if (action === "approve") result = await tasks.approvePlan(taskId, input);
        else if (action === "pause") result = await tasks.pause(taskId);
        else if (action === "resume") result = await tasks.resume(taskId);
        else if (action === "cancel") result = await tasks.cancelPlan(taskId);
        else if (action === "retry") result = await tasks.retry(taskId);
        writeJson(response, 200, result);
        return;
      }

      writeJson(response, 404, {
        error: { code: "route_not_found", message: "Route not found", request_id: requestId },
      });
    } catch (error) {
      const status = error instanceof AgentOrchestratorError || error instanceof TaskAccessError
        ? error.status
        : 500;
      if (status >= 500) {
        logger.error("zarvis task request failed", {
          request_id: requestId,
          message: error?.message,
        });
      }
      writeJson(response, status, {
        error: {
          code: error?.code ?? (status === 500 ? "internal_error" : "task_request_failed"),
          message: status >= 500 ? "The task request could not be completed." : error.message,
          request_id: requestId,
        },
      });
    }
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const host = process.env.HOST ?? "127.0.0.1";
  const port = Number(process.env.PORT ?? 8096);
  createZarvisTaskServer().listen(port, host, () => {
    console.info(`zarvis-task-gateway listening on http://${host}:${port}`);
  });
}
