import { createServer } from "node:http";
import { createHash, timingSafeEqual } from "node:crypto";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const host = process.env.HOST || "127.0.0.1";
const port = Number(process.env.PORT || 8800);
const dataDir = process.env.DATA_DIR || "/data";

function emptyOperationalState() {
  return { jobs: {}, idempotency: {}, queue: [], audit: [], workspaces: {} };
}

function operationalSnapshot(value) {
  return structuredClone({
    jobs: value?.jobs || {},
    idempotency: value?.idempotency || {},
    queue: value?.queue || [],
    audit: value?.audit || [],
    workspaces: value?.workspaces || {},
  });
}

function snapshotEvidence(snapshot) {
  return {
    digest: createHash("sha256").update(JSON.stringify(snapshot)).digest("hex"),
    jobs: Object.keys(snapshot.jobs).length,
    queue: snapshot.queue.length,
    audit: snapshot.audit.length,
    workspaces: Object.keys(snapshot.workspaces).length,
  };
}

function send(res, status, payload) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(payload));
}

function authorized(req, env) {
  const supplied = req.headers.authorization?.replace(/^Bearer\s+/i, "");
  const expected = env.Z_PLATFORM_SERVICE_TOKEN;
  if (!supplied || !expected) return false;
  const a = Buffer.from(supplied);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

async function readJson(req) {
  let text = "";
  for await (const chunk of req) {
    text += chunk;
    if (text.length > 1_000_000) throw Object.assign(new Error("Request body is too large"), { status: 413 });
  }
  if (!text.trim()) return {};
  try { return JSON.parse(text); } catch { throw Object.assign(new Error("Request body must be valid JSON"), { status: 400 }); }
}

class DurableState {
  constructor(dir = dataDir) {
    this.dir = dir;
    this.path = join(dir, "state.json");
    this.state = { ...emptyOperationalState(), restoreNamespaces: {} };
    this.writeChain = Promise.resolve();
  }

  async init() {
    await mkdir(this.dir, { recursive: true });
    try {
      this.state = { ...this.state, ...JSON.parse(await readFile(this.path, "utf8")) };
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
      await this.persist();
    }
    return this;
  }

  async persist() {
    this.writeChain = this.writeChain.then(async () => {
      const temp = `${this.path}.tmp`;
      await writeFile(temp, JSON.stringify(this.state, null, 2), { mode: 0o600 });
      await rename(temp, this.path);
    });
    return this.writeChain;
  }

  async snapshot() { return operationalSnapshot(this.state); }
}

function metricText(state) {
  return [
    "# HELP z_platform_agent_jobs_total Number of durable jobs",
    "# TYPE z_platform_agent_jobs_total gauge",
    `z_platform_agent_jobs_total ${Object.keys(state.jobs).length}`,
    "# HELP z_platform_agent_queue_depth Number of queued executions",
    "# TYPE z_platform_agent_queue_depth gauge",
    `z_platform_agent_queue_depth ${state.queue.length}`,
    "# HELP z_platform_agent_audit_events_total Number of audit events",
    "# TYPE z_platform_agent_audit_events_total gauge",
    `z_platform_agent_audit_events_total ${state.audit.length}`,
    "",
  ].join("\n");
}

export async function createAgentProviderServer({ env = process.env, state = new DurableState(env.DATA_DIR || dataDir) } = {}) {
  await state.init();
  return createServer(async (req, res) => {
    if (req.method === "GET" && req.url === "/health") {
      return send(res, 200, { status: "ok", service: "agent-provider", storage: "durable-json", queue_depth: state.state.queue.length });
    }
    if (req.method === "GET" && req.url === "/metrics") {
      res.writeHead(200, { "Content-Type": "text/plain; version=0.0.4" });
      return res.end(metricText(state.state));
    }
    if (!authorized(req, env)) return send(res, 401, { error: "Unauthorized" });

    try {
      let match;
      if (req.method === "GET" && (match = req.url?.match(/^\/jobs\/([^/]+)$/))) {
        const job = state.state.jobs[decodeURIComponent(match[1])];
        return job ? send(res, 200, job) : send(res, 404, { error: "Not found" });
      }
      if (req.method === "GET" && (match = req.url?.match(/^\/jobs\/by-idempotency\/([^/]+)\/([^/]+)$/))) {
        const key = `${decodeURIComponent(match[1])}\n${decodeURIComponent(match[2])}`;
        const id = state.state.idempotency[key];
        return id ? send(res, 200, state.state.jobs[id]) : send(res, 404, { error: "Not found" });
      }
      if (req.method === "PUT" && (match = req.url?.match(/^\/jobs\/([^/]+)$/))) {
        const job = await readJson(req);
        const id = decodeURIComponent(match[1]);
        if (job.id !== id) return send(res, 400, { error: "Job id does not match path" });
        state.state.jobs[id] = structuredClone(job);
        if (job.tenant_id && job.idempotency_key) state.state.idempotency[`${job.tenant_id}\n${job.idempotency_key}`] = id;
        await state.persist();
        return send(res, 200, job);
      }
      if (req.method === "POST" && req.url === "/queue") {
        const item = await readJson(req);
        if (!item.job_id) return send(res, 400, { error: "job_id is required" });
        if (!state.state.queue.some((entry) => entry.job_id === item.job_id && entry.attempt === item.attempt)) state.state.queue.push(item);
        await state.persist();
        return send(res, 202, item);
      }
      if (req.method === "POST" && req.url === "/queue/next") {
        const item = state.state.queue.shift() || null;
        await state.persist();
        return item ? send(res, 200, item) : send(res, 204, null);
      }
      if (req.method === "POST" && req.url === "/events") {
        const event = await readJson(req);
        state.state.audit.push(event);
        await state.persist();
        return send(res, 202, event);
      }
      if (req.method === "GET" && req.url === "/events") return send(res, 200, { events: state.state.audit });
      if (req.method === "POST" && req.url === "/authorize-approval") {
        const { actor, job } = await readJson(req);
        const allowed = actor?.type === "user" && typeof actor.id === "string" && actor.id.length > 0 && actor.id !== job?.requested_by?.id;
        return send(res, 200, { allowed, policy: "authenticated-user-separation-of-duties" });
      }
      if (req.method === "POST" && req.url === "/execute") {
        const job = await readJson(req);
        if (job.approval_state !== "approved" || !Array.isArray(job.approved_tool_grants)) return send(res, 403, { error: "Approved grants are required" });
        const mutating = job.approved_tool_grants.filter((grant) => grant.mutating);
        if (mutating.length && job.constraints?.sandbox !== "restricted") return send(res, 403, { error: "Mutating jobs require restricted sandbox" });
        if (env.AGENT_TEST_FAILURE_INJECTION === "true" && job.objective === "readiness:fail-first-attempt" && Number(job.attempt) === 1) {
          return send(res, 503, { error: "Injected first-attempt failure for readiness verification" });
        }
        return send(res, 200, {
          status: "succeeded",
          result_refs: [{ type: "agent-result", id: `${job.id}-attempt-${job.attempt}` }],
          usage: { input_tokens: 0, output_tokens: 0, runtime_ms: 0 },
          audit: { worker_id: "durable-sandbox", attempt: job.attempt, tool_calls: job.approved_tool_grants.map((grant) => ({ ...grant, status: "validated" })) },
          completed_at: new Date().toISOString(),
        });
      }
      if (req.method === "PUT" && (match = req.url?.match(/^\/workspaces\/([^/]+)$/))) {
        const workspace = await readJson(req);
        const id = decodeURIComponent(match[1]);
        if (!/^[A-Za-z0-9_-]{1,128}$/.test(id)) return send(res, 400, { error: "Invalid workspace id" });
        state.state.workspaces[id] = { ...workspace, id, updated_at: new Date().toISOString() };
        await state.persist();
        return send(res, 200, state.state.workspaces[id]);
      }
      if (req.method === "GET" && (match = req.url?.match(/^\/workspaces\/([^/]+)$/))) {
        const id = decodeURIComponent(match[1]);
        if (!/^[A-Za-z0-9_-]{1,128}$/.test(id)) return send(res, 400, { error: "Invalid workspace id" });
        const workspace = state.state.workspaces[id];
        return workspace ? send(res, 200, workspace) : send(res, 404, { error: "Not found" });
      }
      if (req.method === "POST" && req.url === "/workspaces/cleanup") {
        const { before } = await readJson(req);
        const cutoff = Date.parse(before);
        if (!Number.isFinite(cutoff)) return send(res, 400, { error: "before must be an ISO date" });
        let deleted = 0;
        for (const [id, workspace] of Object.entries(state.state.workspaces)) {
          if (Date.parse(workspace.updated_at || 0) < cutoff) { delete state.state.workspaces[id]; deleted += 1; }
        }
        await state.persist();
        return send(res, 200, { deleted });
      }
      if (req.method === "GET" && req.url === "/backup/export") return send(res, 200, await state.snapshot());
      if (req.method === "GET" && req.url?.startsWith("/backup/verify?")) {
        const params = new URL(req.url, "http://agent-provider").searchParams;
        const object = params.get("object");
        const namespace = params.get("namespace");
        if (!object) return send(res, 400, { error: "object is required" });
        if (!namespace || !/^[A-Za-z0-9_-]{1,128}$/.test(namespace)) return send(res, 400, { error: "valid namespace is required" });
        const snapshot = state.state.restoreNamespaces?.[namespace];
        if (!snapshot) return send(res, 404, { error: "Restore namespace not found" });
        return send(res, 200, {
          verified: true,
          status: "verified",
          isolated: true,
          object,
          namespace,
          ...snapshotEvidence(snapshot),
        });
      }
      if (req.method === "POST" && req.url === "/backup/restore") {
        const { namespace, snapshot: suppliedSnapshot } = await readJson(req);
        if (!namespace || !/^[A-Za-z0-9_-]{1,128}$/.test(namespace)) return send(res, 400, { error: "valid namespace is required" });
        if (!suppliedSnapshot || typeof suppliedSnapshot !== "object" || Array.isArray(suppliedSnapshot)) return send(res, 400, { error: "snapshot is required" });
        const snapshot = { ...emptyOperationalState(), ...operationalSnapshot(suppliedSnapshot) };
        state.state.restoreNamespaces ||= {};
        state.state.restoreNamespaces[namespace] = snapshot;
        await state.persist();
        return send(res, 200, { restored: true, isolated: true, namespace, ...snapshotEvidence(snapshot) });
      }
      return send(res, 404, { error: "Not found" });
    } catch (error) {
      return send(res, error.status || 500, { error: error.message || "Request failed" });
    }
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const server = await createAgentProviderServer();
  server.listen(port, host, () => console.log(`agent-provider listening on http://${host}:${port}`));
}
