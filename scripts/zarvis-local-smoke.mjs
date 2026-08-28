const port = Number(process.env.ZARVIS_ACTION_PORT ?? 8098);
const ownerToken = process.env.ZARVIS_LOCAL_OWNER_TOKEN;
const baseUrl = `http://127.0.0.1:${port}`;

if (typeof ownerToken !== 'string' || Buffer.byteLength(ownerToken) < 32) {
  throw new Error('ZARVIS_LOCAL_OWNER_TOKEN must contain at least 32 bytes');
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers ?? {});
  headers.set('authorization', `Bearer ${ownerToken}`);
  if (options.body) headers.set('content-type', 'application/json');
  const response = await fetch(`${baseUrl}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`${response.status} ${JSON.stringify(payload)}`);
  return payload;
}

async function waitFor(actionId, expected) {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const action = await request(`/v1/actions/${encodeURIComponent(actionId)}`);
    if (action.status === expected) return action;
    if (['failed', 'expired', 'revoked'].includes(action.status)) {
      throw new Error(`action reached ${action.status} while waiting for ${expected}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`timed out waiting for ${expected}`);
}

const health = await fetch(`${baseUrl}/healthz`).then((response) => response.json());
if (health.local_only !== true || health.secrets_exposed !== false) {
  throw new Error('health contract is not local-only and secret-safe');
}

const preview = await request('/v1/actions/preview', {
  method: 'POST',
  body: JSON.stringify({
    capability: 'sandbox.preference.set',
    key: 'smoke.local_action',
    value: 'verified',
  }),
});
if (preview.impact.external_side_effects !== false) {
  throw new Error('preview unexpectedly reports external side effects');
}

await request(`/v1/actions/${encodeURIComponent(preview.action_id)}/approve`, {
  method: 'POST',
  body: JSON.stringify({
    approval_digest: preview.approval_digest,
    approval_nonce: preview.approval_nonce,
  }),
});

const executed = await waitFor(preview.action_id, 'executed');
await request(`/v1/actions/${encodeURIComponent(preview.action_id)}/rollback`, {
  method: 'POST',
  body: JSON.stringify({
    rollback_digest: executed.rollback_digest,
    rollback_nonce: executed.rollback_nonce,
  }),
});
const rolledBack = await waitFor(preview.action_id, 'rolled_back');

process.stdout.write(`${JSON.stringify({
  schema_version: 'zarvis.local-smoke.v1',
  action_id: rolledBack.action_id,
  final_status: rolledBack.status,
  local_only: true,
  external_side_effects: false,
})}\n`);
