import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { ZarvisProactiveRuntime, ZARVIS_OWNER_USER_ID } from '../runtime.mjs';
import { FileProactiveStore, MemoryProactiveStore } from '../store.mjs';
import { createProactiveServer } from '../server.mjs';

function adapter({ targets = ['one'], signals = {} } = {}) {
  return {
    allowedTargets: targets,
    calls: [],
    async evaluate(subscription, checkedAt) {
      this.calls.push({ subscription_id: subscription.subscription_id, checked_at: checkedAt });
      const value = signals[subscription.target] ?? { status: 'healthy', confidence: 1 };
      return {
        signal_key: `health:${subscription.target}`,
        status: value.status,
        severity: value.status === 'healthy' ? 'info' : 'high',
        confidence: value.confidence,
        summary: `${subscription.target} is ${value.status}`,
        source_url: `http://127.0.0.1/${subscription.target}/healthz`,
        evidence: { checked_at: checkedAt },
        proposed_action: value.status === 'healthy' ? null : {
          capability: 'sandbox.preference.set',
          key: 'assistant.proactive_attention',
          value: `unhealthy:${subscription.target}`,
        },
      };
    },
  };
}

function fixture({
  store = new MemoryProactiveStore(),
  localAdapter = adapter(),
  initialNow = '2026-08-06T03:00:00.000Z',
} = {}) {
  let now = initialNow;
  let sequence = 0;
  const runtime = new ZarvisProactiveRuntime({
    store,
    adapter: localAdapter,
    now: () => now,
    idFactory: () => `proactive-${++sequence}`,
  });
  return { runtime, store, adapter: localAdapter, setNow(value) { now = value; } };
}

async function subscribe(runtime, overrides = {}) {
  return runtime.createSubscription({
    check: 'local.service.health',
    target: 'one',
    interval_minutes: 1,
    notify_on: 'unhealthy',
    missed_run_policy: 'run_once',
    ...overrides,
  });
}

async function disableQuietHours(runtime, overrides = {}) {
  return runtime.updatePolicy({
    timezone: 'Asia/Bangkok',
    quiet_hours_start: '00:00',
    quiet_hours_end: '00:00',
    daily_notification_budget: 5,
    default_cooldown_minutes: 60,
    confidence_threshold: 0.7,
    ...overrides,
  });
}

test('policy validates IANA timezone, quiet hours, budgets, cooldown, and confidence', async () => {
  const { runtime } = fixture();
  const policy = await disableQuietHours(runtime, { daily_notification_budget: 3, confidence_threshold: 0.8 });
  assert.equal(policy.owner_user_id, ZARVIS_OWNER_USER_ID);
  assert.equal(policy.daily_notification_budget, 3);
  await assert.rejects(runtime.updatePolicy({ timezone: 'Not/AZone' }), (error) => error.code === 'invalid_timezone');
  await assert.rejects(runtime.updatePolicy({ quiet_hours_start: '25:00' }), (error) => error.code === 'invalid_quiet_hours');
});

test('subscription is owner-bound, idempotent, allowlisted, and revocable', async () => {
  const { runtime } = fixture();
  const created = await subscribe(runtime);
  assert.equal(created.owner_user_id, ZARVIS_OWNER_USER_ID);
  assert.equal(created.replayed, false);
  assert.equal((await subscribe(runtime)).replayed, true);
  await assert.rejects(subscribe(runtime, { check: 'shell.execute' }), (error) => error.code === 'check_denied');
  await assert.rejects(subscribe(runtime, { untrusted_content: true }), (error) => error.code === 'confused_deputy_denied');
  assert.equal((await runtime.revokeSubscription(created.subscription_id)).status, 'revoked');
});

test('healthy read-only evaluation is audited without creating a notification', async () => {
  const { runtime, adapter: localAdapter } = fixture();
  await disableQuietHours(runtime);
  await subscribe(runtime);
  const tick = await runtime.tick();
  assert.equal(tick.evaluated, 1);
  assert.equal(tick.results[0].decision, 'not_triggered');
  assert.equal((await runtime.listNotifications()).length, 0);
  assert.equal(localAdapter.calls.length, 1);
});

test('unhealthy signal creates explainable notification and approval-only handoff', async () => {
  const localAdapter = adapter({ signals: { one: { status: 'unhealthy', confidence: 1 } } });
  const { runtime } = fixture({ localAdapter });
  await disableQuietHours(runtime);
  await subscribe(runtime);
  await runtime.tick();
  const [notification] = await runtime.listNotifications();
  assert.equal(notification.delivery_state, 'delivered');
  assert.match(notification.explanation, /Read-only local\.service\.health/);
  assert.equal(notification.requires_owner_approval, true);
  const handoff = await runtime.createActionHandoff(notification.notification_id);
  assert.equal(handoff.destination, 'zarvis-action-gateway');
  assert.equal(handoff.requires_owner_approval, true);
  assert.equal(handoff.executed, false);
  assert.equal(handoff.request.capability, 'sandbox.preference.set');
  assert.equal((await runtime.createActionHandoff(notification.notification_id)).replayed, true);
});

test('quiet hours suppress notification server-side', async () => {
  const localAdapter = adapter({ signals: { one: { status: 'unhealthy', confidence: 1 } } });
  const { runtime } = fixture({ localAdapter, initialNow: '2026-08-06T16:00:00.000Z' });
  await subscribe(runtime);
  await runtime.tick();
  assert.equal((await runtime.listNotifications())[0].delivery_state, 'suppressed_quiet_hours');
});

test('daily budget and cooldown prevent notification storms', async () => {
  const localAdapter = adapter({
    targets: ['one', 'two'],
    signals: { one: { status: 'unhealthy', confidence: 1 }, two: { status: 'unhealthy', confidence: 1 } },
  });
  const first = fixture({ localAdapter });
  await disableQuietHours(first.runtime, { daily_notification_budget: 1 });
  await subscribe(first.runtime, { target: 'one' });
  await subscribe(first.runtime, { target: 'two' });
  await first.runtime.tick();
  assert.deepEqual((await first.runtime.listNotifications()).map((item) => item.delivery_state).sort(), ['delivered', 'suppressed_budget']);

  const second = fixture({ localAdapter: adapter({ signals: { one: { status: 'unhealthy', confidence: 1 } } }) });
  await disableQuietHours(second.runtime, { daily_notification_budget: 5, default_cooldown_minutes: 60 });
  await subscribe(second.runtime, { notify_on: 'always' });
  await second.runtime.tick();
  second.setNow('2026-08-06T03:01:00.000Z');
  await second.runtime.tick();
  assert.deepEqual((await second.runtime.listNotifications()).map((item) => item.delivery_state).sort(), ['delivered', 'suppressed_cooldown']);
});

test('confidence threshold suppresses low-confidence signals', async () => {
  const { runtime } = fixture({ localAdapter: adapter({ signals: { one: { status: 'unhealthy', confidence: 0.4 } } }) });
  await disableQuietHours(runtime, { confidence_threshold: 0.7 });
  await subscribe(runtime);
  await runtime.tick();
  assert.equal((await runtime.listNotifications())[0].delivery_state, 'suppressed_confidence');
});

test('missed-run skip avoids catch-up while run_once evaluates once', async () => {
  const localAdapter = adapter({ targets: ['one', 'two'] });
  const { runtime, setNow } = fixture({ localAdapter });
  await disableQuietHours(runtime);
  await subscribe(runtime, { target: 'one', missed_run_policy: 'skip' });
  await subscribe(runtime, { target: 'two', missed_run_policy: 'run_once' });
  setNow('2026-08-06T03:03:00.000Z');
  const tick = await runtime.tick();
  assert.deepEqual(tick.results.map((item) => item.decision).sort(), ['missed_run_skipped', 'not_triggered']);
  assert.equal(localAdapter.calls.length, 1);
});

test('file journal recovers policy, schedule, notification, feedback, and handoff after restart', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'zarvis-proactive-'));
  try {
    const first = fixture({
      store: new FileProactiveStore({ dataDir: directory }),
      localAdapter: adapter({ signals: { one: { status: 'unhealthy', confidence: 1 } } }),
    });
    await disableQuietHours(first.runtime);
    await subscribe(first.runtime);
    await first.runtime.tick();
    const [notification] = await first.runtime.listNotifications();
    await first.runtime.recordFeedback(notification.notification_id, { rating: 'useful' });
    await first.runtime.createActionHandoff(notification.notification_id);

    const second = fixture({ store: new FileProactiveStore({ dataDir: directory }), localAdapter: adapter() });
    assert.equal((await second.runtime.listSubscriptions()).length, 1);
    const [recovered] = await second.runtime.listNotifications();
    assert.equal(recovered.feedback.rating, 'useful');
    assert.equal(recovered.handoff.executed, false);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test('HTTP service separates owner policy from worker tick and never exposes autonomous mutation', async () => {
  assert.throws(() => createProactiveServer(), /ZARVIS_LOCAL_OWNER_TOKEN/);
  const ownerToken = 'o'.repeat(32);
  const workerToken = 'p'.repeat(32);
  const { runtime } = fixture({ localAdapter: adapter({ signals: { one: { status: 'unhealthy', confidence: 1 } } }) });
  await disableQuietHours(runtime);
  const server = createProactiveServer({ ownerToken, workerToken, runtime });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  const base = `http://127.0.0.1:${address.port}`;
  try {
    const health = await fetch(`${base}/healthz`).then((response) => response.json());
    assert.equal(health.autonomous_mutation, false);
    assert.equal((await fetch(`${base}/v1/subscriptions`)).status, 403);

    const created = await fetch(`${base}/v1/subscriptions`, {
      method: 'POST',
      headers: { authorization: `Bearer ${ownerToken}`, 'content-type': 'application/json' },
      body: JSON.stringify({ check: 'local.service.health', target: 'one', interval_minutes: 1, notify_on: 'unhealthy', missed_run_policy: 'run_once' }),
    });
    assert.equal(created.status, 201);
    assert.equal((await fetch(`${base}/v1/internal/proactive/tick`, { method: 'POST' })).status, 403);
    const tick = await fetch(`${base}/v1/internal/proactive/tick`, {
      method: 'POST',
      headers: { 'x-zarvis-proactive-worker-token': workerToken },
    });
    assert.equal(tick.status, 200);
    const notifications = await fetch(`${base}/v1/notifications`, { headers: { authorization: `Bearer ${ownerToken}` } }).then((response) => response.json());
    assert.equal(notifications.notifications.length, 1);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
