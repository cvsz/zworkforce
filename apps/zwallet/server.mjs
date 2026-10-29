import { createServer } from "node:http";
import { fileURLToPath } from "node:url";

const defaultHost = process.env.HOST || "127.0.0.1";
const defaultPort = Number(process.env.PORT || 3040);

class LedgerUnavailableError extends Error {
  constructor() {
    super("Billing service unavailable");
    this.name = "LedgerUnavailableError";
  }
}

function send(response, status, body, headers = {}) {
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    ...headers,
  });
  response.end(JSON.stringify(body));
}

async function readJson(request) {
  let text = "";
  for await (const chunk of request) text += chunk;
  return text.trim() ? JSON.parse(text) : {};
}

function ledgerUrl(env, path) {
  const configured = env.Z_PLATFORM_BILLING_LEDGER_URL;
  const base = typeof configured === "string" ? configured.trim().replace(/\/+$/, "") : "";
  if (!base) throw new LedgerUnavailableError();
  return base + path;
}

async function forwardLedger(path, input, env, fetchImpl) {
  const configuredToken = env.Z_PLATFORM_SERVICE_TOKEN;
  const token = typeof configuredToken === "string" ? configuredToken.trim() : "";
  if (!token) throw new LedgerUnavailableError();

  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("Request body must be a JSON object");
  }

  const forbidden = ["wallet_signature", "card_number", "kyc_payload", "mpc_share", "swap_route"];
  for (const key of forbidden) {
    if (Object.hasOwn(input, key)) throw new Error(`${key} is not accepted by the audited adapter`);
  }

  try {
    const result = await fetchImpl(ledgerUrl(env, path), {
      method: "POST",
      headers: {
        Authorization: "Bearer " + token,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(input),
    });

    if (!result || result.ok !== true) throw new LedgerUnavailableError();

    const payload = await result.json();
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new LedgerUnavailableError();
    }
    return payload;
  } catch (error) {
    if (error instanceof LedgerUnavailableError) throw error;
    // Do not propagate transport details, response bodies, or parser errors to callers.
    throw new LedgerUnavailableError();
  }
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
        return send(response, 200, {
          status: "ok",
          service: "zwallet-adapter",
          ledger_configured: Boolean(env.Z_PLATFORM_BILLING_LEDGER_URL && env.Z_PLATFORM_SERVICE_TOKEN),
          wallet_authority: false,
          card_data: false,
        });
      }
      if (request.method === "POST" && request.url === "/api/invoice-intents") {
        return send(response, 201, await createInvoiceIntent(await readJson(request), env, fetchImpl));
      }
      if (request.method === "POST" && request.url === "/api/credits") {
        return send(response, 200, await setCredits(await readJson(request), env, fetchImpl));
      }
      return send(response, 404, { error: "Not found" });
    } catch (error) {
      if (error instanceof LedgerUnavailableError) {
        return send(
          response,
          503,
          { error: "Billing service unavailable" },
          { "Cache-Control": "no-store" },
        );
      }
      return send(response, 400, { error: error.message || "Request failed" });
    }
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  createZWalletServer().listen(defaultPort, defaultHost, () => console.log("zwallet adapter listening on http://" + defaultHost + ":" + defaultPort));
}
