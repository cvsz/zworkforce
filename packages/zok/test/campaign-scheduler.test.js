import test from 'node:test';
import assert from 'node:assert/strict';
import { createCampaignScheduler } from '../server/campaigns/campaign-scheduler.js';

test('campaign scheduler creates and lists schedules', async () => {
  const calls = [];
  const pool = {
    connect() {
      return Promise.resolve({
        query(text, values = []) {
          calls.push({ text, values });
          if (text.trimStart().startsWith('SELECT')) {
            return Promise.resolve({
              rows: [{ id: 's1', campaignId: 'c1', ruleType: 'once', nextRunAt: '2026-08-22T10:00:00Z', paused: false }],
            });
          }
          if (text.trimStart().startsWith('INSERT')) {
            return Promise.resolve({
              rows: [{ id: 's2', campaignId: 'c1', ruleType: 'cron', cronExpression: '0 9 * * *', nextRunAt: '2026-08-23T09:00:00Z', paused: false }],
            });
          }
          return Promise.resolve({ rows: [] });
        },
        release() {},
      });
    },
  };

  const scheduler = createCampaignScheduler({ pool });

  const schedules = await scheduler.listSchedules('tenant-1');
  assert.deepEqual(schedules, [{ id: 's1', campaignId: 'c1', ruleType: 'once', nextRunAt: '2026-08-22T10:00:00Z', paused: false }]);

  const created = await scheduler.createSchedule('tenant-1', {
    campaignId: 'c1',
    ruleType: 'cron',
    cronExpression: '0 9 * * *',
    timezone: 'UTC',
    nextRunAt: '2026-08-23T09:00:00Z',
  });
  assert.equal(created.id, 's2');
  assert.equal(created.cronExpression, '0 9 * * *');
});

test('campaign scheduler pauses and resumes schedules', async () => {
  const pool = {
    connect() {
      return Promise.resolve({
        async query(text, values = []) {
          if (text.includes('UPDATE') && text.includes('paused = true')) {
            return Promise.resolve({
              rows: [{ id: 's1', campaignId: 'c1', paused: true }],
            });
          }
          if (text.includes('UPDATE') && text.includes('paused = false')) {
            return Promise.resolve({
              rows: [{ id: 's1', campaignId: 'c1', paused: false }],
            });
          }
          return Promise.resolve({ rows: [] });
        },
        release() {},
      });
    },
  };

  const scheduler = createCampaignScheduler({ pool });

  const paused = await scheduler.pauseSchedule('tenant-1', 's1');
  assert.equal(paused.paused, true);

  const resumed = await scheduler.resumeSchedule('tenant-1', 's1');
  assert.equal(resumed.paused, false);
});

test('campaign scheduler gets due schedules', async () => {
  const pool = {
    connect() {
      return Promise.resolve({
        async query(text, values = []) {
          if (text.includes('paused = false AND next_run_at <= now()')) {
            return Promise.resolve({
              rows: [{ id: 's1', campaignId: 'c1', nextRunAt: new Date().toISOString() }],
            });
          }
          return Promise.resolve({ rows: [] });
        },
        release() {},
      });
    },
  };

  const scheduler = createCampaignScheduler({ pool });
  const due = await scheduler.getDueSchedules('tenant-1');
  assert.equal(due.length, 1);
  assert.equal(due[0].id, 's1');
});

test('campaign scheduler validates inputs', async () => {
  const scheduler = createCampaignScheduler({ pool: null });

  await assert.rejects(() => scheduler.createSchedule('tenant-1', {}), /campaignId is required/);
  await assert.rejects(() => scheduler.createSchedule('tenant-1', { campaignId: 'c1', ruleType: 'invalid' }), /ruleType must be once, cron, or event/);
  await assert.rejects(() => scheduler.createSchedule('tenant-1', { campaignId: 'c1', ruleType: 'cron' }), /cronExpression is required for cron ruleType/);
  await assert.rejects(() => scheduler.listSchedules(''), /tenantId is required/);
});

test('campaign scheduler converts timezones', async () => {
  const scheduler = createCampaignScheduler({ pool: null });
  const utc = scheduler.convertToUtc('09:00', 'Asia/Bangkok');
  assert.equal(utc, '02:00');
});

test('campaign scheduler calculates next run for once and cron', async () => {
  const scheduler = createCampaignScheduler({ pool: null });
  const once = scheduler.calculateNextRun('once', null, 'UTC', new Date('2026-08-22T10:00:00Z'));
  assert.deepEqual(once, new Date('2026-08-22T10:00:00Z'));

  const cron = scheduler.calculateNextRun('cron', '0 9 * * *', 'UTC', new Date('2026-08-22T10:00:00Z'));
  assert.equal(cron.getHours(), 9);
  assert.equal(cron.getDate(), 23);
});
