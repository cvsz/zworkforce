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
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
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
  return text.trim() ? JSON.parse(text) : {};
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
    input_tokens: Number(input.input_tokens || 0),
    output_tokens: Number(input.output_tokens || 0),
    recorded_at: input.recorded_at || new Date().toISOString(),
  };
}

export class MemoryLedgerStore {
  constructor() {
    this.records = new Map();
    this.credits = new Map();
    this.invoiceIntents = new Map();
  }

  async recordUsage(record) {
    if (this.records.has(record.idempotency_key)) return { duplicate: true, record: this.records.get(record.idempotency_key) };
    this.records.set(record.idempotency_key, structuredClone(record));
    return { duplicate: false, record };
  }

  async setCredits(tenantId, amount) {
    this.credits.set(tenantId, Number(amount));
    return { tenant_id: tenantId, credits: this.credits.get(tenantId) };
  }

  async createInvoiceIntent(intent) {
    if (this.invoiceIntents.has(intent.idempotency_key)) return this.invoiceIntents.get(intent.idempotency_key);
    this.invoiceIntents.set(intent.idempotency_key, structuredClone(intent));
    return intent;
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
    if (record.input_tokens < 0 || record.output_tokens < 0) throw new BillingLedgerError("usage tokens must be non-negative");
    return this.store.recordUsage(record);
  }

  async setCredits(input) {
    return this.store.setCredits(requireString(input.tenant_id, "tenant_id"), Number(input.credits));
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

export function createBillingLedgerServer({ env = process.env, ledger = new BillingLedger() } = {}) {
  return createServer(async (request, response) => {
    if (request.method === "GET" && request.url === "/health") return send(response, 200, { status: "ok", service: "billing-ledger", wallet_authority: false, card_data: false });
    if (!authorized(request, env)) return send(response, 401, { error: "Unauthorized" });

    try {
      if (request.method === "POST" && request.url === "/v1/usage") {
        const result = await ledger.recordUsage(await readJson(request));
        return send(response, result.duplicate ? 200 : 201, result);
      }
      if (request.method === "POST" && request.url === "/v1/credits") return send(response, 200, await ledger.setCredits(await readJson(request)));
      if (request.method === "POST" && request.url === "/v1/invoice-intents") return send(response, 201, await ledger.createInvoiceIntent(await readJson(request)));
      return send(response, 404, { error: "Not found" });
    } catch (error) {
      return send(response, error instanceof BillingLedgerError ? error.status : 400, { error: error.message || "Request failed" });
    }
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  createBillingLedgerServer().listen(defaultPort, defaultHost, () => console.log("billing-ledger listening on http://" + defaultHost + ":" + defaultPort));
}
