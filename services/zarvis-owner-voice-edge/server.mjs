import { createServer, request as httpRequest } from 'node:http';

const HOST = process.env.HOST || '0.0.0.0';
const PORT = Number(process.env.PORT || 3023);
const UPSTREAM = new URL(process.env.ZVOICE_UPSTREAM_URL || 'http://zvoice:3022');
const OWNER_ID = '4076926';
const EDGE_SECRET = process.env.ZARVIS_EDGE_SHARED_SECRET || '';

if (Buffer.byteLength(EDGE_SECRET) < 32) {
  throw new Error('ZARVIS_EDGE_SHARED_SECRET must contain at least 32 bytes');
}

const HOP_BY_HOP = new Set([
  'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
  'te', 'trailer', 'transfer-encoding', 'upgrade',
]);

function filteredHeaders(headers) {
  return Object.fromEntries(
    Object.entries(headers).filter(([name]) => !HOP_BY_HOP.has(name.toLowerCase())),
  );
}

function proxy(request, response) {
  const reqUrl = new URL(request.url || '/', 'http://dummy.local');
  const target = new URL(`${reqUrl.pathname}${reqUrl.search}`, UPSTREAM.origin);
  const headers = {
    ...filteredHeaders(request.headers),
    host: UPSTREAM.host,
    'x-zarvis-owner-id': OWNER_ID,
    'x-zarvis-edge-secret': EDGE_SECRET,
    'x-forwarded-proto': 'https',
    'x-forwarded-for': '127.0.0.1',
  };

  const upstream = httpRequest(target, {
    method: request.method,
    headers,
    timeout: 15_000,
  }, (upstreamResponse) => {
    response.writeHead(upstreamResponse.statusCode || 502, filteredHeaders(upstreamResponse.headers));
    upstreamResponse.pipe(response);
  });

  upstream.on('timeout', () => upstream.destroy(new Error('upstream timeout')));
  upstream.on('error', (error) => {
    if (!response.headersSent) {
      const body = `${JSON.stringify({ error: { code: 'voice_edge_upstream_error', message: error.message } })}\n`;
      response.writeHead(502, {
        'content-type': 'application/json; charset=utf-8',
        'content-length': Buffer.byteLength(body),
        'cache-control': 'no-store',
      });
      response.end(body);
    } else {
      response.destroy(error);
    }
  });

  request.pipe(upstream);
}

const server = createServer((request, response) => {
  if (request.url === '/edge-healthz') {
    const body = `${JSON.stringify({
      status: 'ok',
      service: 'zarvis-owner-voice-edge',
      owner_github_id: OWNER_ID,
      local_only: true,
      secrets_exposed: false,
    })}\n`;
    response.writeHead(200, {
      'content-type': 'application/json; charset=utf-8',
      'content-length': Buffer.byteLength(body),
      'cache-control': 'no-store',
    });
    response.end(body);
    return;
  }
  proxy(request, response);
});

server.listen(PORT, HOST, () => {
  process.stdout.write(`zarvis-owner-voice-edge listening on http://${HOST}:${PORT}\n`);
});
