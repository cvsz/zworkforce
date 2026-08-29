import { execFileSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { performance } from 'node:perf_hooks';

const evidencePath = process.argv[2] ?? 'zarvis-local-release-acceptance.json';
const acceptance = JSON.parse(await readFile(evidencePath, 'utf8'));
const envFile = process.env.ZARVIS_LOCAL_ENV_FILE ?? '.env.zarvis.local';
const composeFile = process.env.ZARVIS_LOCAL_COMPOSE_FILE ?? 'compose.zarvis-local.yml';
const actionPort = Number(process.env.ZARVIS_ACTION_PORT ?? 8098);
const proactivePort = Number(process.env.ZARVIS_PROACTIVE_PORT ?? 8099);
const ownerToken = process.env.ZARVIS_LOCAL_OWNER_TOKEN;
if (typeof ownerToken !== 'string' || Buffer.byteLength(ownerToken) < 32) throw new Error('Owner token is missing');

function compose(...args) {
  return execFileSync('docker', ['compose', '--env-file', envFile, '-f', composeFile, ...args], {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  }).trim();
}

async function waitForHealth(url, timeoutMs = 60_000) {
  const started = performance.now();
  while (performance.now() - started < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return performance.now() - started;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Health did not recover: ${url}`);
}

async function ownerGet(base, path) {
  const response = await fetch(`${base}${path}`, { headers: { authorization: `Bearer ${ownerToken}` } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`${response.status} ${path} ${JSON.stringify(payload)}`);
  return payload;
}

compose('stop', 'zarvis-action-worker', 'zarvis-proactive-worker');
const started = performance.now();
compose('restart', 'zarvis-action-gateway', 'zarvis-proactive');
const [actionRecovery, proactiveRecovery] = await Promise.all([
  waitForHealth(`http://127.0.0.1:${actionPort}/healthz`),
  waitForHealth(`http://127.0.0.1:${proactivePort}/healthz`),
]);

function assertSafeId(id) {
  if (typeof id !== 'string' || !/^[a-zA-Z0-9_.\-]+$/.test(id)) throw new Error('Invalid ID');
  return id;
}

const actionId = assertSafeId(acceptance.action.action_id);
const action = await ownerGet(`http://127.0.0.1:${actionPort}`, `/v1/actions/${encodeURIComponent(actionId)}`);
const { subscriptions } = await ownerGet(`http://127.0.0.1:${proactivePort}`, '/v1/subscriptions');
const subscription = subscriptions.find((item) => item.subscription_id === acceptance.proactive.subscription_id);
const { notifications } = await ownerGet(`http://127.0.0.1:${proactivePort}`, '/v1/notifications');
const notification = notifications.find((item) => item.notification_id === acceptance.proactive.notification_id);
if (action.status !== 'rolled_back' || subscription?.status !== 'revoked' || notification?.handoff?.executed !== false) {
  throw new Error('Durable state did not survive service restart');
}

compose('start', 'zarvis-action-worker', 'zarvis-proactive-worker');
const totalMs = performance.now() - started;
if (Math.max(actionRecovery, proactiveRecovery) > 60_000) throw new Error('Restart recovery SLO exceeded');

process.stdout.write(`${JSON.stringify({
  schema_version: 'zarvis.local-restart-drill.v1',
  workers_interrupted: true,
  services_restarted: ['zarvis-action-gateway', 'zarvis-proactive'],
  durable_state_preserved: true,
  workers_resumed: true,
  action_recovery_ms: Number(actionRecovery.toFixed(2)),
  proactive_recovery_ms: Number(proactiveRecovery.toFixed(2)),
  total_drill_ms: Number(totalMs.toFixed(2)),
  recovery_slo_ms: 60000,
})}\n`);
