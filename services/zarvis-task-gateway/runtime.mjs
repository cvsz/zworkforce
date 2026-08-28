import { createHash, randomUUID } from "node:crypto";
import {
  AgentOrchestrator,
  AgentOrchestratorError,
} from "../agent-orchestrator/server.mjs";
import { createDurableFileProviders } from "../agent-orchestrator/durable-adapters.mjs";
import { executeGitHubRepositoryStatus } from "../zarvis-orchestrator/src/github-status-tool.mjs";

export const ZARVIS_OWNER_GITHUB_ID = "4076926";
export const ZARVIS_OWNER_USER_ID = `github:${ZARVIS_OWNER_GITHUB_ID}`;
export const ZARVIS_OWNER_TENANT_ID = `owner-${ZARVIS_OWNER_GITHUB_ID}`;

const ID_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/;
const REPOSITORY_PATTERN = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
const MAX_STEPS = 20;
const APPROVAL_TTL_MS = 15 * 60 * 1000;
const READ_ONLY_TOOLS = new Set([
  "github.repository.status",
  "zarvis.repository.summary",
]);

function requireString(value, field, max = 2000) {
  if (typeof value !== "string") throw new AgentOrchestratorError(`${field} is required`, 400);
  const normalized = value.trim();
  if (!normalized || normalized.length > max) {
    throw new AgentOrchestratorError(`${field} is invalid`, 400);
  }
  return normalized;
}

function requireId(value, field) {
  const normalized = requireString(value, field, 128);
  if (!ID_PATTERN.test(normalized)) throw new AgentOrchestratorError(`${field} is invalid`, 400);
  return normalized;
}

function stablePlanValue({ objective, steps }) {
  return {
    objective,
    steps: steps.map((step) => ({
      id: step.id,
      tool: step.tool,
      scope: step.scope,
      depends_on: [...step.depends_on],
      arguments: step.arguments,
    })),
  };
}

export function planDigest(plan) {
  return createHash("sha256").update(JSON.stringify(stablePlanValue(plan))).digest("hex");
}

function normalizeArguments(value) {
  if (value == null) return {};
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new AgentOrchestratorError("step.arguments must be an object", 400);
  }
  return structuredClone(value);
}

export function normalizePlan(input) {
  const objective = requireString(input.objective ?? input.task, "objective");
  if (!Array.isArray(input.steps) || input.steps.length < 1 || input.steps.length > MAX_STEPS) {
    throw new AgentOrchestratorError(`steps must contain between 1 and ${MAX_STEPS} items`, 400);
  }

  const ids = new Set();
  const steps = input.steps.map((raw, index) => {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      throw new AgentOrchestratorError("step is invalid", 400);
    }
    const id = requireId(raw.id, "step.id");
    if (ids.has(id)) throw new AgentOrchestratorError("step.id must be unique", 400);
    ids.add(id);

    const tool = requireString(raw.tool, "step.tool", 128);
    if (!READ_ONLY_TOOLS.has(tool)) {
      throw new AgentOrchestratorError("Only registered read-only ZARVIS task tools are allowed", 400);
    }
    if (raw.mutating === true) {
      throw new AgentOrchestratorError("Mutating task steps remain blocked", 403);
    }

    const scope = requireString(raw.scope, "step.scope", 256);
    if (!REPOSITORY_PATTERN.test(scope)) {
      throw new AgentOrchestratorError("step.scope must be an owner/repository identifier", 400);
    }
    const dependsOn = raw.depends_on == null ? [] : raw.depends_on;
    if (!Array.isArray(dependsOn) || dependsOn.some((dependency) => typeof dependency !== "string")) {
      throw new AgentOrchestratorError("step.depends_on must be an array of step IDs", 400);
    }
    for (const dependency of dependsOn) {
      if (!ids.has(dependency)) {
        throw new AgentOrchestratorError(
          `step ${id} may depend only on an earlier step; missing ${dependency}`,
          400,
        );
      }
    }

    return {
      id,
      order: index,
      tool,
      scope,
      mutating: false,
      depends_on: [...dependsOn],
      arguments: normalizeArguments(raw.arguments),
    };
  });

  return { objective, steps };
}

function requestedGrants(steps) {
  const unique = new Map();
  for (const step of steps) {
    const key = `${step.tool}\n${step.scope}`;
    if (!unique.has(key)) {
      unique.set(key, { tool: step.tool, scope: step.scope, mutating: false });
    }
  }
  return [...unique.values()];
}

function approvalExpiry(now) {
  const timestamp = Date.parse(now);
  if (!Number.isFinite(timestamp)) throw new AgentOrchestratorError("Runtime clock is invalid", 500);
  return new Date(timestamp + APPROVAL_TTL_MS).toISOString();
}

function assertApprovalProof(job, input, now) {
  if (job.approval_consumed_at) {
    throw new AgentOrchestratorError("Approval proof was already consumed", 409);
  }
  if (input.approval_digest !== job.approval_digest) {
    throw new AgentOrchestratorError("Approval digest does not match the exact task plan", 409);
  }
  if (input.approval_nonce !== job.approval_nonce) {
    throw new AgentOrchestratorError("Approval nonce is invalid", 409);
  }
  if (Date.parse(now) > Date.parse(job.approval_expires_at)) {
    throw new AgentOrchestratorError("Approval proof has expired", 409);
  }
}

function taskEvent(type, job, now, extra = {}) {
  return {
    event_id: randomUUID(),
    event_type: type,
    event_version: "v1",
    occurred_at: now,
    tenant_id: ZARVIS_OWNER_TENANT_ID,
    user_id: ZARVIS_OWNER_USER_ID,
    task_id: job.id,
    correlation_id: job.correlation_id,
    ...extra,
  };
}

function expiredResult(job, now) {
  return {
    status: "expired",
    result_refs: [],
    step_results: [],
    checkpoint: { completed_step_ids: [] },
    usage: { input_tokens: 0, output_tokens: 0, runtime_ms: 0 },
    audit: {
      worker_id: "zarvis-plan-worker",
      attempt: job.attempt,
      tool_calls: [],
      reason: "approval_expired",
    },
    completed_at: now,
  };
}

export class ZarvisPlanWorkerRuntime {
  constructor({
    githubExecutor = executeGitHubRepositoryStatus,
    now = () => new Date().toISOString(),
  } = {}) {
    this.githubExecutor = githubExecutor;
    this.now = now;
  }

  async execute(job) {
    const startedAt = this.now();
    if (Date.parse(startedAt) > Date.parse(job.approval_expires_at)) {
      return expiredResult(job, startedAt);
    }

    const completed = new Map();
    const stepResults = [];

    for (const step of job.plan.steps) {
      const dependencies = step.depends_on.map((id) => completed.get(id));
      if (dependencies.some((dependency) => dependency?.status !== "succeeded")) {
        const skipped = {
          step_id: step.id,
          status: "skipped",
          reason: "dependency_failed",
          completed_at: this.now(),
        };
        completed.set(step.id, skipped);
        stepResults.push(skipped);
        continue;
      }

      try {
        let output;
        if (step.tool === "github.repository.status") {
          const [owner, repo] = step.scope.split("/");
          output = await this.githubExecutor({ owner, repo });
        } else if (step.tool === "zarvis.repository.summary") {
          const repository = dependencies.at(-1)?.output;
          if (!repository?.full_name) {
            throw new Error("Repository status dependency is missing");
          }
          output = {
            text: `${repository.full_name} uses ${repository.default_branch} and has ${repository.open_issues_count} open issues and pull requests.`,
            repository: repository.full_name,
          };
        } else {
          throw new Error(`Unregistered task tool: ${step.tool}`);
        }

        const succeeded = {
          step_id: step.id,
          status: "succeeded",
          output,
          completed_at: this.now(),
        };
        completed.set(step.id, succeeded);
        stepResults.push(succeeded);
      } catch (error) {
        const failed = {
          step_id: step.id,
          status: "failed",
          error: { code: "STEP_FAILED", message: error?.message || "Step failed" },
          completed_at: this.now(),
        };
        completed.set(step.id, failed);
        stepResults.push(failed);
        return {
          status: "failed",
          result_refs: [],
          step_results: stepResults,
          checkpoint: { completed_step_ids: stepResults.map((result) => result.step_id) },
          usage: { input_tokens: 0, output_tokens: 0, runtime_ms: 0 },
          audit: {
            worker_id: "zarvis-plan-worker",
            attempt: job.attempt,
            tool_calls: stepResults.map((result) => ({
              step_id: result.step_id,
              status: result.status,
            })),
          },
          completed_at: this.now(),
        };
      }
    }

    return {
      status: "succeeded",
      result_refs: [{ type: "zarvis-task-result", id: `${job.id}-attempt-${job.attempt}` }],
      step_results: stepResults,
      checkpoint: { completed_step_ids: stepResults.map((result) => result.step_id) },
      usage: { input_tokens: 0, output_tokens: 0, runtime_ms: 0 },
      audit: {
        worker_id: "zarvis-plan-worker",
        attempt: job.attempt,
        tool_calls: stepResults.map((result) => ({
          step_id: result.step_id,
          status: result.status,
        })),
      },
      completed_at: this.now(),
    };
  }
}

export class ZarvisTaskRuntime extends AgentOrchestrator {
  constructor(options = {}) {
    const providers = options.store && options.queue && options.audit
      ? { store: options.store, queue: options.queue, audit: options.audit }
      : createDurableFileProviders({ rootDir: options.rootDir });
    super({
      ...providers,
      worker: options.worker ?? new ZarvisPlanWorkerRuntime({
        githubExecutor: options.githubExecutor,
        now: options.now,
      }),
      idGenerator: options.idGenerator,
      now: options.now,
    });
  }

  async submitPlan(input) {
    const plan = normalizePlan(input);
    const digest = planDigest(plan);
    const idempotencyKey = requireId(input.idempotency_key, "idempotency_key");
    const duplicate = await this.store.findByIdempotency(
      ZARVIS_OWNER_TENANT_ID,
      idempotencyKey,
    );
    if (duplicate) {
      if (duplicate.approval_digest !== digest) {
        throw new AgentOrchestratorError(
          "idempotency_key was already used with a different exact task plan",
          409,
        );
      }
      return { status: 200, job: duplicate };
    }

    const submitted = await super.submit({
      tenant_id: ZARVIS_OWNER_TENANT_ID,
      objective: plan.objective,
      tool_grants: requestedGrants(plan.steps),
      input_refs: Array.isArray(input.input_refs) ? input.input_refs : [],
      idempotency_key: idempotencyKey,
      correlation_id: input.correlation_id ?? randomUUID(),
      requested_by: { type: "user", id: ZARVIS_OWNER_USER_ID },
      max_retries: input.max_retries ?? 1,
      timeout_seconds: input.timeout_seconds ?? 900,
    });

    const now = this.now();
    const job = await this.store.save({
      ...submitted.job,
      plan,
      approval_digest: digest,
      approval_nonce: randomUUID(),
      approval_expires_at: approvalExpiry(now),
      owner_user_id: ZARVIS_OWNER_USER_ID,
      task_version: "zarvis.task.v1",
      updated_at: now,
    });
    await this.audit.emit(taskEvent("zarvis.task.plan-created.v1", job, now, {
      approval_digest: digest,
      approval_expires_at: job.approval_expires_at,
      step_count: plan.steps.length,
    }));
    return { status: 202, job };
  }

  async approvePlan(id, input) {
    const job = await this.get(id);
    if (job.status !== "pending_approval") {
      throw new AgentOrchestratorError("Task is not awaiting approval", 409);
    }
    const now = this.now();
    assertApprovalProof(job, input, now);
    const approved = await super.approve(id, {
      approved_by: ZARVIS_OWNER_USER_ID,
      tool_grants: job.requested_tool_grants,
      constraints: input.constraints,
      expires_at: job.approval_expires_at,
    });
    return this.store.save({
      ...approved,
      approval_consumed_at: now,
      approval_nonce: null,
      updated_at: now,
    });
  }

  async pause(id) {
    const job = await this.get(id);
    if (!["pending_approval", "approved"].includes(job.status)) {
      throw new AgentOrchestratorError("Only pending or approved tasks can be paused", 409);
    }
    const now = this.now();
    const paused = await this.store.save({
      ...job,
      status: "paused",
      paused_from_status: job.status,
      paused_by: ZARVIS_OWNER_USER_ID,
      paused_at: now,
      updated_at: now,
    });
    await this.audit.emit(taskEvent("zarvis.task.paused.v1", paused, now, {
      paused_from_status: job.status,
    }));
    return paused;
  }

  async resume(id) {
    const job = await this.get(id);
    if (job.status !== "paused") {
      throw new AgentOrchestratorError("Only paused tasks can be resumed", 409);
    }
    const resumedStatus = job.paused_from_status === "approved" ? "approved" : "pending_approval";
    const now = this.now();
    const resumed = await this.store.save({
      ...job,
      status: resumedStatus,
      resumed_by: ZARVIS_OWNER_USER_ID,
      resumed_at: now,
      paused_from_status: null,
      updated_at: now,
    });
    if (resumedStatus === "approved") {
      await this.queue.enqueue({
        job_id: resumed.id,
        tenant_id: resumed.tenant_id,
        attempt: resumed.attempt + 1,
        enqueued_at: now,
      });
    }
    await this.audit.emit(taskEvent("zarvis.task.resumed.v1", resumed, now, {
      resumed_status: resumedStatus,
    }));
    return resumed;
  }

  async cancelPlan(id) {
    return super.cancel(id, { cancelled_by: ZARVIS_OWNER_USER_ID });
  }

  async listPlans() {
    if (typeof this.store.listByTenant === "function") {
      return this.store.listByTenant(ZARVIS_OWNER_TENANT_ID);
    }
    if (this.store.jobs instanceof Map) {
      return [...this.store.jobs.values()]
        .filter((job) => job.tenant_id === ZARVIS_OWNER_TENANT_ID)
        .map((job) => structuredClone(job));
    }
    throw new AgentOrchestratorError("Task listing is unavailable for this store adapter", 501);
  }
}
