import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { createReverseProxyConfig } from '../server/edge/reverse-proxy.js';
import express from 'express';

test('reverse proxy config sets trust proxy in production mode', () => {
  const app = express();
  const config = createReverseProxyConfig({ isProduction: true });
  config.apply(app);
  assert.ok(app.get('trust proxy'));
});

test('reverse proxy config sets trust proxy in development mode', () => {
  const app = express();
  const config = createReverseProxyConfig({ isProduction: false });
  config.apply(app);
  assert.ok(app.get('trust proxy'));
});

test('reverse proxy middleware passes valid headers through', async () => {
  const app = express();
  const config = createReverseProxyConfig({ isProduction: true });
  config.apply(app);
  app.use(config.middleware);
  app.get('/test', (req, res) => res.json({ secure: req.secure, proto: req.get('x-forwarded-proto') }));

  const server = app.listen(0);
  await new Promise(resolve => server.once('listening', resolve));
  try {
    const port = server.address().port;

    const response = await fetch(`http://127.0.0.1:${port}/test`, {
      headers: {
        'x-forwarded-proto': 'https',
        'x-forwarded-host': 'example.com',
        'x-forwarded-port': '443',
        'x-forwarded-for': '203.0.113.1, 198.51.100.1',
      },
    });

    assert.equal(response.status, 200);
    const body = await response.json();
    assert.equal(body.proto, 'https');
    assert.equal(body.secure, true);
  } finally {
    server.close();
  }
});

test('reverse proxy middleware rejects invalid x-forwarded-proto', async () => {
  const app = express();
  const config = createReverseProxyConfig({ isProduction: true });
  config.apply(app);
  app.use(config.middleware);
  app.get('/test', (req, res) => res.json({ ok: true }));

  const server = app.listen(0);
  await new Promise(resolve => server.once('listening', resolve));
  try {
    const port = server.address().port;

    const response = await fetch(`http://127.0.0.1:${port}/test`, {
      headers: { 'x-forwarded-proto': 'invalid' },
    });

    assert.equal(response.status, 400);
    const body = await response.json();
    assert.equal(body.error, 'Invalid proxy headers');
  } finally {
    server.close();
  }
});

test('reverse proxy middleware rejects invalid x-forwarded-host', async () => {
  const app = express();
  const config = createReverseProxyConfig({ isProduction: true });
  config.apply(app);
  app.use(config.middleware);
  app.get('/test', (req, res) => res.json({ ok: true }));

  const server = app.listen(0);
  await new Promise(resolve => server.once('listening', resolve));
  try {
    const port = server.address().port;

    const response = await fetch(`http://127.0.0.1:${port}/test`, {
      headers: { 'x-forwarded-host': 'not a valid host!' },
    });

    assert.equal(response.status, 400);
    const body = await response.json();
    assert.equal(body.error, 'Invalid proxy headers');
  } finally {
    server.close();
  }
});

test('reverse proxy middleware accepts valid websocket upgrade headers', async () => {
  const app = express();
  const config = createReverseProxyConfig({ isProduction: true });
  config.apply(app);
  app.use(config.middleware);
  app.get('/ws', (req, res) => res.json({ upgrade: req.get('upgrade') }));

  const server = app.listen(0);
  await new Promise(resolve => server.once('listening', resolve));
  try {
    const port = server.address().port;

    const response = await new Promise((resolve, reject) => {
      const req = http.request({
        hostname: '127.0.0.1',
        port,
        path: '/ws',
        method: 'GET',
        headers: { upgrade: 'websocket' },
      }, (res) => {
        let data = '';
        res.on('data', chunk => { data += chunk; });
        res.on('end', () => resolve({ status: res.statusCode, body: JSON.parse(data) }));
      });
      req.on('error', reject);
      req.end();
    });

    assert.equal(response.status, 200);
    assert.equal(response.body.upgrade, 'websocket');
  } finally {
    server.close();
  }
});

test('reverse proxy config validates forwarded-for IPs', async () => {
  const app = express();
  const config = createReverseProxyConfig({ isProduction: true });
  config.apply(app);
  app.use(config.middleware);
  app.get('/test', (req, res) => res.json({ ok: true }));

  const server = app.listen(0);
  await new Promise(resolve => server.once('listening', resolve));
  try {
    const port = server.address().port;

    const response = await fetch(`http://127.0.0.1:${port}/test`, {
      headers: { 'x-forwarded-for': 'not-an-ip' },
    });

    assert.equal(response.status, 400);
    const body = await response.json();
    assert.equal(body.error, 'Invalid proxy headers');
  } finally {
    server.close();
  }
});
