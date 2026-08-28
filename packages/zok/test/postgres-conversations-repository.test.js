import test from 'node:test';
import assert from 'node:assert/strict';
import { createConversationsRepository } from '../server/storage/postgres/conversations-repository.js';

const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';
const contactId = 'cccccccc-3333-4333-8333-cccccccccccc';
const conversationId = 'dddddddd-4444-4444-8444-dddddddddddd';

test('conversations repository creates tenant-scoped conversations and messages', async () => {
  const calls = [];
  const tx = {
    tenantId,
    async query(text, values = []) {
      calls.push({ text, values });
      if (/INSERT INTO conversations/i.test(text)) {
        return { rows: [{ id: conversationId, contactId, channel: 'line', status: 'open' }] };
      }
      if (/INSERT INTO messages/i.test(text)) {
        return { rows: [{ id: 'eeeeeeee-5555-4555-8555-eeeeeeeeeeee', conversationId, direction: 'outbound', senderType: 'agent', body: 'Hello' }] };
      }
      return { rows: [{ id: conversationId, contactId, channel: 'line', status: 'open', messages: [] }] };
    },
  };
  const repository = createConversationsRepository(tx);

  const conversation = await repository.create({ contactId, channel: 'line' });
  assert.equal(conversation.id, conversationId);
  assert.equal(calls[0].values[0], tenantId);
  assert.equal(calls[0].values[1], contactId);

  const message = await repository.addMessage(conversationId, {
    direction: 'outbound',
    senderType: 'agent',
    body: ' Hello ',
  });
  assert.equal(message.body, 'Hello');
  assert.equal(calls[1].values[0], tenantId);
  assert.equal(calls[1].values[1], conversationId);
  assert.equal(calls[1].values[4], 'Hello');
});

test('conversations repository validates tenant transaction context and inputs', async () => {
  assert.throws(
    () => createConversationsRepository({ query: async () => ({ rows: [] }) }),
    /tenant transaction context is required/i,
  );
  const repository = createConversationsRepository({ tenantId, query: async () => ({ rows: [] }) });
  await assert.rejects(() => repository.create({ contactId: 'bad', channel: 'line' }), /valid contact id/i);
  await assert.rejects(() => repository.create({ contactId, channel: 'sms' }), /supported channel/i);
  await assert.rejects(() => repository.addMessage('bad', { direction: 'outbound', senderType: 'agent', body: 'x' }), /valid conversation id/i);
  await assert.rejects(() => repository.addMessage(conversationId, { direction: 'sideways', senderType: 'agent', body: 'x' }), /valid message direction/i);
  await assert.rejects(() => repository.addMessage(conversationId, { direction: 'outbound', senderType: 'hacker', body: 'x' }), /valid sender type/i);
  await assert.rejects(() => repository.addMessage(conversationId, { direction: 'outbound', senderType: 'agent', body: '' }), /message body is required/i);
});
