const MAX_PROMPT_CHARACTERS = 12_000;
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const SAFE_FILE_NAME = /^[a-zA-Z0-9][a-zA-Z0-9._ -]{0,127}$/;

export class ChatRequestError extends Error {}

export function validateChatRequest(body) {
  if (!body || typeof body !== "object") throw new ChatRequestError("Request body must be an object");
  const prompt = typeof body.prompt === "string" ? body.prompt.trim() : "";
  const model = typeof body.model === "string" ? body.model.trim() : "default";
  if (!prompt) throw new ChatRequestError("Prompt is required");
  if (prompt.length > MAX_PROMPT_CHARACTERS) throw new ChatRequestError("Prompt exceeds 12000 characters");
  if (!model) throw new ChatRequestError("Model is required");
  return { prompt, model };
}

function config(env) {
  const baseUrl = env.Z_PLATFORM_AI_GATEWAY_URL?.trim().replace(/\/$/, "");
  const token = env.Z_PLATFORM_SERVICE_TOKEN;
  if (!baseUrl || !token) throw new ChatRequestError("AI gateway is not configured");
  return { baseUrl, token };
}

function gatewayUrl(baseUrl, path) {
  const gatewayPath = baseUrl.endsWith("/v1") && path.startsWith("/v1/") ? path.slice(3) : path;
  return baseUrl + gatewayPath;
}

async function requestGateway(path, options, { fetchImpl = fetch, env = process.env } = {}) {
  const { baseUrl, token } = config(env);
  let response;
  try {
    response = await fetchImpl(gatewayUrl(baseUrl, path), {
      ...options,
      headers: { Authorization: "Bearer " + token, ...options.headers },
      signal: AbortSignal.timeout(60_000),
    });
  } catch {
    throw new ChatRequestError("AI gateway request failed");
  }
  if (!response.ok) throw new ChatRequestError("AI gateway rejected the request");
  return response;
}

export async function forwardChat(body, options = {}) {
  const { prompt, model } = validateChatRequest(body);
  const response = await requestGateway("/v1/chat/completions", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ model, messages: [{ role: "user", content: prompt }], stream: false }),
  }, options);
  const payload = await response.json().catch(() => { throw new ChatRequestError("AI gateway returned invalid JSON"); });
  const content = payload?.choices?.[0]?.message?.content;
  if (typeof content !== "string") throw new ChatRequestError("AI gateway returned an unsupported response");
  return { content };
}

export async function forwardChatStream(body, options = {}) {
  const { prompt, model } = validateChatRequest(body);
  const response = await requestGateway("/v1/chat/completions", {
    method: "POST",
    headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
    body: JSON.stringify({ model, messages: [{ role: "user", content: prompt }], stream: true }),
  }, options);
  if (!response.body) throw new ChatRequestError("AI gateway returned an empty stream");
  return response.body;
}

export async function forwardFile({ name, type, bytes }, options = {}) {
  if (!SAFE_FILE_NAME.test(name) || name.includes("..")) throw new ChatRequestError("File name is invalid");
  if (!bytes?.length || bytes.length > MAX_FILE_BYTES) throw new ChatRequestError("File must be between 1 byte and 10 MB");
  const response = await requestGateway("/v1/files", {
    method: "POST",
    headers: { "Content-Type": type || "application/octet-stream", "X-Filename": name },
    body: bytes,
  }, options);
  const payload = await response.json().catch(() => { throw new ChatRequestError("AI gateway returned invalid JSON"); });
  if (typeof payload?.id !== "string") throw new ChatRequestError("AI gateway returned an invalid file record");
  return { id: payload.id, name, size_bytes: bytes.length };
}
