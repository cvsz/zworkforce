import test from 'node:test';
import assert from 'node:assert/strict';
import { createCampaignExecutor } from '../server/campaigns/campaign-executor.js';

test('campaign executor dispatches supported actions and returns status', async () => {
  const executor = createCampaignExecutor();

  const sendResult = await executor.executeAction({
    type: 'send_message',
    channel: 'whatsapp',
    contactId: 'contact-1',
    campaignId: 'campaign-1',
    payload: { data: { text: 'Hello', to: '+1234567890' } },
    tenantId: 'tenant-1',
  });
  assert.equal(sendResult.status, 'completed');
  assert.ok(sendResult.result.delivered);

  const tagResult = await executor.executeAction({
    type: 'update_tag',
    channel: 'line',
    contactId: 'contact-2',
    campaignId: 'campaign-1',
    payload: { data: { contactId: 'contact-2', tags: ['vip'] } },
    tenantId: 'tenant-1',
  });
  assert.equal(tagResult.status, 'completed');
  assert.equal(tagResult.result.updated, true);

  const webhookResult = await executor.executeAction({
    type: 'webhook',
    channel: 'messenger',
    contactId: 'contact-3',
    campaignId: 'campaign-2',
    payload: { data: { url: 'https://example.com/hook', body: { foo: 'bar' } } },
    tenantId: 'tenant-1',
  });
  assert.equal(webhookResult.status, 'completed');
  assert.equal(webhookResult.result.url, 'https://example.com/hook');
});

test('campaign executor rejects unsupported action types', async () => {
  const executor = createCampaignExecutor();

  const result = await executor.executeAction({
    type: 'unknown_action',
    channel: 'whatsapp',
    contactId: 'contact-1',
    campaignId: 'campaign-1',
    payload: {},
    tenantId: 'tenant-1',
  });
  assert.equal(result.status, 'failed');
  assert.ok(result.error.includes('Unsupported action type'));
});

test('campaign executor validates send_message payload', async () => {
  const executor = createCampaignExecutor();

  const result = await executor.executeAction({
    type: 'send_message',
    channel: 'whatsapp',
    contactId: 'contact-1',
    campaignId: 'campaign-1',
    payload: { data: { text: 'Hello' } },
    tenantId: 'tenant-1',
  });
  assert.equal(result.status, 'failed');
  assert.ok(result.error.includes('send_message requires text and to'));
});

test('campaign executor validates update_tag payload', async () => {
  const executor = createCampaignExecutor();

  const result = await executor.executeAction({
    type: 'update_tag',
    channel: 'line',
    contactId: 'contact-1',
    campaignId: 'campaign-1',
    payload: { data: { contactId: 'contact-1' } },
    tenantId: 'tenant-1',
  });
  assert.equal(result.status, 'failed');
  assert.ok(result.error.includes('update_tag requires contactId and tags array'));
});

test('campaign executor validates webhook payload', async () => {
  const executor = createCampaignExecutor();

  const result = await executor.executeAction({
    type: 'webhook',
    channel: 'messenger',
    contactId: 'contact-1',
    campaignId: 'campaign-1',
    payload: { data: {} },
    tenantId: 'tenant-1',
  });
  assert.equal(result.status, 'failed');
  assert.ok(result.error.includes('webhook requires url'));
});

test('campaign executor rate limits per channel', async () => {
  const executor = createCampaignExecutor();
  const results = [];

  for (let i = 0; i < 10; i += 1) {
    results.push(executor.executeAction({
      type: 'send_message',
      channel: 'whatsapp',
      contactId: `contact-${i}`,
      campaignId: 'campaign-1',
      payload: { data: { text: 'Hello', to: `+${i}` } },
      tenantId: 'tenant-1',
    }));
  }

  const outcomes = await Promise.all(results);
  const completed = outcomes.filter(r => r.status === 'completed');
  assert.ok(completed.length > 0, 'some messages should complete within rate limits');
});
