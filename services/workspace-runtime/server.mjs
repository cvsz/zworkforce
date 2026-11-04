import { createServer } from "node:http";
import { createHmac, randomUUID, timingSafeEqual } from "node:crypto";
import { fileURLToPath } from "node:url";

const defaultHost = process.env.HOST || "127.0.0.1";
const defaultPort = Number(process.env.PORT || 8600);

export class WorkspaceRuntimeError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.status = status;
  }
}

function send(response, status, body) {
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(body));
}

function authorized(request, env) {
  const token = request.headers.authorization?.replace(/^Bearer\s+/i, "");
  const expected = env.Z_PLATFORM_SERVICE_TOKEN;
  if (!token || !expected) return false;
  const a = Buffer.from(token);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

async function readJson(request) {
  let text = "";
  for await (const chunk of request) {
    text += chunk;
    if (text.length > 100000) throw new WorkspaceRuntimeError("Request body is too large", 413);
  }
  return text.trim() ? JSON.parse(text) : {};
}

export function computeApprovalSignature(action, approval, targetValue, secret) {
  const requester = String(approval?.requester_id || "");
  const approver = String(approval?.approver_id || "");
  const expiresAt = String(approval?.expires_at || "");
  const payload = `${action}:${requester}:${approver}:${expiresAt}:${String(targetValue || "")}`;
  return createHmac("sha256", secret).update(payload).digest("hex");
}

function requireApproval(input, action, env = process.env, nowIso = () => new Date().toISOString()) {
  if (!input.approval || input.approval.state !== "approved") throw new WorkspaceRuntimeError(`${action} requires explicit approval`, 403);
  if (!Array.isArray(input.approval.grants) || !input.approval.grants.includes(action)) throw new WorkspaceRuntimeError(`${action} approval grant is missing`, 403);

  const requesterId = typeof input.approval.requester_id === "string" ? input.approval.requester_id.trim() : "";
  const approverId = typeof input.approval.approver_id === "string" ? input.approval.approver_id.trim() : "";
  const requireFourEyes = env.Z_PLATFORM_REQUIRE_FOUR_EYES === "true" || Boolean(requesterId || approverId);
  if (requireFourEyes) {
    if (!requesterId || !approverId) {
      throw new WorkspaceRuntimeError("four-eyes approval requires both requester_id and approver_id", 403);
    }
    if (requesterId === approverId) {
      throw new WorkspaceRuntimeError("four-eyes approval prohibits self-approval", 403);
    }
  }

  if (input.approval.expires_at !== undefined) {
    const expiresMs = Date.parse(String(input.approval.expires_at));
    const currentMs = Date.parse(nowIso());
    if (Number.isNaN(expiresMs) || expiresMs <= currentMs) {
      throw new WorkspaceRuntimeError("approval has expired", 403);
    }
  }

  const signingSecret = env.Z_PLATFORM_APPROVAL_SIGNING_SECRET;
  if (signingSecret) {
    const targetValue = action === "shell" ? input.command : input.target;
    const expectedSig = computeApprovalSignature(action, input.approval, targetValue, signingSecret);
    const providedSig = typeof input.approval.signature === "string" ? input.approval.signature : "";
    const a = Buffer.from(providedSig);
    const b = Buffer.from(expectedSig);
    if (!providedSig || a.length !== b.length || !timingSafeEqual(a, b)) {
      throw new WorkspaceRuntimeError("approval signature is invalid or missing", 403);
    }
  }
}

function assertSafeProject(input) {
  if (typeof input.project_id !== "string" || !/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$/.test(input.project_id)) throw new WorkspaceRuntimeError("project_id is invalid");
  for (const file of input.files || []) {
    if (typeof file.path !== "string" || file.path.startsWith("/") || file.path.includes("..")) throw new WorkspaceRuntimeError("generated file path is unsafe");
    if (/\.env$|\.pem$|\.key$|terraform\.tfvars$/.test(file.path)) throw new WorkspaceRuntimeError("secret-bearing generated files are prohibited");
    if (file.owner !== "generator") throw new WorkspaceRuntimeError("generated files must declare generator ownership");
  }
}

export class WorkspaceRuntime {
  constructor({ idGenerator = randomUUID, now = () => new Date().toISOString(), env = process.env } = {}) {
    this.idGenerator = idGenerator;
    this.now = now;
    this.env = env;
  }

  validateGeneratedProject(input) {
    assertSafeProject(input);
    return {
      validation_id: this.idGenerator(),
      status: "validated",
      project_id: input.project_id,
      file_count: (input.files || []).length,
      checked_at: this.now(),
    };
  }

  requestShell(input) {
    requireApproval(input, "shell", this.env, this.now);
    return { request_id: this.idGenerator(), status: "accepted", action: "shell", command: input.command, accepted_at: this.now() };
  }

  requestDeploy(input) {
    requireApproval(input, "deploy", this.env, this.now);
    return { request_id: this.idGenerator(), status: "accepted", action: "deploy", target: input.target, accepted_at: this.now() };
  }
}

export function createWorkspaceRuntimeServer({ env = process.env, runtime = new WorkspaceRuntime({ env }) } = {}) {
  return createServer(async (request, response) => {
    if (request.method === "GET" && request.url === "/health") return send(response, 200, { status: "ok", service: "workspace-runtime", sandbox: "approval-gated" });
    if (!authorized(request, env)) return send(response, 401, { error: "Unauthorized" });

    try {
      if (request.method === "POST" && request.url === "/v1/projects/validate") return send(response, 200, runtime.validateGeneratedProject(await readJson(request)));
      if (request.method === "POST" && request.url === "/v1/shell") return send(response, 202, runtime.requestShell(await readJson(request)));
      if (request.method === "POST" && request.url === "/v1/deploy") return send(response, 202, runtime.requestDeploy(await readJson(request)));
      return send(response, 404, { error: "Not found" });
    } catch (error) {
      return send(response, error instanceof WorkspaceRuntimeError ? error.status : 400, { error: error.message || "Request failed" });
    }
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  createWorkspaceRuntimeServer().listen(defaultPort, defaultHost, () => {
    console.log("workspace-runtime listening on http://" + defaultHost + ":" + defaultPort);
  });
}
