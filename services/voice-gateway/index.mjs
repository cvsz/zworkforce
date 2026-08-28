import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import { createServer } from "node:http";
import { connect as connectTcp } from "node:net";
import { fileURLToPath } from "node:url";

const DEFAULT_TICKET_TTL_SECONDS = 60;
const MAX_BODY_BYTES = 32 * 1024;

function log(level, event, fields = {}) {
  process.stdout.write(`${JSON.stringify({
    timestamp: new Date().toISOString(),
    level,
    service: "voice-gateway",
    event,
    ...fields,
  })}\n`);
}

function sendJson(response, status, payload, headers = {}) {
  const body = JSON.stringify(payload);
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(body),
    "Cache-Control": "no-store",
    ...headers,
  });
  response.end(body);
}

async function readJson(request) {
  let size = 0;
  const chunks = [];
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) throw new Error("Request body is too large");
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function base64UrlEncode(value) {
  return Buffer.from(value).toString("base64url");
}

function base64UrlDecode(value) {
  return Buffer.from(value, "base64url");
}

function boundedInteger(value, fallback, minimum, maximum) {
  const number = Number(value);
  if (!Number.isInteger(number) || number < minimum || number > maximum) return fallback;
  return number;
}

export function parseBearer(header) {
  if (typeof header !== "string") return null;
  const trimmed = header.trim();
  if (!trimmed.toLowerCase().startsWith("bearer ")) return null;
  const token = trimmed.slice(7).trim();
  return token || null;
}

export function createTicketCodec(secret, { now = () => Date.now(), usedNonces = new Map() } = {}) {
  if (typeof secret !== "string" || secret.length < 32) {
    throw new Error("VOICE_TICKET_SECRET must be at least 32 characters");
  }

  function purgeExpiredNonces(currentSeconds) {
    for (const [nonce, expiresAt] of usedNonces) {
      if (expiresAt <= currentSeconds) usedNonces.delete(nonce);
    }
  }

  function sign(encodedPayload) {
    return createHmac("sha256", secret).update(encodedPayload).digest();
  }

  function issue({ tenantId, subjectId, ttlSeconds = DEFAULT_TICKET_TTL_SECONDS }) {
    const issuedAt = Math.floor(now() / 1000);
    const ttl = boundedInteger(ttlSeconds, DEFAULT_TICKET_TTL_SECONDS, 10, 300);
    const claims = {
      v: 1,
      iat: issuedAt,
      nbf: issuedAt - 5,
      exp: issuedAt + ttl,
      nonce: randomBytes(18).toString("base64url"),
      tenant_id: tenantId,
      subject_id: subjectId,
    };
    const encodedPayload = base64UrlEncode(JSON.stringify(claims));
    const signature = base64UrlEncode(sign(encodedPayload));
    return {
      ticket: `${encodedPayload}.${signature}`,
      claims,
    };
  }

  function verify(ticket, { consume = true } = {}) {
    if (typeof ticket !== "string" || ticket.length > 4096) {
      throw new Error("Invalid voice ticket");
    }
    const parts = ticket.split(".");
    if (parts.length !== 2) throw new Error("Invalid voice ticket");

    const [encodedPayload, encodedSignature] = parts;
    const expected = sign(encodedPayload);
    const actual = base64UrlDecode(encodedSignature);
    if (expected.length !== actual.length || !timingSafeEqual(expected, actual)) {
      throw new Error("Invalid voice ticket signature");
    }

    let claims;
    try {
      claims = JSON.parse(base64UrlDecode(encodedPayload).toString("utf8"));
    } catch {
      throw new Error("Invalid voice ticket payload");
    }

    const currentSeconds = Math.floor(now() / 1000);
    purgeExpiredNonces(currentSeconds);
    if (claims?.v !== 1 || !claims.nonce || !claims.tenant_id || !claims.subject_id) {
      throw new Error("Incomplete voice ticket");
    }
    if (claims.nbf > currentSeconds || claims.exp <= currentSeconds) {
      throw new Error("Expired voice ticket");
    }
    if (usedNonces.has(claims.nonce)) {
      throw new Error("Voice ticket was already used");
    }
    if (consume) usedNonces.set(claims.nonce, claims.exp);
    return claims;
  }

  return { issue, verify, usedNonces };
}

function clientIp(request) {
  const forwarded = request.headers["x-forwarded-for"];
  if (typeof forwarded === "string" && forwarded.trim()) return forwarded.split(",")[0].trim();
  return request.socket.remoteAddress || "unknown";
}

function requestIdentity(request, allowAnonymous) {
  const tenantId = String(request.headers["x-tenant-id"] || "").trim();
  const subjectId = String(
    request.headers["x-subject-id"] || request.headers["x-user-id"] || "",
  ).trim();

  if (tenantId && subjectId) return { tenantId, subjectId };
  if (allowAnonymous) {
    return {
      tenantId: tenantId || "anonymous",
      subjectId: subjectId || "anonymous",
    };
  }
  throw new Error("Tenant and subject headers are required");
}

function extractTicket(request) {
  const protocols = String(request.headers["sec-websocket-protocol"] || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  const ticketProtocol = protocols.find((value) => value.startsWith("zticket."));
  if (ticketProtocol) {
    return {
      ticket: ticketProtocol.slice("zticket.".length),
      forwardedProtocols: protocols.filter((value) => !value.startsWith("zticket.")),
    };
  }

  const url = new URL(request.url || "/", "http://voice-gateway.local");
  return {
    ticket: url.searchParams.get("ticket"),
    forwardedProtocols: protocols,
  };
}

function cleanUpstreamPath(rawUrl) {
  const url = new URL(rawUrl || "/v1/realtime", "http://voice-gateway.local");
  url.searchParams.delete("ticket");
  const query = url.searchParams.toString();
  return `${url.pathname}${query ? `?${query}` : ""}`;
}

function serializeUpgradeRequest(request, target, claims, forwardedProtocols) {
  const headers = { ...request.headers };
  delete headers["proxy-connection"];
  delete headers["content-length"];
  delete headers["sec-websocket-protocol"];
  headers.host = target.host;
  headers.connection = "Upgrade";
  headers.upgrade = "websocket";
  headers["x-z-platform-tenant"] = claims.tenant_id;
  headers["x-z-platform-subject"] = claims.subject_id;
  headers["x-z-platform-voice-session"] = claims.nonce;
  if (forwardedProtocols.length) {
    headers["sec-websocket-protocol"] = forwardedProtocols.join(", ");
  }

  const lines = [`GET ${cleanUpstreamPath(request.url)} HTTP/1.1`];
  for (const [name, value] of Object.entries(headers)) {
    if (value == null) continue;
    if (Array.isArray(value)) {
      for (const item of value) lines.push(`${name}: ${item}`);
    } else {
      lines.push(`${name}: ${value}`);
    }
  }
  return `${lines.join("\r\n")}\r\n\r\n`;
}

function closeSocket(socket, status, message) {
  if (!socket.destroyed) {
    socket.end(
      `HTTP/1.1 ${status}\r\nConnection: close\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: ${Buffer.byteLength(message)}\r\n\r\n${message}`,
    );
  }
}

export function createVoiceGateway({ env = process.env, now = () => Date.now() } = {}) {
  const serviceToken = env.Z_PLATFORM_SERVICE_TOKEN;
  if (!serviceToken) throw new Error("Z_PLATFORM_SERVICE_TOKEN is required");

  const codec = createTicketCodec(env.VOICE_TICKET_SECRET || "", { now });
  const upstream = new URL(env.VOICE_AGENT_URL || "http://voice-agent:8765");
  const publicWebSocketUrl = env.VOICE_PUBLIC_WS_URL || "ws://127.0.0.1:8450/v1/realtime";
  const allowAnonymous = String(env.VOICE_ALLOW_ANONYMOUS || "false").toLowerCase() === "true";
  const ticketTtlSeconds = boundedInteger(env.VOICE_TICKET_TTL_SECONDS, 60, 10, 300);
  const maxSessions = boundedInteger(env.VOICE_MAX_SESSIONS, 4, 1, 1024);
  const maxSessionsPerIp = boundedInteger(env.VOICE_MAX_SESSIONS_PER_IP, 2, 1, 128);

  let activeSessions = 0;
  const sessionsByIp = new Map();
  const metrics = {
    ticketsIssued: 0,
    ticketFailures: 0,
    websocketAccepted: 0,
    websocketRejected: 0,
    upstreamFailures: 0,
  };

  const requestHandler = async (request, response) => {
    try {
      if (request.method === "GET" && request.url === "/health") {
        return sendJson(response, 200, {
          status: "ok",
          service: "voice-gateway",
          active_sessions: activeSessions,
          max_sessions: maxSessions,
        });
      }

      if (request.method === "GET" && request.url === "/metrics") {
        const body = [
          "# TYPE z_platform_voice_active_sessions gauge",
          `z_platform_voice_active_sessions ${activeSessions}`,
          "# TYPE z_platform_voice_tickets_issued_total counter",
          `z_platform_voice_tickets_issued_total ${metrics.ticketsIssued}`,
          "# TYPE z_platform_voice_ticket_failures_total counter",
          `z_platform_voice_ticket_failures_total ${metrics.ticketFailures}`,
          "# TYPE z_platform_voice_websocket_accepted_total counter",
          `z_platform_voice_websocket_accepted_total ${metrics.websocketAccepted}`,
          "# TYPE z_platform_voice_websocket_rejected_total counter",
          `z_platform_voice_websocket_rejected_total ${metrics.websocketRejected}`,
          "# TYPE z_platform_voice_upstream_failures_total counter",
          `z_platform_voice_upstream_failures_total ${metrics.upstreamFailures}`,
          "",
        ].join("\n");
        response.writeHead(200, {
          "Content-Type": "text/plain; version=0.0.4; charset=utf-8",
          "Cache-Control": "no-store",
        });
        return response.end(body);
      }

      if (request.method === "POST" && request.url === "/v1/voice/tickets") {
        if (parseBearer(request.headers.authorization) !== serviceToken) {
          metrics.ticketFailures += 1;
          return sendJson(response, 401, { error: { code: "UNAUTHORIZED", message: "Invalid service token" } });
        }

        const identity = requestIdentity(request, allowAnonymous);
        await readJson(request); // Parse and bound the body for forward-compatible metadata.
        const { ticket, claims } = codec.issue({
          tenantId: identity.tenantId,
          subjectId: identity.subjectId,
          ttlSeconds: ticketTtlSeconds,
        });
        metrics.ticketsIssued += 1;
        log("info", "ticket_issued", {
          tenant_id: identity.tenantId,
          expires_at: claims.exp,
        });
        return sendJson(response, 201, {
          ticket,
          expires_at: new Date(claims.exp * 1000).toISOString(),
          websocket_url: publicWebSocketUrl,
          ticket_transport: "sec-websocket-protocol",
        });
      }

      return sendJson(response, 404, { error: { code: "NOT_FOUND", message: "Route not found" } });
    } catch (error) {
      metrics.ticketFailures += 1;
      log("warn", "request_rejected", { message: error instanceof Error ? error.message : "Request failed" });
      return sendJson(response, 400, {
        error: { code: "BAD_REQUEST", message: error instanceof Error ? error.message : "Request failed" },
      });
    }
  };

  const server = createServer(requestHandler);

  server.on("upgrade", (request, socket, head) => {
    const ip = clientIp(request);
    try {
      if (!request.url?.startsWith("/v1/realtime")) {
        metrics.websocketRejected += 1;
        return closeSocket(socket, "404 Not Found", "Not found");
      }
      if (activeSessions >= maxSessions || (sessionsByIp.get(ip) || 0) >= maxSessionsPerIp) {
        metrics.websocketRejected += 1;
        return closeSocket(socket, "429 Too Many Requests", "Voice session limit reached");
      }

      const { ticket, forwardedProtocols } = extractTicket(request);
      const claims = codec.verify(ticket);
      activeSessions += 1;
      sessionsByIp.set(ip, (sessionsByIp.get(ip) || 0) + 1);
      metrics.websocketAccepted += 1;

      let released = false;
      const release = () => {
        if (released) return;
        released = true;
        activeSessions = Math.max(0, activeSessions - 1);
        const remaining = Math.max(0, (sessionsByIp.get(ip) || 1) - 1);
        if (remaining) sessionsByIp.set(ip, remaining);
        else sessionsByIp.delete(ip);
        log("info", "session_closed", {
          tenant_id: claims.tenant_id,
          active_sessions: activeSessions,
        });
      };

      const upstreamSocket = connectTcp(
        {
          host: upstream.hostname,
          port: Number(upstream.port || 80),
        },
        () => {
          upstreamSocket.write(serializeUpgradeRequest(request, upstream, claims, forwardedProtocols));
          if (head?.length) upstreamSocket.write(head);
          socket.pipe(upstreamSocket);
          upstreamSocket.pipe(socket);
          log("info", "session_opened", {
            tenant_id: claims.tenant_id,
            active_sessions: activeSessions,
          });
        },
      );

      socket.setTimeout(0);
      upstreamSocket.setTimeout(0);
      socket.on("close", release);
      socket.on("error", release);
      upstreamSocket.on("close", release);
      upstreamSocket.on("error", (error) => {
        metrics.upstreamFailures += 1;
        log("error", "upstream_socket_error", { message: error.message });
        if (!socket.destroyed) socket.destroy();
        release();
      });
    } catch (error) {
      metrics.websocketRejected += 1;
      log("warn", "websocket_rejected", { ip, message: error instanceof Error ? error.message : "Rejected" });
      closeSocket(socket, "401 Unauthorized", "Invalid or expired voice ticket");
    }
  });

  return { server, codec, metrics };
}

export function startVoiceGateway(options = {}) {
  const env = options.env || process.env;
  const { server } = createVoiceGateway(options);
  const host = env.HOST || "0.0.0.0";
  const port = Number(env.PORT || 8450);
  server.listen(port, host, () => log("info", "listening", { host, port }));
  return server;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  startVoiceGateway();
}
