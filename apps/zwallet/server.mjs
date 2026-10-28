import { createServer } from "node:http";
import { fileURLToPath } from "node:url";

const defaultHost = process.env.HOST || "127.0.0.1";
const defaultPort = Number(process.env.PORT || 3040);
const MAX_REQUEST_BODY_BYTES = 64 * 1024;

class LedgerUnavailableError extends Error {
  constructor() {
    super("Billing ledger unavailable");
    this.name = "LedgerUnavailableError";
  }
}

class AdapterInputError extends Error {
  constructor(message) {
    super(message);
    this.name = "AdapterInputError";
  }
}

class RequestTooLargeError extends Error {
  constructor() {
    super("Request body too large");
    this.name = "RequestTooLargeError";
  }
}

function send(response, status, body) {
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  response.end(JSON.stringify(body));
}

async function readJson(request) {
  const chunks = [];
  let bytes = 0;
  for await (const chunk of request) {
    const data = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    bytes += data.length;
    if (bytes > MAX_REQUEST_BODY_BYTES) throw new RequestTooLargeError();
    chunks.push(data);
  }
  const text = Buffer.concat(chunks).toString("utf8");
  if (!text.trim()) return {};
  const value = JSON.parse(text);
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new AdapterInputError("JSON body must be an object");
  }
  return value;
}

function ledgerUrl(env, path) {
  const base = env.Z_PLATFORM_BILLING_LEDGER_URL?.replace(/\/$/, "");
  if (!base) throw new LedgerUnavailableError();
  return base + path;
}

function ledgerTimeoutMs(env) {
  const raw = env.Z_PLATFORM_BILLING_LEDGER_TIMEOUT_MS;
  if (raw === undefined || raw === "") return 5000;
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < 100 || value > 30000) {
    throw new LedgerUnavailableError();
  }
  return value;
}

async function forwardLedger(path, input, env, fetchImpl) {
  if (input === null || typeof input !== "object" || Array.isArray(input)) {
    throw new AdapterInputError("JSON body must be an object");
  }
  const token = env.Z_PLATFORM_SERVICE_TOKEN;
  if (!token) throw new LedgerUnavailableError();
  const forbidden = ["wallet_signature", "card_number", "kyc_payload", "mpc_share", "swap_route"];
  for (const key of forbidden) {
    if (Object.hasOwn(input, key)) {
      throw new AdapterInputError(`${key} is not accepted by the audited adapter`);
    }
  }

  const timeoutMs = ledgerTimeoutMs(env);
  let result;
  try {
    result = await fetchImpl(ledgerUrl(env, path), {
      method: "POST",
      headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
      body: JSON.stringify(input),
      redirect: "error",
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch {
    throw new LedgerUnavailableError();
  }

  if (!result.ok) {
    // Redirects are never followed for financial mutations. Treat any 3xx
    // response as an upstream protocol/availability failure, not client input.
    if ((result.status >= 300 && result.status < 400) || result.status >= 500 || result.status === 429 || result.status === 401 || result.status === 403 || result.status === 408) {
      throw new LedgerUnavailableError();
    }
    throw new AdapterInputError("Billing ledger rejected the request");
  }

  let payload;
  try {
    payload = await result.json();
  } catch {
    throw new LedgerUnavailableError();
  }
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    throw new LedgerUnavailableError();
  }
  return payload;
}

export async function createInvoiceIntent(input, env = process.env, fetchImpl = fetch) {
  return forwardLedger("/v1/invoice-intents", input, env, fetchImpl);
}

export async function setCredits(input, env = process.env, fetchImpl = fetch) {
  return forwardLedger("/v1/credits", input, env, fetchImpl);
}

export function createZWalletServer({ env = process.env, fetchImpl = fetch } = {}) {
  return createServer(async (request, response) => {
    try {
      if (request.method === "GET" && request.url === "/health") {
        return send(response, 200, { status: "ok", service: "zwallet-adapter", ledger_configured: Boolean(env.Z_PLATFORM_BILLING_LEDGER_URL && env.Z_PLATFORM_SERVICE_TOKEN), wallet_authority: false, card_data: false });
      }
      if (request.method === "POST" && request.url === "/api/invoice-intents") return send(response, 201, await createInvoiceIntent(await readJson(request), env, fetchImpl));
      if (request.method === "POST" && request.url === "/api/credits") return send(response, 200, await setCredits(await readJson(request), env, fetchImpl));
      return send(response, 404, { error: "Not found" });
    } catch (error) {
      if (error instanceof LedgerUnavailableError) {
        return send(response, 503, { error: "Billing ledger unavailable" });
      }
      if (error instanceof RequestTooLargeError) {
        return send(response, 413, { error: "Request body too large" });
      }
      if (error instanceof AdapterInputError) {
        return send(response, 400, { error: error.message });
      }
      if (error instanceof SyntaxError) {
        return send(response, 400, { error: "Invalid JSON" });
      }
      return send(response, 500, { error: "Internal server error" });
    }
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  createZWalletServer().listen(defaultPort, defaultHost, () => console.log("zwallet adapter listening on http://" + defaultHost + ":" + defaultPort));
}
