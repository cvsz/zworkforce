import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import { Readable } from "node:stream";
import { dirname, extname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { ChatRequestError, forwardChat, forwardChatStream, forwardFile } from "./gateway.mjs";
import { WorkspaceStoreError, createWorkspaceStoreFromEnv } from "./workspace-store.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "public");
const host = process.env.HOST || "127.0.0.1";
const port = Number(process.env.PORT || 3005);
const contentTypes = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8" };
const workspaceStore = createWorkspaceStoreFromEnv();

function sendJson(response, status, payload) {
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(payload));
}
async function readBody(request, limit = 1_000_000) {
  const chunks = []; let size = 0;
  for await (const chunk of request) { size += chunk.length; if (size > limit) throw new ChatRequestError("Request body is too large"); chunks.push(chunk); }
  return Buffer.concat(chunks);
}
async function readJson(request) {
  try { return JSON.parse((await readBody(request)).toString()); }
  catch (error) { if (error instanceof ChatRequestError) throw error; throw new ChatRequestError("Request body must be valid JSON"); }
}
function tenantOwner(request) {
  const value = request.headers["x-tenant-id"];
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}
function handleError(response, error) {
  sendJson(response, error instanceof ChatRequestError || error instanceof WorkspaceStoreError ? 400 : 500, { error: error.message || "Unexpected error" });
}

const server = createServer(async (request, response) => {
  try {
    if (request.method === "POST" && request.url === "/api/workspaces") {
      const input = await readJson(request);
      return sendJson(response, 200, await workspaceStore.ensure({ ...input, owner: tenantOwner(request) || input.owner }));
    }
    const workspaceMatch = request.url?.match(/^\/api\/workspaces\/([^/]+)$/);
    if (request.method === "GET" && workspaceMatch) {
      const workspace = await workspaceStore.read(workspaceMatch[1], { owner: tenantOwner(request) });
      return workspace ? sendJson(response, 200, workspace) : sendJson(response, 404, { error: "Workspace not found" });
    }
    if (request.method === "POST" && request.url === "/api/chat") return sendJson(response, 200, await forwardChat(await readJson(request)));
    if (request.method === "POST" && request.url === "/api/chat/stream") {
      const stream = await forwardChatStream(await readJson(request));
      response.writeHead(200, { "Cache-Control": "no-cache, no-transform", Connection: "keep-alive", "Content-Type": "text/event-stream; charset=utf-8", "X-Accel-Buffering": "no" });
      return Readable.fromWeb(stream).pipe(response);
    }
    if (request.method === "POST" && request.url === "/api/files") {
      const name = request.headers["x-filename"];
      if (typeof name !== "string") throw new ChatRequestError("X-Filename header is required");
      const uploaded = await forwardFile({ name, type: request.headers["content-type"], bytes: await readBody(request, 10 * 1024 * 1024) });
      const workspaceId = request.headers["x-workspace-id"];
      if (typeof workspaceId === "string" && workspaceId.trim()) {
        const workspace = await workspaceStore.addFile(workspaceId, uploaded, { owner: tenantOwner(request) });
        return sendJson(response, 200, { ...uploaded, workspace_id: workspace.id });
      }
      return sendJson(response, 200, uploaded);
    }
  } catch (error) { return handleError(response, error); }

  const path = request.url === "/" ? "/index.html" : request.url;
  if (!path || path.includes("..")) return sendJson(response, 404, { error: "Not found" });
  const file = join(root, path);
  try {
    if (!(await stat(file)).isFile()) throw new Error("not a file");
    response.writeHead(200, { "Content-Type": contentTypes[extname(file)] || "application/octet-stream" });
    createReadStream(file).pipe(response);
  } catch { sendJson(response, 404, { error: "Not found" }); }
});
server.listen(port, host, () => console.log("zaicoder web listening on http://" + host + ":" + port));
