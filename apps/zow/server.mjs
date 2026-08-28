import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const defaultHost = process.env.HOST || "127.0.0.1";
const defaultPort = Number(process.env.PORT || 3030);

function send(response, status, body, type = "application/json; charset=utf-8") {
  response.writeHead(status, { "Content-Type": type });
  response.end(body);
}

async function readJson(request) {
  let text = "";
  for await (const chunk of request) {
    text += chunk;
    if (text.length > 100000) throw new Error("Request body is too large");
  }
  return text.trim() ? JSON.parse(text) : {};
}

function runtimeUrl(env, path) {
  const base = env.Z_PLATFORM_WORKSPACE_RUNTIME_URL?.replace(/\/$/, "");
  if (!base) throw new Error("Workspace runtime is not configured");
  return base + path;
}

async function forwardRuntime(path, input, env, fetchImpl) {
  const token = env.Z_PLATFORM_SERVICE_TOKEN;
  if (!token) throw new Error("Service token is not configured");
  const result = await fetchImpl(runtimeUrl(env, path), {
    method: "POST",
    headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  const payload = await result.json();
  if (!result.ok) throw new Error(payload.error || "Workspace runtime rejected the request");
  return payload;
}

export async function validateProject(input, env = process.env, fetchImpl = fetch) {
  return forwardRuntime("/v1/projects/validate", input, env, fetchImpl);
}

export async function requestShell(input, env = process.env, fetchImpl = fetch) {
  return forwardRuntime("/v1/shell", input, env, fetchImpl);
}

export async function requestDeploy(input, env = process.env, fetchImpl = fetch) {
  return forwardRuntime("/v1/deploy", input, env, fetchImpl);
}

export function createZowServer({ env = process.env, fetchImpl = fetch } = {}) {
  return createServer(async (request, response) => {
    try {
      if (request.method === "GET" && request.url === "/health") {
        return send(response, 200, JSON.stringify({ status: "ok", service: "zow", runtime_configured: Boolean(env.Z_PLATFORM_WORKSPACE_RUNTIME_URL && env.Z_PLATFORM_SERVICE_TOKEN) }));
      }
      if (request.method === "POST" && request.url === "/api/projects/validate") return send(response, 200, JSON.stringify(await validateProject(await readJson(request), env, fetchImpl)));
      if (request.method === "POST" && request.url === "/api/shell") return send(response, 202, JSON.stringify(await requestShell(await readJson(request), env, fetchImpl)));
      if (request.method === "POST" && request.url === "/api/deploy") return send(response, 202, JSON.stringify(await requestDeploy(await readJson(request), env, fetchImpl)));
      if (request.method === "GET" && request.url === "/") return send(response, 200, await readFile(new URL("./public/index.html", import.meta.url)), "text/html; charset=utf-8");
      return send(response, 404, JSON.stringify({ error: "Not found" }));
    } catch (error) {
      return send(response, 400, JSON.stringify({ error: error instanceof Error ? error.message : "Request failed" }));
    }
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  createZowServer().listen(defaultPort, defaultHost, () => {
    console.log("zow listening on http://" + defaultHost + ":" + defaultPort);
  });
}
