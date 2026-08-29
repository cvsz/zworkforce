const actionPort = Number(process.env.ZARVIS_ACTION_PORT ?? 8098);
const proactivePort = Number(process.env.ZARVIS_PROACTIVE_PORT ?? 8099);
const values = {
  oldOwner: process.env.OLD_ZARVIS_LOCAL_OWNER_TOKEN,
  oldActionWorker: process.env.OLD_ZARVIS_ACTION_WORKER_TOKEN,
  oldProactiveWorker: process.env.OLD_ZARVIS_PROACTIVE_WORKER_TOKEN,
  newOwner: process.env.ZARVIS_LOCAL_OWNER_TOKEN,
  newActionWorker: process.env.ZARVIS_ACTION_WORKER_TOKEN,
  newProactiveWorker: process.env.ZARVIS_PROACTIVE_WORKER_TOKEN,
};
for (const [name, value] of Object.entries(values)) {
  if (typeof value !== 'string' || Buffer.byteLength(value) < 32) throw new Error(`${name} is missing`);
}

const actionBase = `http://127.0.0.1:${actionPort}`;
const proactiveBase = `http://127.0.0.1:${proactivePort}`;
const checks = [];
async function check(name, url, expected, options) {
  const response = await fetch(url, options);
  checks.push({ name, expected_status: expected, actual_status: response.status, passed: response.status === expected });
  if (response.status !== expected) throw new Error(`${name}: expected ${expected}, got ${response.status}`);
}

await check('old owner rejected by action', `${actionBase}/v1/status`, 403, { headers: { authorization: `Bearer ${values.oldOwner}` } });
await check('new owner accepted by action', `${actionBase}/v1/status`, 200, { headers: { authorization: `Bearer ${values.newOwner}` } });
await check('old owner rejected by proactive', `${proactiveBase}/v1/status`, 403, { headers: { authorization: `Bearer ${values.oldOwner}` } });
await check('new owner accepted by proactive', `${proactiveBase}/v1/status`, 200, { headers: { authorization: `Bearer ${values.newOwner}` } });
await check('old action worker rejected', `${actionBase}/v1/internal/actions/approved`, 403, { headers: { 'x-zarvis-action-worker-token': values.oldActionWorker } });
await check('new action worker accepted', `${actionBase}/v1/internal/actions/approved`, 200, { headers: { 'x-zarvis-action-worker-token': values.newActionWorker } });
await check('old proactive worker rejected', `${proactiveBase}/v1/internal/proactive/tick`, 403, { method: 'POST', headers: { 'x-zarvis-proactive-worker-token': values.oldProactiveWorker } });
await check('new proactive worker accepted', `${proactiveBase}/v1/internal/proactive/tick`, 200, { method: 'POST', headers: { 'x-zarvis-proactive-worker-token': values.newProactiveWorker } });

process.stdout.write(`${JSON.stringify({
  schema_version: 'zarvis.local-rotation-verification.v1',
  rotated: true,
  independent_credentials: true,
  old_credentials_rejected: true,
  new_credentials_accepted: true,
  checks,
})}\n`);
