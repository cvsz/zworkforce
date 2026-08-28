import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { FileActionStore, MemoryActionStore } from '../store.mjs';
import {
  ActionError,
  LOCAL_CAPABILITY,
  ZARVIS_OWNER_TENANT_ID,
  ZARVIS_OWNER_USER_ID,
  ZarvisLocalActionRuntime,
} from '../runtime.mjs';
import { createActionServer } from '../server.mjs';

function fixture({ store = new MemoryActionStore(), initialNow = '2026-08-06T02:00:00.000Z' } = {}) {
  let now = initialNow;
  let sequence = 0;
  const runtime = new ZarvisLocalActionRuntime({
    store,
    now: () => now,
    idFactory: () => `id-${++sequence}`,
  });
  return {
    runtime,
    store,
    setNow(value) { now = value; },
  };
}

async function preview(runtime, overrides = {}) {
  return runtime.preview({
    capability: LOCAL_CAPABILITY,
    key: 'assistant.response_style',
    value: 'concise',
    ...overrides,
  });
}

async function approve(runtime, action) {
  return runtime.approve(action.action_id, {
    approval_digest: action.approval_digest,
    approval_nonce: action.approval_nonce,
  });
}

test('preview is permanently owner-bound and reports no external side effects', async () => {
  const { runtime } = fixture();
  const action = await preview(runtime);
  assert.equal(action.owner_user_id, ZARVIS_OWNER_USER_ID);
  assert.equal(action.tenant_id, ZARVIS_OWNER_TENANT_ID);
  assert.equal(action.status, 'pending_approval');
  assert.equal(action.reversible, true);
  assert.equal(action.impact.external_side_effects, false);
  assert.match(action.approval_digest, /^[a-f0-9]{64}$/);
});

test('default-deny registry rejects unknown capabilities and confused-deputy fields', async () => {
  const { runtime } = fixture();
  await assert.rejects(
    runtime.preview({ capability: 'shell.execute', key: 'x', value: 'y' }),
    (error) => error instanceof ActionError && error.code === 'capability_denied',
  );
  await assert.rejects(
    preview(runtime, { untrusted_content: true }),
    (error) => error instanceof ActionError && error.code === 'confused_deputy_denied',
  );
});

test('approval requires the exact digest and one-time nonce', async () => {
  const { runtime } = fixture();
  const action = await preview(runtime);
  await assert.rejects(
    runtime.approve(action.action_id, { approval_digest: '0'.repeat(64), approval_nonce: action.approval_nonce }),
    (error) => error.code === 'approval_mismatch',
  );
  const approved = await approve(runtime, action);
  assert.equal(approved.status, 'approved');
  assert.equal(approved.approval_nonce, null);
  const replay = await approve(runtime, action);
  assert.equal(replay.replayed, true);
});

test('approved action executes once and mutates only the local preference store', async () => {
  const { runtime, store } = fixture();
  const action = await preview(runtime);
  await approve(runtime, action);
  const executed = await runtime.execute(action.action_id);
  assert.equal(executed.status, 'executed');
  assert.match(executed.rollback_digest, /^[a-f0-9]{64}$/);
  assert.equal((await store.readState()).preferences['assistant.response_style'], 'concise');
  const replay = await runtime.execute(action.action_id);
  assert.equal(replay.replayed, true);
});

test('compare-and-set rejects execution after local state drift', async () => {
  const { runtime, store } = fixture();
  const action = await preview(runtime);
  await approve(runtime, action);
  const state = await store.readState();
  await store.writeState({ ...state, preferences: { 'assistant.response_style': 'verbose' } });
  await assert.rejects(
    runtime.execute(action.action_id),
    (error) => error.code === 'stale_preview' && error.status === 409,
  );
});

test('rollback requires exact proof and restores the previous value', async () => {
  const { runtime, store } = fixture();
  const state = await store.readState();
  await store.writeState({ ...state, preferences: { 'assistant.response_style': 'balanced' } });
  const action = await preview(runtime);
  await approve(runtime, action);
  const executed = await runtime.execute(action.action_id);
  await assert.rejects(
    runtime.rollback(action.action_id, { rollback_digest: executed.rollback_digest, rollback_nonce: 'wrong' }),
    (error) => error.code === 'rollback_mismatch',
  );
  const rolledBack = await runtime.rollback(action.action_id, {
    rollback_digest: executed.rollback_digest,
    rollback_nonce: executed.rollback_nonce,
  });
  assert.equal(rolledBack.status, 'rolled_back');
  assert.equal((await store.readState()).preferences['assistant.response_style'], 'balanced');
});

test('expired approval never reaches approval or execution', async () => {
  const first = fixture();
  const pending = await preview(first.runtime);
  first.setNow('2026-08-06T02:16:00.000Z');
  await assert.rejects(approve(first.runtime, pending), (error) => error.code === 'approval_expired');
  await assert.rejects(first.runtime.execute(pending.action_id), (error) => error.code === 'invalid_action_state');

  const second = fixture();
  const approved = await preview(second.runtime);
  await approve(second.runtime, approved);
  second.setNow('2026-08-06T02:16:00.000Z');
  await assert.rejects(second.runtime.execute(approved.action_id), (error) => error.code === 'approval_expired');
  assert.equal((await second.runtime.getAction(approved.action_id)).status, 'expired');
  assert.equal(Object.hasOwn((await second.store.readState()).preferences, approved.key), false);
});

test('emergency stop revokes pending and approved actions and blocks new previews', async () => {
  const { runtime } = fixture();
  const pending = await preview(runtime, { key: 'assistant.language', value: 'th' });
  const approved = await preview(runtime, { key: 'assistant.response_style', value: 'concise' });
  await approve(runtime, approved);
  const stopped = await runtime.emergencyStop('test');
  assert.equal(stopped.revoked, 2);
  assert.equal((await runtime.getAction(pending.action_id)).status, 'revoked');
  assert.equal((await runtime.getAction(approved.action_id)).status, 'revoked');
  await assert.rejects(preview(runtime), (error) => error.code === 'emergency_stop_active');
  await assert.rejects(runtime.resume({ confirmation: 'wrong' }), (error) => error.code === 'resume_confirmation_required');
  assert.equal((await runtime.resume({ confirmation: 'RESUME_LOCAL_ACTIONS' })).emergency_stop, false);
});

test('fixed-path store reconstructs executed action and local state after restart', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'zarvis-action-'));
  try {
    const first = fixture({ store: new FileActionStore({ dataDir: directory }) });
    const action = await preview(first.runtime);
    await approve(first.runtime, action);
    await first.runtime.execute(action.action_id);

    const second = fixture({ store: new FileActionStore({ dataDir: directory }) });
    assert.equal((await second.runtime.getAction(action.action_id)).status, 'executed');
    assert.equal((await second.store.readState()).preferences['assistant.response_style'], 'concise');
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test('HTTP service fails closed and separates owner approval from worker queue and execution', async () => {
  assert.throws(() => createActionServer(), /ZARVIS_LOCAL_OWNER_TOKEN/);

  const ownerToken = 'o'.repeat(32);
  const workerToken = 'w'.repeat(32);
  const { runtime } = fixture();
  const server = createActionServer({ ownerToken, workerToken, runtime });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  const base = `http://127.0.0.1:${address.port}`;
  try {
    assert.equal((await fetch(`${base}/healthz`)).status, 200);
    assert.equal((await fetch(`${base}/v1/actions`)).status, 403);
    assert.equal((await fetch(`${base}/v1/internal/actions/approved`)).status, 403);

    const createdResponse = await fetch(`${base}/v1/actions/preview`, {
      method: 'POST',
      headers: { authorization: `Bearer ${ownerToken}`, 'content-type': 'application/json' },
      body: JSON.stringify({ capability: LOCAL_CAPABILITY, key: 'assistant.language', value: 'th' }),
    });
    assert.equal(createdResponse.status, 201);
    const created = await createdResponse.json();

    const approvedResponse = await fetch(`${base}/v1/actions/${created.action_id}/approve`, {
      method: 'POST',
      headers: { authorization: `Bearer ${ownerToken}`, 'content-type': 'application/json' },
      body: JSON.stringify({ approval_digest: created.approval_digest, approval_nonce: created.approval_nonce }),
    });
    assert.equal(approvedResponse.status, 200);

    const queueResponse = await fetch(`${base}/v1/internal/actions/approved`, {
      headers: { 'x-zarvis-action-worker-token': workerToken },
    });
    assert.equal(queueResponse.status, 200);
    assert.deepEqual((await queueResponse.json()).action_ids, [created.action_id]);

    assert.equal((await fetch(`${base}/v1/internal/actions/${created.action_id}/execute`, { method: 'POST' })).status, 403);
    const executedResponse = await fetch(`${base}/v1/internal/actions/${created.action_id}/execute`, {
      method: 'POST',
      headers: { 'x-zarvis-action-worker-token': workerToken },
    });
    assert.equal(executedResponse.status, 200);
    assert.equal((await executedResponse.json()).status, 'executed');
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
