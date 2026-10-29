import { createServer } from "node:http";
import { randomUUID, timingSafeEqual } from "node:crypto";
import { fileURLToPath } from "node:url";

const defaultHost = process.env.HOST || "127.0.0.1";
const defaultPort = Number(process.env.PORT || 8700);
const MAX_REQUEST_BODY_BYTES = 64 * 1024;

export class BillingLedgerError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.status = status;
    this.publicMessage = message;
  }
}

function send(response, status, body) {
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  response.end(JSON.stringify(body));
}

function authorized(request, env) {
  const authorization = request.headers.authorization;
  const match = typeof authorization === "string"
    ? /^Bearer[ \t]+(\S+)$/i.exec(authorization)
    : null;
  const supplied = match?.[1];
  const expected = env.Z_PLATFORM_SERVICE_TOKEN;
  if (!supplied || !expected) return false;
  const a = Buffer.from(supplied);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

async function readJson(request) {
  const rawContentType = request.headers["content-type"];
  const mediaType = typeof rawContentType === "string"
    ? rawContentType.split(";", 1)[0].trim().toLowerCase()
    : "";
  if (mediaType !== "application/json") {
    request.resume();
    throw new BillingLedgerError("Content-Type must be application/json", 415);
  }

  const rawContentLength = request.headers["content-length"];
  if (typeof rawContentLength === "string") {
    const normalizedLength = rawContentLength.trim();
    const declaredLength = Number(normalizedLength);
    if (!/^\d+$/.test(normalizedLength) || !Number.isSafeInteger(declaredLength) || declaredLength < 0) {
      request.resume();
      throw new BillingLedgerError("Invalid Content-Length", 400);
    }
    if (declaredLength > MAX_REQUEST_BODY_BYTES) {
      request.resume();
      throw new BillingLedgerError("Request body is too large", 413);
    }
  }

  const chunks = [];
  let bytes = 0;
  let tooLarge = false;
  for await (const chunk of request) {
    const data = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    bytes += data.byteLength;
    if (bytes > MAX_REQUEST_BODY_BYTES) {
      tooLarge = true;
      chunks.length = 0;
      continue;
    }
    if (!tooLarge) chunks.push(data);
  }
  if (tooLarge) throw new BillingLedgerError("Request body is too large", 413);

  const text = Buffer.concat(chunks).toString("utf8");
  if (!text.trim()) return {};
  try {
    return JSON.parse(text);
  } catch {
    throw new BillingLedgerError("Invalid JSON body", 400);
  }
}

function requireObjectPayload(input, label) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new BillingLedgerError(`${label} payload must be an object`);
  }
  return input;
}

function requireString(value, name) {
  if (typeof value !== "string" || !value.trim()) throw new BillingLedgerError(`${name} is required`);
  return value.trim();
}

function normalizeUsage(input) {
  return {
    event_type: "ai.usage.recorded.v1",
    event_version: "v1",
    usage_id: requireString(input.usage_id || input.request_id, "usage_id"),
    idempotency_key: requireString(input.idempotency_key, "idempotency_key"),
    tenant_id: requireString(input.tenant_id, "tenant_id"),
    subject_id: input.subject_id ? requireString(input.subject_id, "subject_id") : "unknown",
    model: requireString(input.model || "unknown", "model"),
    input_tokens: input.input_tokens === undefined ? 0 : input.input_tokens,
    output_tokens: input.output_tokens === undefined ? 0 : input.output_tokens,
    recorded_at: input.recorded_at || new Date().toISOString(),
  };
}

function idempotencyScopeKey(tenantId, idempotencyKey) {
  return JSON.stringify([tenantId, idempotencyKey]);
}

function stableFingerprint(value, excludedKeys = []) {
  const stable = Object.fromEntries(
    Object.entries(value)
      .filter(([key]) => !excludedKeys.includes(key))
      .sort(([left], [right]) => left.localeCompare(right)),
  );
  return JSON.stringify(stable);
}

export class MemoryLedgerStore {
  constructor() {
    this.records = new Map();
    this.recordFingerprints = new Map();
    this.credits = new Map();
    this.invoiceIntents = new Map();
    this.invoiceIntentFingerprints = new Map();
  }

  async recordUsage(record) {
    const key = idempotencyScopeKey(record.tenant_id, record.idempotency_key);
    const fingerprint = stableFingerprint(record, ["recorded_at"]);
    if (this.records.has(key)) {
      if (this.recordFingerprints.get(key) !== fingerprint) {
        throw new BillingLedgerError("Idempotency key conflicts with an existing request", 409);
      }
      return { duplicate: true, record: structuredClone(this.records.get(key)) };
    }
    this.records.set(key, structuredClone(record));
    this.recordFingerprints.set(key, fingerprint);
    return { duplicate: false, record: structuredClone(record) };
  }

  async setCredits(tenantId, amount) {
    this.credits.set(tenantId, Number(amount));
    return { tenant_id: tenantId, credits: this.credits.get(tenantId) };
  }

  async createInvoiceIntent(intent) {
    const key = idempotencyScopeKey(intent.tenant_id, intent.idempotency_key);
    const fingerprint = stableFingerprint(intent, ["intent_id", "created_at"]);
    if (this.invoiceIntents.has(key)) {
      if (this.invoiceIntentFingerprints.get(key) !== fingerprint) {
        throw new BillingLedgerError("Idempotency key conflicts with an existing request", 409);
      }
      return structuredClone(this.invoiceIntents.get(key));
    }
    this.invoiceIntents.set(key, structuredClone(intent));
    this.invoiceIntentFingerprints.set(key, fingerprint);
    return structuredClone(intent);
  }
}

function requireMutationAuthorization({ ledger, env, allowEphemeralStore, request, tenantId, operation }) {
  // Memory writes are exclusively a test harness capability; NODE_ENV alone is not sufficient.
  if (
    ledger.store instanceof MemoryLedgerStore &&
    env.NODE_ENV === "test" &&
    allowEphemeralStore === true
  ) {
    return;
  }

  if (!ledger.store?.durable) {
    throw new BillingLedgerError("Persistent billing storage is not configured", 503);
  }
  if (env.Z_BILLING_LEDGER_ENABLE_MUTATIONS !== "true") {
    throw new BillingLedgerError("Billing mutations are disabled by the release gate", 503);
  }
  if (env.Z_BILLING_LEDGER_TENANT_AUTHZ_MODE !== "trusted-gateway") {
    throw new BillingLedgerError("Trusted tenant authorization is not configured", 503);
  }

  const assertedTenant = request.headers["x-authenticated-tenant"];
  if (typeof assertedTenant !== "string" || assertedTenant.trim() !== tenantId) {
    throw new BillingLedgerError("Tenant authorization failed", 403);
  }

  // This legacy setter has neither operation idempotency nor an append-only audit
  // contract. Do not enable it through the generic billing mutation release gate.
  if (operation === "credits") {
    throw new BillingLedgerError(
      "Credit mutations are disabled pending an append-only audited adjustment contract",
      503,
    );
  }
}

export class BillingLedger {
  constructor({ store = new MemoryLedgerStore(), idGenerator = randomUUID, now = () => new Date().toISOString() } = {}) {
    this.store = store;
    this.idGenerator = idGenerator;
    this.now = now;
  }

  async recordUsage(input) {
    const payload = requireObjectPayload(input, "Usage");
    const record = normalizeUsage({ ...payload, recorded_at: payload.recorded_at || this.now() });
    if (!Number.isSafeInteger(record.input_tokens) || record.input_tokens < 0 ||
        !Number.isSafeInteger(record.output_tokens) || record.output_tokens < 0) {
      throw new BillingLedgerError("usage tokens must be non-negative safe integers");
    }
    return this.store.recordUsage(record);
  }

  async setCredits(input) {
    const payload = requireObjectPayload(input, "Credits");
    const tenantId = requireString(payload.tenant_id, "tenant_id");
    const credits = payload.credits;
    if (!Number.isSafeInteger(credits) || credits < 0) {
      throw new BillingLedgerError("credits must be a non-negative safe integer");
    }
    return this.store.setCredits(tenantId, credits);
  }

  async createInvoiceIntent(input) {
    const payload = requireObjectPayload(input, "Invoice intent");
    const intent = {
      intent_id: this.idGenerator(),
      idempotency_key: requireString(payload.idempotency_key, "idempotency_key"),
      tenant_id: requireString(payload.tenant_id, "tenant_id"),
      currency: requireString(payload.currency, "currency").toUpperCase(),
      amount_minor: payload.amount_minor,
      status: "requires_payment_processor",
      created_at: this.now(),
    };
    if (!/^[A-Z]{3}$/.test(intent.currency)) {
      throw new BillingLedgerError("currency must be a three-letter ISO currency code");
    }
    if (typeof intent.amount_minor !== "number" || !Number.isSafeInteger(intent.amount_minor) || intent.amount_minor <= 0) {
      throw new BillingLedgerError("amount_minor must be a positive safe integer");
    }
    return this.store.createInvoiceIntent(intent);
  }
}

export function createBillingLedgerServer({
  env = process.env,
  ledger = new BillingLedger(),
  allowEphemeralStore = false,
} = {}) {
  const server = createServer(async (request, response) => {
    if (request.method === "GET" && request.url === "/health") {
      return send(response, 200, {
        status: "ok",
        service: "billing-ledger",
        wallet_authority: false,
        card_data: false,
      });
    }

    if (request.method === "GET" && request.url === "/ready") {
      if (!ledger.store?.durable || typeof ledger.store.assertReady !== "function") {
        return send(response, 503, { status: "not_ready", reason: "durable storage unavailable" });
      }
      try {
        await ledger.store.assertReady();
        return send(response, 200, { status: "ready", service: "billing-ledger", persistence: "postgresql" });
      } catch {
        return send(response, 503, { status: "not_ready", reason: "durable storage unavailable" });
      }
    }

    if (!authorized(request, env)) return send(response, 401, { error: "Unauthorized" });

    try {
      if (request.method === "POST" && request.url === "/v1/usage") {
        const input = requireObjectPayload(await readJson(request), "Usage");
        const tenantId = requireString(input.tenant_id, "tenant_id");
        requireMutationAuthorization({ ledger, env, allowEphemeralStore, request, tenantId, operation: "usage" });
        const result = await ledger.recordUsage(input);
        return send(response, result.duplicate ? 200 : 201, result);
      }

      if (request.method === "POST" && request.url === "/v1/credits") {
        const input = requireObjectPayload(await readJson(request), "Credits");
        const tenantId = requireString(input.tenant_id, "tenant_id");
        requireMutationAuthorization({ ledger, env, allowEphemeralStore, request, tenantId, operation: "credits" });
        return send(response, 200, await ledger.setCredits(input));
      }

      if (request.method === "POST" && request.url === "/v1/invoice-intents") {
        const input = requireObjectPayload(await readJson(request), "Invoice intent");
        const tenantId = requireString(input.tenant_id, "tenant_id");
        requireMutationAuthorization({ ledger, env, allowEphemeralStore, request, tenantId, operation: "invoice-intent" });
        return send(response, 201, await ledger.createInvoiceIntent(input));
      }

      return send(response, 404, { error: "Not found" });
    } catch (error) {
      if (error instanceof BillingLedgerError) {
        return send(response, error.status, { error: error.publicMessage });
      }
      if (error && Number.isInteger(error.status) && error.status >= 400 && error.status <= 599 &&
          typeof error.publicMessage === "string") {
        return send(response, error.status, { error: error.publicMessage });
      }
      // Never expose database, adapter, or runtime exception details to callers.
      return send(response, 500, { error: "Internal server error" });
    }
  });

  // Bound slow/incomplete HTTP requests and idle keep-alive sockets. These
  // limits complement the byte-bounded JSON reader; they do not replace
  // gateway-level connection/rate limits.
  server.headersTimeout = 10_000;
  server.requestTimeout = 30_000;
  server.keepAliveTimeout = 5_000;
  server.maxRequestsPerSocket = 1_000;
  server.setTimeout(30_000, (socket) => socket.destroy());
  return server;
}

export function validateDatabaseTransport(databaseUrl, env = process.env) {
  if (!databaseUrl) return;

  let parsed;
  try {
    parsed = new URL(databaseUrl);
  } catch {
    throw new Error("Database URL is invalid");
  }

  const tlsRequired =
    env.NODE_ENV === "production" ||
    env.Z_BILLING_LEDGER_REQUIRE_TLS === "true" ||
    env.Z_BILLING_LEDGER_ENABLE_MUTATIONS === "true";

  if (tlsRequired && parsed.searchParams.get("sslmode") !== "verify-full") {
    throw new Error("Database TLS verification is required");
  }
}

async function startServer() {
  let ledger = new BillingLedger();
  const databaseUrl = process.env.DATABASE_URL;

  if (databaseUrl) {
    validateDatabaseTransport(databaseUrl, process.env);

    const { Pool } = await import("pg");
    const { PostgresLedgerStore } = await import("./postgres-store.mjs");
    const pool = new Pool({
      connectionString: databaseUrl,
      max: 10,
      connectionTimeoutMillis: 3000,
      idleTimeoutMillis: 30000,
      statement_timeout: 5000,
      query_timeout: 7000,
      application_name: "zeaz-billing-ledger",
    });
    pool.on("error", () => {
      console.error("billing-ledger PostgreSQL pool reported an idle-client error");
    });
    ledger = new BillingLedger({ store: new PostgresLedgerStore({ pool }) });
  } else {
    console.warn("billing-ledger has no DATABASE_URL; mutation routes will fail closed");
  }

  const server = createBillingLedgerServer({ ledger });
  server.listen(defaultPort, defaultHost, () => {
    console.log("billing-ledger listening on " + defaultHost + ":" + defaultPort);
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  startServer().catch(() => {
    console.error("billing-ledger startup failed; check database configuration without printing credentials");
    process.exitCode = 1;
  });
}
