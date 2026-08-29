const proactivePort = Number(process.env.ZARVIS_PROACTIVE_PORT ?? 8099);
const ownerToken = process.env.ZARVIS_LOCAL_OWNER_TOKEN;
const workerToken = process.env.ZARVIS_PROACTIVE_WORKER_TOKEN;
const baseUrl = `http://127.0.0.1:${proactivePort}`;

for (const [name, value] of Object.entries({
  ZARVIS_LOCAL_OWNER_TOKEN: ownerToken,
  ZARVIS_PROACTIVE_WORKER_TOKEN: workerToken,
})) {
  if (typeof value !== 'string' || Buffer.byteLength(value) < 32) {
    throw new Error(`${name} must contain at least 32 bytes`);
  }
}

async function ownerRequest(path, options = {}) {
  const headers = new Headers(options.headers ?? {});
  headers.set('authorization', `Bearer ${ownerToken}`);
  if (options.body) headers.set('content-type', 'application/json');
  const response = await fetch(`${baseUrl}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`${response.status} ${JSON.stringify(payload)}`);
  return payload;
}

async function workerRequest(path, options = {}) {
  const headers = new Headers(options.headers ?? {});
  headers.set('x-zarvis-proactive-worker-token', workerToken);
  const response = await fetch(`${baseUrl}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`${response.status} ${JSON.stringify(payload)}`);
  return payload;
}

const health = await fetch(`${baseUrl}/healthz`).then((response) => response.json());
if (health.local_only !== true || health.autonomous_mutation !== false || health.secrets_exposed !== false) {
  throw new Error('Proactive health contract is not local-only and non-mutating');
}

await ownerRequest('/v1/policy', {
  method: 'PUT',
  body: JSON.stringify({
    timezone: 'Asia/Bangkok',
    quiet_hours_start: '00:00',
    quiet_hours_end: '00:00',
    daily_notification_budget: 5,
    default_cooldown_minutes: 60,
    confidence_threshold: 0.7,
  }),
});

const subscription = await ownerRequest('/v1/subscriptions', {
  method: 'POST',
  body: JSON.stringify({
    check: 'local.service.health',
    target: 'zarvis-action-gateway',
    interval_minutes: 1,
    notify_on: 'unhealthy',
    missed_run_policy: 'run_once',
  }),
});

const tick = await workerRequest('/v1/internal/proactive/tick', { method: 'POST' });
if (tick.evaluated !== 1 || tick.results[0]?.decision !== 'delivered') {
  throw new Error(`Unexpected proactive decision: ${JSON.stringify(tick)}`);
}

const { notifications } = await ownerRequest('/v1/notifications');
if (notifications.length !== 1) throw new Error('Expected one proactive notification');
const notification = notifications[0];
if (
  notification.delivery_state !== 'delivered'
  || notification.requires_owner_approval !== true
  || notification.proposed_action?.capability !== 'sandbox.preference.set'
) {
  throw new Error('Notification is not an explainable approval-only proposal');
}

const handoff = await ownerRequest(`/v1/notifications/${encodeURIComponent(notification.notification_id)}/handoff`, {
  method: 'POST',
});
if (
  handoff.destination !== 'zarvis-action-gateway'
  || handoff.requires_owner_approval !== true
  || handoff.executed !== false
) {
  throw new Error('Handoff crossed the autonomous-mutation boundary');
}

await ownerRequest(`/v1/notifications/${encodeURIComponent(notification.notification_id)}/feedback`, {
  method: 'POST',
  body: JSON.stringify({ rating: 'useful', note: 'local proactive smoke evidence' }),
});
await ownerRequest(`/v1/subscriptions/${encodeURIComponent(subscription.subscription_id)}/revoke`, {
  method: 'POST',
});

process.stdout.write(`${JSON.stringify({
  schema_version: 'zarvis.proactive-local-smoke.v1',
  local_only: true,
  autonomous_mutation: false,
  subscription_id: subscription.subscription_id,
  notification_id: notification.notification_id,
  delivery_state: notification.delivery_state,
  source_url: notification.source_url,
  handoff_id: handoff.handoff_id,
  handoff_requires_owner_approval: handoff.requires_owner_approval,
  handoff_executed: handoff.executed,
  final_subscription_status: 'revoked',
})}\n`);
