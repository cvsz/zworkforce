import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import { dirname, extname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "public");
const host = process.env.HOST || "127.0.0.1";
const port = Number(process.env.PORT || 3005);
const contentTypes = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
};

function sendJson(response, status, payload) {
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
  });
  response.end(JSON.stringify(payload));
}

function isTenantScopedApiRequest(request) {
  const pathname = (request.url || "/").split("?", 1)[0];

  if (request.method === "POST") {
    return [
      "/api/workspaces",
      "/api/chat",
      "/api/chat/stream",
      "/api/files",
    ].includes(pathname);
  }

  return (
    request.method === "GET" &&
    /^\/api\/workspaces\/[^/]+$/.test(pathname)
  );
}

function rejectUnverifiedTenant(response) {
  response.writeHead(503, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    Connection: "close",
  });
  response.end(
    JSON.stringify({
      error: "Authenticated tenant identity is not configured",
    }),
  );
}

export function createZaiCoderServer() {
  return createServer(async (request, response) => {
    if (isTenantScopedApiRequest(request)) {
      return rejectUnverifiedTenant(response);
    }

    const pathname = (request.url || "/").split("?", 1)[0];
    const path = pathname === "/" ? "/index.html" : pathname;
    if (!path || path.includes("..")) {
      return sendJson(response, 404, { error: "Not found" });
    }

    const file = join(root, path);
    try {
      if (!(await stat(file)).isFile()) throw new Error("not a file");
      response.writeHead(200, {
        "Content-Type":
          contentTypes[extname(file)] || "application/octet-stream",
      });
      createReadStream(file).pipe(response);
    } catch {
      sendJson(response, 404, { error: "Not found" });
    }
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  createZaiCoderServer().listen(port, host, () => {
    console.log("zaicoder web listening on http://" + host + ":" + port);
  });
}
