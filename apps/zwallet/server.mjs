import { createServer } from "node:http";
import { fileURLToPath } from "node:url";

const defaultHost = process.env.HOST || "127.0.0.1";
const defaultPort = Number(process.env.PORT || 3040);

function send(response, status, body) {
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(body));
}

async function readJson(request) {
  let text = "";
  for await (const chunk of request) text += chunk;
  return text.trim() ? JSON.parse(text) : {};
}

function ledgerUrl(env, path) {
  const base = env.Z_PLATFORM_BILLING_LEDGER_URL?.replace(/\/$/, "");
  if (!base) throw new Error("Billing ledger is not configured");
  return base + path;
}

async function forwardLedger(path, input, env, fetchImpl) {
  const token = env.Z_PLATFORM_SERVICE_TOKEN;
  if (!token) throw new Error("Service token is not configured");
  const forbidden = ["wallet_signature", "card_number", "kyc_payload", "mpc_share", "swap_route"];
  for (const key of forbidden) if (Object.hasOwn(input, key)) throw new Error(`${key} is not accepted by the audited adapter`);
  const result = await fetchImpl(ledgerUrl(env, path), {
    method: "POST",
    headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  const payload = await result.json();
  if (!result.ok) throw new Error(payload.error || "Billing ledger rejected the request");
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
      return send(response, 400, { error: error.message || "Request failed" });
    }
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  createZWalletServer().listen(defaultPort, defaultHost, () => console.log("zwallet adapter listening on http://" + defaultHost + ":" + defaultPort));
}
