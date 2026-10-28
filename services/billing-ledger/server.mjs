import { createServer } from "node:http";
import { randomUUID, timingSafeEqual } from "node:crypto";
import { fileURLToPath } from "node:url";

const defaultHost = process.env.HOST || "127.0.0.1";
const defaultPort = Number(process.env.PORT || 8700);

export class BillingLedgerError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.status = status;
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
  const supplied = request.headers.authorization?.replace(/^Bearer\s+/i, "");
  const expected = env.Z_PLATFORM_SERVICE_TOKEN;
  if (!supplied || !expected) return false;
  const a = Buffer.from(supplied);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

async function readJson(request) {
  let text = "";
  for await (const chunk of request) {
    text += chunk;
    if (text.length > 100000) throw new BillingLedgerError("Request body is too large", 413);
  }
  if (!text.trim()) return {};
  try {
    return JSON.parse(text);
  } catch {
    throw new BillingLedgerError("Invalid JSON body", 400);
  }
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

function requireDurableMutationStore(ledger, env, allowEphemeralStore) {
  // Require both a test runtime and an explicit caller opt-in; NODE_ENV alone is not a safety boundary.
  if (
    ledger.store instanceof MemoryLedgerStore &&
    !(env.NODE_ENV === "test" && allowEphemeralStore === true)
  ) {
    throw new BillingLedgerError("Persistent billing storage is not configured", 503);
  }
}

export class BillingLedger {
  constructor({ store = new MemoryLedgerStore(), idGenerator = randomUUID, now = () => new Date().toISOString() } = {}) {
    this.store = store;
    this.idGenerator = idGenerator;
    this.now = now;
  }

  async recordUsage(input) {
    const record = normalizeUsage({ ...input, recorded_at: input.recorded_at || this.now() });
    if (!Number.isSafeInteger(record.input_tokens) || record.input_tokens < 0 ||
        !Number.isSafeInteger(record.output_tokens) || record.output_tokens < 0) {
      throw new BillingLedgerError("usage tokens must be non-negative safe integers");
    }
    return this.store.recordUsage(record);
  }

  async setCredits(input) {
    if (!input || typeof input !== "object" || Array.isArray(input)) {
      throw new BillingLedgerError("Credits payload must be an object");
    }
    const tenantId = requireString(input.tenant_id, "tenant_id");
    const credits = input.credits;
    if (!Number.isSafeInteger(credits) || credits < 0) {
      throw new BillingLedgerError("credits must be a non-negative safe integer");
    }
    return this.store.setCredits(tenantId, credits);
  }

  async createInvoiceIntent(input) {
    const intent = {
      intent_id: this.idGenerator(),
      idempotency_key: requireString(input.idempotency_key, "idempotency_key"),
      tenant_id: requireString(input.tenant_id, "tenant_id"),
      currency: requireString(input.currency, "currency").toUpperCase(),
      amount_minor: Number(input.amount_minor),
      status: "requires_payment_processor",
      created_at: this.now(),
    };
    if (!Number.isInteger(intent.amount_minor) || intent.amount_minor <= 0) throw new BillingLedgerError("amount_minor must be a positive integer");
    return this.store.createInvoiceIntent(intent);
  }
}

export function createBillingLedgerServer({
  env = process.env,
  ledger = new BillingLedger(),
  allowEphemeralStore = false,
} = {}) {
  return createServer(async (request, response) => {
    if (request.method === "GET" && request.url === "/health") return send(response, 200, { status: "ok", service: "billing-ledger", wallet_authority: false, card_data: false });
    if (!authorized(request, env)) return send(response, 401, { error: "Unauthorized" });

    try {
      if (request.method === "POST" && request.url === "/v1/usage") {
        requireDurableMutationStore(ledger, env, allowEphemeralStore);
        const result = await ledger.recordUsage(await readJson(request));
        return send(response, result.duplicate ? 200 : 201, result);
      }
      if (request.method === "POST" && request.url === "/v1/credits") {
        requireDurableMutationStore(ledger, env, allowEphemeralStore);
        return send(response, 200, await ledger.setCredits(await readJson(request)));
      }
      if (request.method === "POST" && request.url === "/v1/invoice-intents") {
        requireDurableMutationStore(ledger, env, allowEphemeralStore);
        return send(response, 201, await ledger.createInvoiceIntent(await readJson(request)));
      }
      return send(response, 404, { error: "Not found" });
    } catch (error) {
      if (error instanceof BillingLedgerError) {
        return send(response, error.status, { error: error.message });
      }
      // Do not expose database, adapter, or runtime exception details to callers.
      return send(response, 500, { error: "Internal server error" });
    }
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  createBillingLedgerServer().listen(defaultPort, defaultHost, () => console.log("billing-ledger listening on http://" + defaultHost + ":" + defaultPort));
}
