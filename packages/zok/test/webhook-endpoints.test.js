import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

process.env.NODE_ENV = 'test';
process.env.ZOK_NO_LISTEN = 'true';
process.env.ZOK_WHATSAPP_WEBHOOK_SECRET = 'dev-whatsapp-secret-1234567890';
process.env.ZOK_LINE_WEBHOOK_SECRET = 'dev-line-secret-1234567890';
process.env.ZOK_MESSENGER_WEBHOOK_SECRET = 'dev-messenger-secret-1234567890';
process.env.ZOK_TIKTOK_WEBHOOK_SECRET = 'dev-tiktok-secret-1234567890';

const testDirectory = await mkdtemp(path.join(os.tmpdir(), 'zok-webhook-endpoints-'));
const databaseFile = path.join(testDirectory, 'db.json');
await writeFile(databaseFile, JSON.stringify({
  chats: [],
  aiConfig: {},
  flowNodes: [],
  campaigns: [],
  integrations: [],
  syncLogs: [],
}), 'utf8');

process.env.ZOK_DB_FILE = databaseFile;

const { startServer } = await import('../server.js');
const server = startServer(0);
await new Promise(resolve => server.once('listening', resolve));
const baseUrl = `http://127.0.0.1:${server.address().port}`;

function computeSignature(secret, payload) {
  const body = Buffer.isBuffer(payload) ? payload : Buffer.from(
    typeof payload === 'string' ? payload : JSON.stringify(payload),
  );
  return createHmac('sha256', secret).update(body).digest('hex');
}

async function sendWebhook(provider, payload, secret) {
  const body = JSON.stringify(payload);
  const signature = computeSignature(secret, body);
  const headerName = provider === 'line' ? 'x-line-signature' : provider === 'tiktok' ? 'x-tiktok-signature' : 'x-hub-signature-256';
  const signatureValue = headerName === 'x-line-signature' ? signature : `sha256=${signature}`;

  const response = await fetch(`${baseUrl}/api/webhooks/${provider}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      [headerName]: signatureValue,
    },
    body,
  });
  return { response, status: response.status, data: await response.json() };
}

test('webhook endpoint rejects missing signature', async () => {
  const response = await fetch(`${baseUrl}/api/webhooks/whatsapp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ entry: [] }),
  });
  assert.equal(response.status, 401);
  assert.ok((await response.json()).error.includes('Missing'));
});

test('webhook endpoint rejects invalid signature', async () => {
  const response = await fetch(`${baseUrl}/api/webhooks/whatsapp`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-hub-signature-256': 'sha256=invalid',
    },
    body: JSON.stringify({ entry: [] }),
  });
  assert.equal(response.status, 401);
  assert.ok((await response.json()).error.includes('Invalid'));
});

test('webhook endpoint accepts valid WhatsApp signature and returns 202', async () => {
  const { response, data } = await sendWebhook('whatsapp', {
    entry: [
      {
        changes: [
          {
            value: {
              messages: [
                { id: 'msg-1' }
              ]
            }
          }
        ]
      }
    ]
  }, 'dev-whatsapp-secret-1234567890');
  assert.equal(response.status, 202);
  assert.equal(data.status, 'accepted');
});

test('webhook endpoint accepts valid LINE signature', async () => {
  const { response, data } = await sendWebhook('line', {
    events: [{ type: 'message', message: { id: 'msg-1' } }],
  }, 'dev-line-secret-1234567890');
  assert.equal(response.status, 202);
  assert.equal(data.status, 'accepted');
  assert.equal(data.eventType, 'message');
});

test('webhook endpoint accepts valid Messenger signature', async () => {
  const { response, data } = await sendWebhook('messenger', {
    entry: [
      {
        changes: [
          {
            value: {
              messages: [
                { mid: 'msg-1' }
              ]
            }
          }
        ]
      }
    ]
  }, 'dev-messenger-secret-1234567890');
  assert.equal(response.status, 202);
  assert.equal(data.status, 'accepted');
});

test('webhook endpoint accepts valid TikTok signature', async () => {
  const { response, data } = await sendWebhook('tiktok', {
    type: 'message',
    data: { id: 'msg-1' },
  }, 'dev-tiktok-secret-1234567890');
  assert.equal(response.status, 202);
  assert.equal(data.status, 'accepted');
});

test('webhook endpoint returns duplicate status on same idempotency key', async () => {
  const payload = {
    entry: [
      {
        changes: [
          {
            value: {
              messages: [
                { id: 'dup-msg-1' }
              ]
            }
          }
        ]
      }
    ]
  };
  const first = await sendWebhook('whatsapp', payload, 'dev-whatsapp-secret-1234567890');
  assert.equal(first.status, 202);

  const second = await sendWebhook('whatsapp', payload, 'dev-whatsapp-secret-1234567890');
  assert.equal(second.status, 200);
  assert.equal(second.data.status, 'duplicate');
});

test('consent endpoint returns 503 when consent service is unavailable', async () => {
  const response = await fetch(`${baseUrl}/api/consent/contact-1`);
  assert.equal(response.status, 503);
  const body = await response.json();
  assert.ok(body.error.includes('not available') || body.error.includes('not configured'));
});

test('consent POST endpoint returns 503 when consent service is unavailable', async () => {
  const response = await fetch(`${baseUrl}/api/consent/contact-1`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel: 'whatsapp', status: 'granted' }),
  });
  assert.equal(response.status, 503);
});

after(async () => {
  await new Promise(resolve => server.close(resolve));
  await rm(testDirectory, { recursive: true, force: true });
});
