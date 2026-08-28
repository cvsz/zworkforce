import assert from 'node:assert/strict';
import test from 'node:test';
import { MemoryActionStore } from '../store.mjs';
import { LOCAL_CAPABILITY, ZarvisLocalActionRuntime } from '../runtime.mjs';
import { createActionServer } from '../server.mjs';

test('concurrent worker execution requests serialize into one execution and one replay', async () => {
  const ownerToken = 'o'.repeat(32);
  const workerToken = 'w'.repeat(32);
  let sequence = 0;
  const runtime = new ZarvisLocalActionRuntime({
    store: new MemoryActionStore(),
    now: () => '2026-08-06T02:00:00.000Z',
    idFactory: () => `concurrent-${++sequence}`,
  });
  const server = createActionServer({ ownerToken, workerToken, runtime });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  const base = `http://127.0.0.1:${address.port}`;

  try {
    const previewResponse = await fetch(`${base}/v1/actions/preview`, {
      method: 'POST',
      headers: { authorization: `Bearer ${ownerToken}`, 'content-type': 'application/json' },
      body: JSON.stringify({
        capability: LOCAL_CAPABILITY,
        key: 'assistant.concurrent',
        value: 'safe',
      }),
    });
    assert.equal(previewResponse.status, 201);
    const preview = await previewResponse.json();

    const approvalResponse = await fetch(`${base}/v1/actions/${preview.action_id}/approve`, {
      method: 'POST',
      headers: { authorization: `Bearer ${ownerToken}`, 'content-type': 'application/json' },
      body: JSON.stringify({
        approval_digest: preview.approval_digest,
        approval_nonce: preview.approval_nonce,
      }),
    });
    assert.equal(approvalResponse.status, 200);

    const execute = () => fetch(`${base}/v1/internal/actions/${preview.action_id}/execute`, {
      method: 'POST',
      headers: { 'x-zarvis-action-worker-token': workerToken },
    });
    const responses = await Promise.all([execute(), execute()]);
    assert.deepEqual(responses.map((response) => response.status), [200, 200]);
    const results = await Promise.all(responses.map((response) => response.json()));
    assert.equal(results[0].execution_id, results[1].execution_id);
    assert.deepEqual(results.map((result) => result.replayed).sort(), [false, true]);

    const executionEvents = (await runtime.store.readEvents())
      .filter((event) => event.event_type === 'zarvis.action.executed.v1');
    assert.equal(executionEvents.length, 1);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
