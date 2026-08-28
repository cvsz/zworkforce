import { createServer } from "node:http";
import { randomUUID, timingSafeEqual } from "node:crypto";
import { fileURLToPath } from "node:url";

const defaultHost = process.env.HOST || "127.0.0.1";
const defaultPort = Number(process.env.PORT || 8500);
const TERMINAL = new Set(["succeeded", "failed", "cancelled", "expired"]);

export class AgentOrchestratorError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.status = status;
  }
}

function json(response, status, body) {
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

async function body(request) {
  let text = "";
  for await (const chunk of request) {
    text += chunk;
    if (text.length > 100000) throw new AgentOrchestratorError("Request body is too large", 413);
  }
  if (!text.trim()) return {};
  try {
    return JSON.parse(text);
  } catch {
    throw new AgentOrchestratorError("Request body must be valid JSON", 400);
  }
}

function requireString(value, name) {
  if (typeof value !== "string" || !value.trim()) throw new AgentOrchestratorError(`${name} is required`, 400);
  return value.trim();
}

function normalizeToolGrant(value) {
  if (typeof value === "string") {
    return { tool: value, scope: "*", mutating: !/:read$|\.read$/.test(value) };
  }
  if (!value || typeof value !== "object") throw new AgentOrchestratorError("tool grant is invalid", 400);
  return {
    tool: requireString(value.tool, "tool"),
    scope: requireString(value.scope ?? "*", "scope"),
    mutating: Boolean(value.mutating),
  };
}

function normalizeToolGrants(value, { allowEmpty = false } = {}) {
  if (!Array.isArray(value)) throw new AgentOrchestratorError("tool_grants must be an array", 400);
  if (!allowEmpty && value.length === 0) throw new AgentOrchestratorError("tool_grants must not be empty", 400);
  return value.map(normalizeToolGrant);
}

function grantKey(grant) {
  return `${grant.tool}\n${grant.scope}\n${grant.mutating}`;
}

function assertApprovedGrants(requested, approved) {
  const requestedKeys = new Set(requested.map(grantKey));
  for (const grant of approved) {
    if (!requestedKeys.has(grantKey(grant))) throw new AgentOrchestratorError("approved tool grant was not requested", 400);
  }
  const mutating = approved.filter((grant) => grant.mutating);
  if (mutating.length > 0 && approved.length === 0) throw new AgentOrchestratorError("mutating jobs require explicit approval grants", 400);
}

function buildEvent(type, job, now, extra = {}) {
  return {
    event_id: randomUUID(),
    event_type: type,
    event_version: "v1",
    occurred_at: now(),
    tenant_id: job.tenant_id,
    job_id: job.id,
    correlation_id: job.correlation_id,
    ...extra,
  };
}

export class MemoryJobStore {
  constructor({ jobs = new Map() } = {}) {
    this.jobs = jobs;
  }

  async findById(id) {
    return this.jobs.get(id) || null;
  }

  async findByIdempotency(tenantId, idempotencyKey) {
    return [...this.jobs.values()].find((job) => job.tenant_id === tenantId && job.idempotency_key === idempotencyKey) || null;
  }

  async save(job) {
    this.jobs.set(job.id, structuredClone(job));
    return structuredClone(job);
  }
}

export class MemoryQueueAdapter {
  constructor() {
    this.items = [];
  }

  async enqueue(item) {
    if (this.items.some((queued) => queued.job_id === item.job_id && queued.attempt === item.attempt)) return item;
    this.items.push(structuredClone(item));
    return item;
  }

  async dequeue() {
    return this.items.shift() || null;
  }

  size() {
    return this.items.length;
  }
}

export class MemoryAuditSink {
  constructor() {
    this.events = [];
  }

  async emit(event) {
    this.events.push(structuredClone(event));
    return event;
  }
}

export class SandboxedWorkerRuntime {
  constructor({ allowedTools = {}, now = () => new Date().toISOString() } = {}) {
    this.allowedTools = allowedTools;
    this.now = now;
  }

  async execute(job) {
    const auditCalls = [];
    for (const grant of job.approved_tool_grants) {
      const implementation = this.allowedTools[grant.tool];
      if (!implementation) {
        auditCalls.push({ tool: grant.tool, scope: grant.scope, mutating: grant.mutating, status: "skipped" });
        continue;
      }
      await implementation({ job, grant });
      auditCalls.push({ tool: grant.tool, scope: grant.scope, mutating: grant.mutating, status: "succeeded" });
    }
    return {
      status: "succeeded",
      result_refs: [{ type: "agent-result", id: `${job.id}-attempt-${job.attempt}` }],
      usage: { input_tokens: 0, output_tokens: 0, runtime_ms: 0 },
      audit: { worker_id: "sandbox-worker", attempt: job.attempt, tool_calls: auditCalls },
      completed_at: this.now(),
    };
  }
}

function normalizeBaseUrl(value, name) {
  if (typeof value !== "string" || !value.trim()) throw new AgentOrchestratorError(`${name} is required`, 500);
  const url = new URL(value);
  if (!["http:", "https:"].includes(url.protocol)) throw new AgentOrchestratorError(`${name} must be http or https`, 500);
  return url.toString().replace(/\/$/, "");
}

class HttpJsonClient {
  constructor({ baseUrl, token, fetchFn = globalThis.fetch, timeoutMs = 5000, name }) {
    this.baseUrl = normalizeBaseUrl(baseUrl, name);
    this.token = token;
    this.fetchFn = fetchFn;
    this.timeoutMs = timeoutMs;
    if (typeof this.fetchFn !== "function") throw new AgentOrchestratorError("fetch implementation is unavailable", 500);
  }

  async request(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetchFn(`${this.baseUrl}${path}`, {
        ...options,
        headers: {
          Accept: "application/json",
          ...(options.body ? { "Content-Type": "application/json" } : {}),
          ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
          ...options.headers,
        },
        signal: controller.signal,
      });
      if (response.status === 404) return null;
      if (!response.ok) {
        let message = `provider request failed with status ${response.status}`;
        try {
          const payload = await response.json();
          if (payload?.error) message = payload.error;
        } catch {}
        throw new AgentOrchestratorError(message, response.status);
      }
      if (response.status === 204) return null;
      return response.json();
    } catch (error) {
      if (error?.name === "AbortError") throw new AgentOrchestratorError("provider request timed out", 504);
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }
}

export class HttpJobStore {
  constructor({ baseUrl = process.env.AGENT_JOB_STORE_URL, token = process.env.Z_PLATFORM_SERVICE_TOKEN, fetchFn, timeoutMs = Number(process.env.AGENT_PROVIDER_TIMEOUT_MS || 5000) } = {}) {
    this.client = new HttpJsonClient({ baseUrl, token, fetchFn, timeoutMs, name: "AGENT_JOB_STORE_URL" });
  }

  async findById(id) {
    return this.client.request(`/jobs/${encodeURIComponent(id)}`);
  }

  async findByIdempotency(tenantId, idempotencyKey) {
    return this.client.request(`/jobs/by-idempotency/${encodeURIComponent(tenantId)}/${encodeURIComponent(idempotencyKey)}`);
  }

  async save(job) {
    return this.client.request(`/jobs/${encodeURIComponent(job.id)}`, { method: "PUT", body: JSON.stringify(job) });
  }
}

export class HttpQueueAdapter {
  constructor({ baseUrl = process.env.AGENT_QUEUE_URL, token = process.env.Z_PLATFORM_SERVICE_TOKEN, fetchFn, timeoutMs = Number(process.env.AGENT_PROVIDER_TIMEOUT_MS || 5000) } = {}) {
    this.client = new HttpJsonClient({ baseUrl, token, fetchFn, timeoutMs, name: "AGENT_QUEUE_URL" });
  }

  async enqueue(item) {
    return this.client.request("/queue", { method: "POST", body: JSON.stringify(item) });
  }

  async dequeue() {
    return this.client.request("/queue/next", { method: "POST" });
  }
}

export class HttpAuditSink {
  constructor({ baseUrl = process.env.AGENT_AUDIT_URL, token = process.env.Z_PLATFORM_SERVICE_TOKEN, fetchFn, timeoutMs = Number(process.env.AGENT_PROVIDER_TIMEOUT_MS || 5000) } = {}) {
    this.client = new HttpJsonClient({ baseUrl, token, fetchFn, timeoutMs, name: "AGENT_AUDIT_URL" });
  }

  async emit(event) {
    return this.client.request("/events", { method: "POST", body: JSON.stringify(event) });
  }
}

export class HttpIdentityProvider {
  constructor({ baseUrl = process.env.AGENT_IDENTITY_URL, token = process.env.Z_PLATFORM_SERVICE_TOKEN, fetchFn, timeoutMs = Number(process.env.AGENT_PROVIDER_TIMEOUT_MS || 5000) } = {}) {
    this.client = new HttpJsonClient({ baseUrl, token, fetchFn, timeoutMs, name: "AGENT_IDENTITY_URL" });
  }

  async assertActorCanApprove(actor, job) {
    const result = await this.client.request("/authorize-approval", { method: "POST", body: JSON.stringify({ actor, job }) });
    if (!result?.allowed) throw new AgentOrchestratorError("approval actor is not authorized", 403);
    return result;
  }
}

export class HttpSandboxRuntime {
  constructor({ baseUrl = process.env.AGENT_SANDBOX_URL, token = process.env.Z_PLATFORM_SERVICE_TOKEN, fetchFn, timeoutMs = Number(process.env.AGENT_SANDBOX_TIMEOUT_MS || process.env.AGENT_PROVIDER_TIMEOUT_MS || 30000) } = {}) {
    this.client = new HttpJsonClient({ baseUrl, token, fetchFn, timeoutMs, name: "AGENT_SANDBOX_URL" });
  }

  async execute(job) {
    return this.client.request("/execute", { method: "POST", body: JSON.stringify(job) });
  }
}

export function createProductionProvidersFromEnv(env = process.env) {
  const required = ["AGENT_JOB_STORE_URL", "AGENT_QUEUE_URL", "AGENT_AUDIT_URL", "AGENT_IDENTITY_URL", "AGENT_SANDBOX_URL"];
  const missing = required.filter((name) => !env[name]);
  if (missing.length > 0) throw new AgentOrchestratorError(`missing production provider config: ${missing.join(", ")}`, 500);
  return {
    store: new HttpJobStore({ baseUrl: env.AGENT_JOB_STORE_URL, token: env.Z_PLATFORM_SERVICE_TOKEN, timeoutMs: Number(env.AGENT_PROVIDER_TIMEOUT_MS || 5000) }),
    queue: new HttpQueueAdapter({ baseUrl: env.AGENT_QUEUE_URL, token: env.Z_PLATFORM_SERVICE_TOKEN, timeoutMs: Number(env.AGENT_PROVIDER_TIMEOUT_MS || 5000) }),
    audit: new HttpAuditSink({ baseUrl: env.AGENT_AUDIT_URL, token: env.Z_PLATFORM_SERVICE_TOKEN, timeoutMs: Number(env.AGENT_PROVIDER_TIMEOUT_MS || 5000) }),
    identity: new HttpIdentityProvider({ baseUrl: env.AGENT_IDENTITY_URL, token: env.Z_PLATFORM_SERVICE_TOKEN, timeoutMs: Number(env.AGENT_PROVIDER_TIMEOUT_MS || 5000) }),
    worker: new HttpSandboxRuntime({ baseUrl: env.AGENT_SANDBOX_URL, token: env.Z_PLATFORM_SERVICE_TOKEN, timeoutMs: Number(env.AGENT_SANDBOX_TIMEOUT_MS || env.AGENT_PROVIDER_TIMEOUT_MS || 30000) }),
  };
}

export function createAgentOrchestratorFromEnv(env = process.env) {
  if ((env.AGENT_ORCHESTRATOR_PROVIDER_MODE || "memory").toLowerCase() === "production") {
    return new AgentOrchestrator(createProductionProvidersFromEnv(env));
  }
  return new AgentOrchestrator();
}

export class AgentOrchestrator {
  constructor({ store = new MemoryJobStore(), queue = new MemoryQueueAdapter(), audit = new MemoryAuditSink(), identity, worker = new SandboxedWorkerRuntime(), idGenerator = randomUUID, now = () => new Date().toISOString() } = {}) {
    this.store = store;
    this.queue = queue;
    this.audit = audit;
    this.identity = identity;
    this.worker = worker;
    this.idGenerator = idGenerator;
    this.now = now;
  }

  async submit(input) {
    const tenantId = requireString(input.tenant_id, "tenant_id");
    const objective = requireString(input.objective ?? input.task, "task");
    const idempotencyKey = requireString(input.idempotency_key, "idempotency_key");
    const duplicate = await this.store.findByIdempotency(tenantId, idempotencyKey);
    if (duplicate) return { status: 200, job: duplicate };

    const job = {
      id: this.idGenerator(),
      tenant_id: tenantId,
      objective,
      task: objective,
      requested_tool_grants: normalizeToolGrants(input.tool_grants_requested ?? input.tool_grants),
      tool_grants: normalizeToolGrants(input.tool_grants_requested ?? input.tool_grants),
      input_refs: Array.isArray(input.input_refs) ? input.input_refs : [],
      status: "pending_approval",
      approval_state: "pending",
      idempotency_key: idempotencyKey,
      correlation_id: input.correlation_id,
      attempt: 0,
      max_retries: Number(input.max_retries ?? input.execution_policy?.max_retries ?? 1),
      timeout_seconds: Number(input.timeout_seconds ?? input.execution_policy?.timeout_seconds ?? 900),
      created_at: this.now(),
      updated_at: this.now(),
    };
    const saved = await this.store.save(job);
    await this.audit.emit(buildEvent("agent.job.requested.v1", saved, this.now, {
      requested_by: input.requested_by ?? { type: "service", id: "agent-orchestrator" },
      objective: saved.objective,
      input_refs: saved.input_refs,
      tool_grants_requested: saved.requested_tool_grants,
      execution_policy: { requires_approval: true, timeout_seconds: saved.timeout_seconds, max_retries: saved.max_retries },
    }));
    return { status: 202, job: saved };
  }

  async approve(id, input) {
    const job = await this.get(id);
    if (job.status !== "pending_approval") throw new AgentOrchestratorError("Job is not awaiting approval", 409);
    const approvedBy = requireString(input.approved_by, "approved_by");
    if (this.identity) await this.identity.assertActorCanApprove({ type: "user", id: approvedBy }, job);
    const grants = normalizeToolGrants(input.tool_grants ?? job.requested_tool_grants);
    assertApprovedGrants(job.requested_tool_grants, grants);
    const next = await this.store.save({
      ...job,
      status: "approved",
      approval_state: "approved",
      approved_by: approvedBy,
      approved_at: this.now(),
      approved_tool_grants: grants,
      constraints: {
        sandbox: input.constraints?.sandbox ?? "restricted",
        network: input.constraints?.network ?? "deny-by-default",
        timeout_seconds: Number(input.constraints?.timeout_seconds ?? job.timeout_seconds),
        max_retries: Number(input.constraints?.max_retries ?? job.max_retries),
      },
      updated_at: this.now(),
    });
    await this.queue.enqueue({ job_id: next.id, tenant_id: next.tenant_id, attempt: next.attempt + 1, enqueued_at: this.now() });
    await this.audit.emit(buildEvent("agent.job.approved.v1", next, this.now, {
      approved_by: { type: "user", id: approvedBy },
      approval_state: "approved",
      tool_grants: grants.map((grant) => ({ ...grant, expires_at: input.expires_at ?? new Date(Date.now() + 60 * 60 * 1000).toISOString() })),
      constraints: next.constraints,
    }));
    return next;
  }

  async get(id) {
    const job = await this.store.findById(id);
    if (!job) throw new AgentOrchestratorError("Job not found", 404);
    return job;
  }

  async cancel(id, input = {}) {
    const job = await this.get(id);
    if (TERMINAL.has(job.status)) throw new AgentOrchestratorError("Job is already terminal", 409);
    const next = await this.store.save({ ...job, status: "cancelled", cancelled_by: input.cancelled_by, cancelled_at: this.now(), updated_at: this.now() });
    await this.audit.emit(buildEvent("agent.job.completed.v1", next, this.now, {
      status: "cancelled",
      audit: { worker_id: "agent-orchestrator", attempt: next.attempt, tool_calls: [] },
    }));
    return next;
  }

  async retry(id) {
    const job = await this.get(id);
    if (job.status !== "failed") throw new AgentOrchestratorError("Only failed jobs can be retried", 409);
    if (job.attempt >= job.max_retries + 1) throw new AgentOrchestratorError("Retry limit exceeded", 409);
    const next = await this.store.save({ ...job, status: "approved", updated_at: this.now() });
    await this.queue.enqueue({ job_id: next.id, tenant_id: next.tenant_id, attempt: next.attempt + 1, enqueued_at: this.now() });
    return next;
  }

  async runNext() {
    const item = await this.queue.dequeue();
    if (!item) return null;
    const job = await this.get(item.job_id);
    if (job.status !== "approved") return job;
    const running = await this.store.save({ ...job, status: "running", attempt: item.attempt, started_at: this.now(), updated_at: this.now() });
    try {
      const result = await this.worker.execute(running);
      const completed = await this.store.save({ ...running, ...result, status: result.status, updated_at: this.now() });
      await this.audit.emit(buildEvent("agent.job.completed.v1", completed, this.now, {
        status: completed.status,
        result_refs: completed.result_refs,
        usage: completed.usage,
        audit: completed.audit,
      }));
      return completed;
    } catch (error) {
      const failed = await this.store.save({
        ...running,
        status: "failed",
        error: { code: "WORKER_FAILED", message: error?.message || "Worker failed" },
        audit: { worker_id: "sandbox-worker", attempt: running.attempt, tool_calls: [] },
        updated_at: this.now(),
      });
      await this.audit.emit(buildEvent("agent.job.completed.v1", failed, this.now, {
        status: "failed",
        error: failed.error,
        audit: failed.audit,
      }));
      return failed;
    }
  }
}

export function createAgentOrchestratorServer({ env = process.env, orchestrator, jobs, idGenerator = randomUUID, now = () => new Date().toISOString() } = {}) {
  const providerMode = (env.AGENT_ORCHESTRATOR_PROVIDER_MODE || "memory").toLowerCase();
  const service = orchestrator || (providerMode === "production" ? createAgentOrchestratorFromEnv(env) : new AgentOrchestrator({ store: new MemoryJobStore({ jobs }), idGenerator, now }));
  return createServer(async (request, response) => {
    if (request.method === "GET" && request.url === "/health") {
      return json(response, 200, { status: "ok", service: "agent-orchestrator", storage: providerMode === "production" ? "production-adapters" : "memory", execution_enabled: true, external_traffic_enabled: env.AGENT_EXTERNAL_TRAFFIC_ENABLED === "true" });
    }

    if (!authorized(request, env)) return json(response, 401, { error: "Unauthorized" });

    try {
      if (request.method === "POST" && request.url === "/v1/jobs") {
        const result = await service.submit(await body(request));
        return json(response, result.status, result.job);
      }

      const approve = request.url?.match(/^\/v1\/jobs\/([^/]+)\/approve$/);
      if (request.method === "POST" && approve) return json(response, 200, await service.approve(approve[1], await body(request)));

      const cancel = request.url?.match(/^\/v1\/jobs\/([^/]+)\/cancel$/);
      if (request.method === "POST" && cancel) return json(response, 200, await service.cancel(cancel[1], await body(request)));

      const retry = request.url?.match(/^\/v1\/jobs\/([^/]+)\/retry$/);
      if (request.method === "POST" && retry) return json(response, 200, await service.retry(retry[1]));

      if (request.method === "POST" && request.url === "/v1/worker/run-next") return json(response, 200, await service.runNext() ?? { status: "idle" });

      const get = request.url?.match(/^\/v1\/jobs\/([^/]+)$/);
      if (request.method === "GET" && get) return json(response, 200, await service.get(get[1]));

      return json(response, 404, { error: "Not found" });
    } catch (error) {
      const status = error instanceof AgentOrchestratorError ? error.status : 400;
      return json(response, status, { error: error instanceof Error ? error.message : "Invalid request" });
    }
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  createAgentOrchestratorServer().listen(defaultPort, defaultHost, () => {
    console.log("agent-orchestrator listening on http://" + defaultHost + ":" + defaultPort);
  });
}
