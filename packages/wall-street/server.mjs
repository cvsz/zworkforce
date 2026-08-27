import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
const host = process.env.WALL_STREET_HOST || '127.0.0.1';
const port = Number(process.env.WALL_STREET_PORT || '4174');
const zworkforceUrl = (process.env.ZWORKFORCE_URL || 'http://127.0.0.1:9569').replace(/\/$/, '');

const contentTypes = new Map([
  ['.html', 'text/html; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.css', 'text/css; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
]);

const csp = [
  "default-src 'self'",
  "script-src 'self' https://s3.tradingview.com",
  "style-src 'self'",
  "img-src 'self' data: https://s3-symbol-logo.tradingview.com",
  "frame-src https://www.tradingview.com https://s.tradingview.com",
  "connect-src 'self' https://api.binance.com https://api.kucoin.com wss://stream.binance.com:9443 wss://*.kucoin.com",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  "frame-ancestors 'none'",
].join('; ');

function sendHeaders(res, status, type, length) {
  res.writeHead(status, {
    'Content-Type': type,
    ...(Number.isInteger(length) ? { 'Content-Length': String(length) } : {}),
    'Cache-Control': 'no-store',
    'Content-Security-Policy': csp,
    'Referrer-Policy': 'no-referrer',
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
  });
}

function sendJson(res, status, data) {
  const body = Buffer.from(JSON.stringify(data));
  sendHeaders(res, status, 'application/json; charset=utf-8', body.length);
  res.end(body);
}

async function healthBridge(res) {
  try {
    const upstream = await fetch(`${zworkforceUrl}/health`, {
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(3000),
    });
    if (!upstream.ok) {
      return sendJson(res, 502, { status: 'unavailable', upstream_status: upstream.status });
    }
    const body = await upstream.json();
    return sendJson(res, 200, {
      status: body?.status === 'ok' ? 'ok' : 'degraded',
      version: typeof body?.version === 'string' ? body.version : null,
    });
  } catch {
    return sendJson(res, 502, { status: 'unavailable' });
  }
}

async function staticFile(req, res, pathname) {
  const relative = pathname === '/' ? 'index.html' : pathname.slice(1);
  const target = resolve(root, relative);
  if (!target.startsWith(root.endsWith(sep) ? root : `${root}${sep}`)) {
    return sendJson(res, 404, { error: 'not_found' });
  }
  try {
    const info = await stat(target);
    if (!info.isFile()) return sendJson(res, 404, { error: 'not_found' });
    const data = await readFile(target);
    sendHeaders(res, 200, contentTypes.get(extname(target)) || 'application/octet-stream', data.length);
    if (req.method === 'HEAD') return res.end();
    return res.end(data);
  } catch {
    return sendJson(res, 404, { error: 'not_found' });
  }
}

const server = createServer(async (req, res) => {
  let url;
  try {
    url = new URL(req.url || '/', 'http://127.0.0.1');
  } catch {
    return sendJson(res, 400, { error: 'invalid_request' });
  }
  if (!['GET', 'HEAD'].includes(req.method || '')) {
    res.setHeader('Allow', 'GET, HEAD');
    return sendJson(res, 405, { error: 'method_not_allowed' });
  }
  if (url.pathname === '/api/zworkforce-health') return healthBridge(res);
  return staticFile(req, res, url.pathname);
});

server.listen(port, host, () => {
  console.log(`Wall Street operator surface listening on http://${host}:${port}`);
  console.log(`ZWorkforce health bridge target: ${zworkforceUrl}`);
});
