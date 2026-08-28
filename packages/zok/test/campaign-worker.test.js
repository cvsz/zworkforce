import test from 'node:test';
import assert from 'node:assert/strict';
import { createCampaignWorker } from '../server/campaigns/campaign-worker.js';

test('campaign worker starts and stops', async () => {
  const worker = createCampaignWorker({ pool: null, concurrency: 1 });

  await worker.start();
  assert.equal(worker.isHealthy(), true);
  assert.equal(worker.getQueueDepth(), 1);

  await worker.stop();
  assert.equal(worker.isHealthy(), false);
  assert.equal(worker.getQueueDepth(), 0);
});

test('campaign worker does not start twice', async () => {
  const worker = createCampaignWorker({ pool: null, concurrency: 1 });

  await worker.start();
  await worker.start(); // second start should be a no-op
  assert.equal(worker.getQueueDepth(), 1);

  await worker.stop();
});

test('campaign worker health reflects database status', async () => {
  let queryCount = 0;
  const pool = {
    connect() {
      return Promise.resolve({
        async query() {
          queryCount += 1;
          return { rows: [] };
        },
        release() {},
      });
    },
  };

  const worker = createCampaignWorker({ pool, concurrency: 1 });
  await worker.start();
  await worker.checkHealth();
  assert.equal(worker.isHealthy(), true);

  const badPool = {
    connect() {
      return Promise.resolve({
        async query() {
          throw new Error('connection failed');
        },
        release() {},
      });
    },
  };

  const badWorker = createCampaignWorker({ pool: badPool, concurrency: 1 });
  await badWorker.start();
  await badWorker.checkHealth();
  assert.equal(badWorker.isHealthy(), false);

  await worker.stop();
  await badWorker.stop();
});

test('campaign worker exposes active count', async () => {
  const worker = createCampaignWorker({ pool: null, concurrency: 1 });
  assert.equal(worker.getActiveCount(), 0);

  await worker.start();
  assert.equal(worker.getActiveCount(), 0);

  await worker.stop();
});
