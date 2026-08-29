const actionPort = Number(process.env.ZARVIS_ACTION_PORT ?? 8098);
const proactivePort = Number(process.env.ZARVIS_PROACTIVE_PORT ?? 8099);
const ownerToken = process.env.ZARVIS_LOCAL_OWNER_TOKEN;
const actionWorkerToken = process.env.ZARVIS_ACTION_WORKER_TOKEN;
const proactiveWorkerToken = process.env.ZARVIS_PROACTIVE_WORKER_TOKEN;
const actionBase = `http://127.0.0.1:${actionPort}`;
const proactiveBase = `http://127.0.0.1:${proactivePort}`;

if ([ownerToken, actionWorkerToken, proactiveWorkerToken].some((value) => typeof value !== 'string' || Buffer.byteLength(value) < 32)) {
  throw new Error('Release red-team secrets are missing');
}

const checks = [];
async function expectStatus(name, url, expected, options = {}) {
  const response = await fetch(url, options);
  const body = await response.text();
  checks.push({ name, expected_status: expected, actual_status: response.status, passed: response.status === expected });
  if (response.status !== expected) throw new Error(`${name}: expected ${expected}, got ${response.status}: ${body}`);
  for (const secret of [ownerToken, actionWorkerToken, proactiveWorkerToken]) {
    if (body.includes(secret)) throw new Error(`${name}: response leaked a configured secret`);
  }
  return body;
}

const wrongOwner = 'x'.repeat(64);
const wrongWorker = 'y'.repeat(64);
await expectStatus('action wrong owner denied', `${actionBase}/v1/status`, 403, { headers: { authorization: `Bearer ${wrongOwner}` } });
await expectStatus('proactive wrong owner denied', `${proactiveBase}/v1/status`, 403, { headers: { authorization: `Bearer ${wrongOwner}` } });
await expectStatus('action wrong worker denied', `${actionBase}/v1/internal/actions/approved`, 403, { headers: { 'x-zarvis-action-worker-token': wrongWorker } });
await expectStatus('proactive wrong worker denied', `${proactiveBase}/v1/internal/proactive/tick`, 403, { method: 'POST', headers: { 'x-zarvis-proactive-worker-token': wrongWorker } });

await expectStatus('unknown action capability denied', `${actionBase}/v1/actions/preview`, 403, {
  method: 'POST',
  headers: { authorization: `Bearer ${ownerToken}`, 'content-type': 'application/json' },
  body: JSON.stringify({ capability: 'shell.execute', key: 'release.test', value: 'id' }),
});
await expectStatus('untrusted action request denied', `${actionBase}/v1/actions/preview`, 403, {
  method: 'POST',
  headers: { authorization: `Bearer ${ownerToken}`, 'content-type': 'application/json' },
  body: JSON.stringify({ capability: 'sandbox.preference.set', key: 'release.test', value: 'x', untrusted_content: true }),
});
await expectStatus('path-like preference key denied', `${actionBase}/v1/actions/preview`, 400, {
  method: 'POST',
  headers: { authorization: `Bearer ${ownerToken}`, 'content-type': 'application/json' },
  body: JSON.stringify({ capability: 'sandbox.preference.set', key: '../../etc/passwd', value: 'x' }),
});
await expectStatus('oversized action payload denied', `${actionBase}/v1/actions/preview`, 413, {
  method: 'POST',
  headers: { authorization: `Bearer ${ownerToken}`, 'content-type': 'application/json' },
  body: JSON.stringify({ capability: 'sandbox.preference.set', key: 'release.large', value: 'x'.repeat(70_000) }),
});

await expectStatus('unknown proactive check denied', `${proactiveBase}/v1/subscriptions`, 403, {
  method: 'POST',
  headers: { authorization: `Bearer ${ownerToken}`, 'content-type': 'application/json' },
  body: JSON.stringify({ check: 'http.fetch', target: 'http://169.254.169.254/latest/meta-data', interval_minutes: 1 }),
});
await expectStatus('unknown proactive target denied', `${proactiveBase}/v1/subscriptions`, 403, {
  method: 'POST',
  headers: { authorization: `Bearer ${ownerToken}`, 'content-type': 'application/json' },
  body: JSON.stringify({ check: 'local.service.health', target: 'metadata-service', interval_minutes: 1 }),
});
await expectStatus('untrusted proactive schedule denied', `${proactiveBase}/v1/subscriptions`, 403, {
  method: 'POST',
  headers: { authorization: `Bearer ${ownerToken}`, 'content-type': 'application/json' },
  body: JSON.stringify({ check: 'local.service.health', target: 'zarvis-action-gateway', interval_minutes: 1, untrusted_content: true }),
});
await expectStatus('registration route absent', `${actionBase}/v1/register`, 404, { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' });
await expectStatus('proactive registration route absent', `${proactiveBase}/v1/register`, 404, { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' });

const actionHealth = await expectStatus('action health secret safe', `${actionBase}/healthz`, 200);
const proactiveHealth = await expectStatus('proactive health secret safe', `${proactiveBase}/healthz`, 200);
if (!JSON.parse(actionHealth).local_only || JSON.parse(proactiveHealth).autonomous_mutation !== false) {
  throw new Error('Health security invariants failed');
}

const actionListBefore = JSON.parse(await expectStatus('action list baseline', `${actionBase}/v1/actions`, 200, {
  headers: { authorization: `Bearer ${ownerToken}` },
})).actions.length;
const notificationPayload = JSON.parse(await expectStatus('proactive notification list', `${proactiveBase}/v1/notifications`, 200, {
  headers: { authorization: `Bearer ${ownerToken}` },
}));
const actionable = notificationPayload.notifications.find((item) => item.proposed_action);
if (!actionable) throw new Error('Red-team requires one actionable proactive notification');
const handoffBody = JSON.parse(await expectStatus('handoff creation or replay allowed', `${proactiveBase}/v1/notifications/${encodeURIComponent(actionable.notification_id)}/handoff`, 200, {
  method: 'POST',
  headers: { authorization: `Bearer ${ownerToken}` },
}));
if (handoffBody.requires_owner_approval !== true || handoffBody.executed !== false) {
  throw new Error('Proactive handoff crossed the owner-approval boundary');
}
const actionListAfter = JSON.parse(await expectStatus('handoff did not create action', `${actionBase}/v1/actions`, 200, {
  headers: { authorization: `Bearer ${ownerToken}` },
})).actions.length;
const handoffIsolated = actionListAfter === actionListBefore;
checks.push({
  name: 'proactive handoff cannot autonomously mutate action state',
  expected_status: 'unchanged_action_count',
  actual_status: handoffIsolated ? 'unchanged_action_count' : 'changed_action_count',
  passed: handoffIsolated,
});
if (!handoffIsolated) throw new Error('Proactive handoff autonomously created an action');

process.stdout.write(`${JSON.stringify({
  schema_version: 'zarvis.local-red-team.v1',
  local_only: true,
  checks_run: checks.length,
  checks_passed: checks.filter((item) => item.passed).length,
  all_passed: checks.every((item) => item.passed),
  secret_leaks_detected: 0,
  autonomous_mutations_detected: 0,
  checks,
})}\n`);
