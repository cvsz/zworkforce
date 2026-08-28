import { timingSafeEqual } from 'node:crypto';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createLocalHealthAdapter } from './local-health-adapter.mjs';
import { ZarvisProactiveRuntime, ProactiveError, ZARVIS_OWNER_GITHUB_ID } from './runtime.mjs';
import { FileProactiveStore } from './store.mjs';

const PUBLIC_DIR = fileURLToPath(new URL('./public/', import.meta.url));
const LOOPBACKS = new Set(['127.0.0.1', '::1', '::ffff:127.0.0.1']);
const JSON_LIMIT = 64 * 1024;

function requireSecret(name, value) {
  if (typeof value !== 'string' || Buffer.byteLength(value) < 32) {
    throw new Error(`${name} must contain at least 32 bytes`);
  }
  return value;
}

function secureEqual(left, right) {
  const a = Buffer.from(left ?? '');
  const b = Buffer.from(right ?? '');
  return a.length === b.length && a.length > 0 && timingSafeEqual(a, b);
}

function serialExecutor() {
  let tail = Promise.resolve();
  return (operation) => {
    const run = tail.then(operation, operation);
    tail = run.then(() => undefined, () => undefined);
    return run;
  };
}

function json(res, status, payload) {
  const body = `${JSON.stringify(payload)}\n`;
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(body),
    'cache-control': 'no-store',
    'x-content-type-options': 'nosniff',
  });
  res.end(body);
}

async function readJson(req) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > JSON_LIMIT) throw new ProactiveError('payload_too_large', 'JSON body is too large.', 413);
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    throw new ProactiveError('invalid_json', 'Request body must be valid JSON.');
  }
}

function requireLoopback(req) {
  if (!LOOPBACKS.has(req.socket.remoteAddress ?? '')) {
    throw new ProactiveError('local_access_only', 'This service accepts loopback clients only.', 403);
  }
}

function bearer(req) {
  const value = req.headers.authorization ?? '';
  return value.startsWith('Bearer ') ? value.slice(7) : '';
}

function requireOwner(req, ownerToken) {
  requireLoopback(req);
  if (!secureEqual(bearer(req), ownerToken)) throw new ProactiveError('owner_access_denied', 'Owner token is invalid.', 403);
}

function requireWorker(req, workerToken) {
  requireLoopback(req);
  const value = req.headers['x-zarvis-proactive-worker-token'];
  if (typeof value !== 'string' || !secureEqual(value, workerToken)) {
    throw new ProactiveError('worker_access_denied', 'Worker token is invalid.', 403);
  }
}

function match(pathname, pattern) {
  const value = pathname.match(pattern);
  return value ? value.slice(1).map(decodeURIComponent) : null;
}

async function serveStatic(pathname, res) {
  const relative = pathname === '/' ? 'index.html' : pathname.slice(1);
  if (!['index.html', 'app.js', 'styles.css'].includes(relative)) return false;
  const data = await readFile(join(PUBLIC_DIR, relative));
  const type = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8' }[extname(relative)];
  res.writeHead(200, {
    'content-type': type,
    'content-length': data.length,
    'cache-control': 'no-store',
    'content-security-policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
    'x-content-type-options': 'nosniff',
    'referrer-policy': 'no-referrer',
  });
  res.end(data);
  return true;
}

export function createProactiveServer({
  ownerToken = process.env.ZARVIS_LOCAL_OWNER_TOKEN,
  workerToken = process.env.ZARVIS_PROACTIVE_WORKER_TOKEN,
  runtime = new ZarvisProactiveRuntime({ store: new FileProactiveStore(), adapter: createLocalHealthAdapter() }),
} = {}) {
  const configuredOwnerToken = requireSecret('ZARVIS_LOCAL_OWNER_TOKEN', ownerToken);
  const configuredWorkerToken = requireSecret('ZARVIS_PROACTIVE_WORKER_TOKEN', workerToken);
  const mutate = serialExecutor();

  return createServer(async (req, res) => {
    try {
      requireLoopback(req);
      const url = new URL(req.url ?? '/', 'http://localhost');

      if (req.method === 'GET' && url.pathname === '/healthz') {
        json(res, 200, {
          status: 'ok',
          service: 'zarvis-proactive',
          local_only: true,
          owner_github_id: ZARVIS_OWNER_GITHUB_ID,
          autonomous_mutation: false,
          secrets_exposed: false,
        });
        return;
      }
      if (req.method === 'GET' && await serveStatic(url.pathname, res)) return;

      if (req.method === 'GET' && url.pathname === '/v1/status') {
        requireOwner(req, configuredOwnerToken);
        json(res, 200, await runtime.status());
        return;
      }
      if (req.method === 'GET' && url.pathname === '/v1/policy') {
        requireOwner(req, configuredOwnerToken);
        json(res, 200, await runtime.getPolicy());
        return;
      }
      if (req.method === 'PUT' && url.pathname === '/v1/policy') {
        requireOwner(req, configuredOwnerToken);
        const body = await readJson(req);
        json(res, 200, await mutate(() => runtime.updatePolicy(body)));
        return;
      }
      if (req.method === 'GET' && url.pathname === '/v1/subscriptions') {
        requireOwner(req, configuredOwnerToken);
        json(res, 200, { subscriptions: await runtime.listSubscriptions() });
        return;
      }
      if (req.method === 'POST' && url.pathname === '/v1/subscriptions') {
        requireOwner(req, configuredOwnerToken);
        const body = await readJson(req);
        json(res, 201, await mutate(() => runtime.createSubscription(body)));
        return;
      }
      if (req.method === 'GET' && url.pathname === '/v1/notifications') {
        requireOwner(req, configuredOwnerToken);
        json(res, 200, { notifications: await runtime.listNotifications() });
        return;
      }
      if (req.method === 'POST' && url.pathname === '/v1/internal/proactive/tick') {
        requireWorker(req, configuredWorkerToken);
        json(res, 200, await mutate(() => runtime.tick()));
        return;
      }

      let route = match(url.pathname, /^\/v1\/subscriptions\/([^/]+)\/revoke$/);
      if (req.method === 'POST' && route) {
        requireOwner(req, configuredOwnerToken);
        json(res, 200, await mutate(() => runtime.revokeSubscription(route[0])));
        return;
      }
      route = match(url.pathname, /^\/v1\/notifications\/([^/]+)\/feedback$/);
      if (req.method === 'POST' && route) {
        requireOwner(req, configuredOwnerToken);
        const body = await readJson(req);
        json(res, 200, await mutate(() => runtime.recordFeedback(route[0], body)));
        return;
      }
      route = match(url.pathname, /^\/v1\/notifications\/([^/]+)\/handoff$/);
      if (req.method === 'POST' && route) {
        requireOwner(req, configuredOwnerToken);
        json(res, 200, await mutate(() => runtime.createActionHandoff(route[0])));
        return;
      }

      json(res, 404, { error: 'not_found' });
    } catch (error) {
      if (error instanceof ProactiveError) {
        json(res, error.status, { error: error.code, message: error.message });
        return;
      }
      json(res, 500, { error: 'internal_error' });
    }
  });
}

export async function startProactiveServer() {
  const host = process.env.ZARVIS_PROACTIVE_HOST ?? '127.0.0.1';
  if (host !== '127.0.0.1' && host !== '::1') throw new Error('ZARVIS_PROACTIVE_HOST must be loopback in local-only mode');
  const port = Number(process.env.ZARVIS_PROACTIVE_PORT ?? 8099);
  const server = createProactiveServer();
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, host, resolve);
  });
  process.stdout.write(`zarvis-proactive listening on http://${host}:${port}\n`);
  return server;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  startProactiveServer().catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}
