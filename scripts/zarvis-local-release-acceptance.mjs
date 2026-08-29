import { performance } from 'node:perf_hooks';

const actionPort = Number(process.env.ZARVIS_ACTION_PORT ?? 8098);
const proactivePort = Number(process.env.ZARVIS_PROACTIVE_PORT ?? 8099);
const ownerToken = process.env.ZARVIS_LOCAL_OWNER_TOKEN;
const actionWorkerToken = process.env.ZARVIS_ACTION_WORKER_TOKEN;
const proactiveWorkerToken = process.env.ZARVIS_PROACTIVE_WORKER_TOKEN;
const actionBase = `http://127.0.0.1:${actionPort}`;
const proactiveBase = `http://127.0.0.1:${proactivePort}`;

for (const [name, value] of Object.entries({ ownerToken, actionWorkerToken, proactiveWorkerToken })) {
  if (typeof value !== 'string' || Buffer.byteLength(value) < 32) throw new Error(`${name} is missing`);
}

async function request(base, path, { auth = 'owner', ...options } = {}) {
  const headers = new Headers(options.headers ?? {});
  if (auth === 'owner') headers.set('authorization', `Bearer ${ownerToken}`);
  if (auth === 'action-worker') headers.set('x-zarvis-action-worker-token', actionWorkerToken);
  if (auth === 'proactive-worker') headers.set('x-zarvis-proactive-worker-token', proactiveWorkerToken);
  if (options.body) headers.set('content-type', 'application/json');
  const response = await fetch(`${base}${path}`, { ...options, headers });
  const text = await response.text();
  let payload = {};
  try { payload = text ? JSON.parse(text) : {}; } catch { payload = { text }; }
  if (!response.ok) throw new Error(`${response.status} ${path} ${JSON.stringify(payload)}`);
  return payload;
}

function percentile(samples, fraction) {
  const ordered = [...samples].sort((a, b) => a - b);
  return ordered[Math.min(ordered.length - 1, Math.ceil(ordered.length * fraction) - 1)];
}

async function measure(url, options, count = 120, concurrency = 12) {
  const samples = [];
  let errors = 0;
  let cursor = 0;
  async function worker() {
    while (cursor < count) {
      cursor += 1;
      const started = performance.now();
      try {
        const response = await fetch(url, options);
        if (!response.ok) errors += 1;
      } catch {
        errors += 1;
      } finally {
        samples.push(performance.now() - started);
      }
    }
  }
  await Promise.all(Array.from({ length: concurrency }, () => worker()));
  return {
    requests: count,
    errors,
    p50_ms: Number(percentile(samples, 0.5).toFixed(2)),
    p95_ms: Number(percentile(samples, 0.95).toFixed(2)),
    max_ms: Number(Math.max(...samples).toFixed(2)),
  };
}

const actionHealth = await request(actionBase, '/healthz', { auth: 'none' });
const proactiveHealth = await request(proactiveBase, '/healthz', { auth: 'none' });
if (!actionHealth.local_only || !proactiveHealth.local_only || proactiveHealth.autonomous_mutation !== false) {
  throw new Error('Local health invariants failed');
}

const releaseValue = `accepted-${process.env.GITHUB_RUN_ID ?? 'local'}`;
const preview = await request(actionBase, '/v1/actions/preview', {
  method: 'POST',
  body: JSON.stringify({
    capability: 'sandbox.preference.set',
    key: 'release.acceptance',
    value: releaseValue,
  }),
});
const approved = await request(actionBase, `/v1/actions/${encodeURIComponent(preview.action_id)}/approve`, {
  method: 'POST',
  body: JSON.stringify({ approval_digest: preview.approval_digest, approval_nonce: preview.approval_nonce }),
});
if (approved.status !== 'approved') throw new Error('Action approval failed');
const executed = await request(actionBase, `/v1/internal/actions/${encodeURIComponent(preview.action_id)}/execute`, {
  method: 'POST',
  auth: 'action-worker',
});
const rolledBack = await request(actionBase, `/v1/actions/${encodeURIComponent(preview.action_id)}/rollback`, {
  method: 'POST',
  body: JSON.stringify({ rollback_digest: executed.rollback_digest, rollback_nonce: executed.rollback_nonce }),
});
if (rolledBack.status !== 'rolled_back') throw new Error('Action rollback failed');

const pending = await request(actionBase, '/v1/actions/preview', {
  method: 'POST',
  body: JSON.stringify({ capability: 'sandbox.preference.set', key: 'release.emergency', value: 'must-not-run' }),
});
const emergency = await request(actionBase, '/v1/emergency-stop', {
  method: 'POST',
  body: JSON.stringify({ reason: 'release_acceptance' }),
});
const revoked = await request(actionBase, `/v1/actions/${encodeURIComponent(pending.action_id)}`);
if (!emergency.emergency_stop || revoked.status !== 'revoked') throw new Error('Emergency revocation failed');
await request(actionBase, '/v1/emergency-resume', {
  method: 'POST',
  body: JSON.stringify({ confirmation: 'RESUME_LOCAL_ACTIONS' }),
});

await request(proactiveBase, '/v1/policy', {
  method: 'PUT',
  body: JSON.stringify({
    timezone: 'Asia/Bangkok',
    quiet_hours_start: '00:00',
    quiet_hours_end: '00:00',
    daily_notification_budget: 20,
    default_cooldown_minutes: 1,
    confidence_threshold: 0.7,
  }),
});

const existingSubscriptions = await request(proactiveBase, '/v1/subscriptions');
const staleAcceptanceSubscriptions = existingSubscriptions.subscriptions.filter(
  (item) => item.status === 'active'
    && item.check === 'local.service.health'
    && item.target === 'zarvis-action-gateway',
);
for (const stale of staleAcceptanceSubscriptions) {
  await request(
    proactiveBase,
    `/v1/subscriptions/${encodeURIComponent(stale.subscription_id)}/revoke`,
    { method: 'POST' },
  );
}

const subscription = await request(proactiveBase, '/v1/subscriptions', {
  method: 'POST',
  body: JSON.stringify({
    check: 'local.service.health',
    target: 'zarvis-action-gateway',
    interval_minutes: 1,
    notify_on: 'unhealthy',
    cooldown_minutes: 1,
    missed_run_policy: 'run_once',
  }),
});
if (subscription.replayed === true) {
  throw new Error(`Release acceptance unexpectedly replayed subscription ${subscription.subscription_id}`);
}

const tick = await request(proactiveBase, '/v1/internal/proactive/tick', {
  method: 'POST',
  auth: 'proactive-worker',
});
const delivery = tick.results.find((item) => item.subscription_id === subscription.subscription_id);
if (delivery?.decision !== 'delivered') {
  throw new Error(`Proactive delivery decision failed: ${JSON.stringify({
    subscription_id: subscription.subscription_id,
    evaluated: tick.evaluated,
    matching_result: delivery ?? null,
    results: tick.results.map((item) => ({
      subscription_id: item.subscription_id,
      decision: item.decision,
      notification_id: item.notification_id,
    })),
  })}`);
}

const notificationList = await request(proactiveBase, '/v1/notifications');
const notification = notificationList.notifications.find(
  (item) => item.notification_id === delivery.notification_id
    && item.subscription_id === subscription.subscription_id,
);
if (!notification?.requires_owner_approval || !notification.proposed_action) throw new Error('Proactive action proposal missing');
const handoff = await request(proactiveBase, `/v1/notifications/${encodeURIComponent(notification.notification_id)}/handoff`, { method: 'POST' });
if (handoff.executed !== false || handoff.requires_owner_approval !== true) throw new Error('Proactive handoff crossed execution boundary');
await request(proactiveBase, `/v1/notifications/${encodeURIComponent(notification.notification_id)}/feedback`, {
  method: 'POST',
  body: JSON.stringify({ rating: 'useful', note: 'automated local release acceptance' }),
});
await request(proactiveBase, `/v1/subscriptions/${encodeURIComponent(subscription.subscription_id)}/revoke`, { method: 'POST' });

const [actionHealthLoad, proactiveHealthLoad, actionStatusLoad, proactiveStatusLoad] = await Promise.all([
  measure(`${actionBase}/healthz`, {}, 120, 12),
  measure(`${proactiveBase}/healthz`, {}, 120, 12),
  measure(`${actionBase}/v1/status`, { headers: { authorization: `Bearer ${ownerToken}` } }, 80, 8),
  measure(`${proactiveBase}/v1/status`, { headers: { authorization: `Bearer ${ownerToken}` } }, 80, 8),
]);
for (const result of [actionHealthLoad, proactiveHealthLoad, actionStatusLoad, proactiveStatusLoad]) {
  if (result.errors !== 0 || result.p95_ms > 750) throw new Error(`Local SLO failed: ${JSON.stringify(result)}`);
}

process.stdout.write(`${JSON.stringify({
  schema_version: 'zarvis.local-release-acceptance.v1',
  owner_github_id: '4076926',
  local_only: true,
  automated_acceptance: 'passed',
  action: {
    action_id: preview.action_id,
    final_status: rolledBack.status,
    emergency_action_id: pending.action_id,
    emergency_final_status: revoked.status,
    emergency_revoked_count: emergency.revoked,
  },
  proactive: {
    subscription_id: subscription.subscription_id,
    final_subscription_status: 'revoked',
    notification_id: notification.notification_id,
    delivery_state: notification.delivery_state,
    handoff_id: handoff.handoff_id,
    handoff_requires_owner_approval: handoff.requires_owner_approval,
    handoff_executed: handoff.executed,
    stale_acceptance_subscriptions_revoked: staleAcceptanceSubscriptions.length,
  },
  slo: {
    threshold_p95_ms: 750,
    action_health: actionHealthLoad,
    proactive_health: proactiveHealthLoad,
    action_status: actionStatusLoad,
    proactive_status: proactiveStatusLoad,
  },
})}\n`);
