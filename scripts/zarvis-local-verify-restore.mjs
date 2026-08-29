import { readFile } from 'node:fs/promises';

const evidencePath = process.argv[2] ?? 'zarvis-local-release-acceptance.json';
const evidence = JSON.parse(await readFile(evidencePath, 'utf8'));
const actionPort = Number(process.env.ZARVIS_ACTION_PORT ?? 8098);
const proactivePort = Number(process.env.ZARVIS_PROACTIVE_PORT ?? 8099);
const ownerToken = process.env.ZARVIS_LOCAL_OWNER_TOKEN;
if (typeof ownerToken !== 'string' || Buffer.byteLength(ownerToken) < 32) throw new Error('Owner token is missing');

function assertSafeId(id) {
  if (typeof id !== 'string' || !/^[a-zA-Z0-9_.\-]+$/.test(id)) throw new Error('Invalid ID');
  return id;
}

async function ownerGet(base, path) {
  const response = await fetch(`${base}${path}`, { headers: { authorization: `Bearer ${ownerToken}` } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`${response.status} ${path} ${JSON.stringify(payload)}`);
  return payload;
}

const actionBase = `http://127.0.0.1:${actionPort}`;
const proactiveBase = `http://127.0.0.1:${proactivePort}`;
const actionId = assertSafeId(evidence.action.action_id);
const emergencyActionId = assertSafeId(evidence.action.emergency_action_id);
const action = await ownerGet(actionBase, `/v1/actions/${encodeURIComponent(actionId)}`);
const emergencyAction = await ownerGet(actionBase, `/v1/actions/${encodeURIComponent(emergencyActionId)}`);
const { subscriptions } = await ownerGet(proactiveBase, '/v1/subscriptions');
const subscription = subscriptions.find((item) => item.subscription_id === evidence.proactive.subscription_id);
const { notifications } = await ownerGet(proactiveBase, '/v1/notifications');
const notification = notifications.find((item) => item.notification_id === evidence.proactive.notification_id);

if (action.status !== 'rolled_back') throw new Error('Restored action rollback state is incorrect');
if (emergencyAction.status !== 'revoked') throw new Error('Restored emergency action state is incorrect');
if (subscription?.status !== 'revoked') throw new Error('Restored proactive subscription state is incorrect');
if (notification?.feedback?.rating !== 'useful') throw new Error('Restored feedback is missing');
if (notification?.handoff?.executed !== false || notification?.handoff?.requires_owner_approval !== true) {
  throw new Error('Restored handoff crossed the approval boundary');
}

process.stdout.write(`${JSON.stringify({
  schema_version: 'zarvis.local-restore-verification.v1',
  restored: true,
  local_only: true,
  action_id: action.action_id,
  action_status: action.status,
  emergency_action_status: emergencyAction.status,
  subscription_status: subscription.status,
  notification_id: notification.notification_id,
  feedback_rating: notification.feedback.rating,
  handoff_executed: notification.handoff.executed,
})}\n`);
