import test from 'node:test';
import assert from 'node:assert/strict';

import { mapLegacyChatToNormalized } from '../server/storage/postgres/legacy-chat-mapping.js';

const legacyChat = {
  id: 42,
  name: ' Example Customer ',
  avatar: 'EC',
  channel: 'line',
  unread: 2,
  time: '10:24 AM',
  messages: [
    { sender: 'customer', text: ' Hello ', time: '10:20 AM' },
    { sender: 'agent', text: ' Hi there ', time: '10:21 AM' },
  ],
  details: {
    phone: ' +66 81 234 5678 ',
    email: ' CUSTOMER@EXAMPLE.COM ',
    assigned: 'Sarah Connor',
    tags: ['VIP', 'LINE OA'],
    orders: [{ id: 'ORD-1', total: '$10.00' }],
  },
};

test('maps one legacy aggregate into stable normalized repository inputs', () => {
  assert.deepEqual(mapLegacyChatToNormalized(legacyChat), {
    contact: {
      name: 'Example Customer',
      email: 'customer@example.com',
      phone: '+66 81 234 5678',
      externalId: 'legacy-chat:42',
      metadata: {
        legacyChatId: 42,
        avatar: 'EC',
        assigned: 'Sarah Connor',
        tags: ['VIP', 'LINE OA'],
        orders: [{ id: 'ORD-1', total: '$10.00' }],
        unread: 2,
        displayTime: '10:24 AM',
      },
    },
    conversation: {
      channel: 'line',
      externalThreadId: 'legacy-chat:42',
    },
    messages: [
      {
        direction: 'inbound',
        senderType: 'customer',
        body: 'Hello',
        externalMessageId: 'legacy-chat:42:message:0',
        metadata: { legacyTime: '10:20 AM' },
      },
      {
        direction: 'outbound',
        senderType: 'agent',
        body: 'Hi there',
        externalMessageId: 'legacy-chat:42:message:1',
        metadata: { legacyTime: '10:21 AM' },
      },
    ],
  });
});

test('mapping is deterministic for retry-safe legacy identifiers', () => {
  const clonedLegacyChat = JSON.parse(JSON.stringify(legacyChat));
  assert.deepEqual(mapLegacyChatToNormalized(legacyChat), mapLegacyChatToNormalized(clonedLegacyChat));
});

test('fails closed on unsupported or malformed legacy records', () => {
  assert.throws(() => mapLegacyChatToNormalized({ ...legacyChat, id: '42' }), /positive integer/);
  assert.throws(() => mapLegacyChatToNormalized({ ...legacyChat, channel: 'sms' }), /supported channel/);
  assert.throws(() => mapLegacyChatToNormalized({ ...legacyChat, unread: -1 }), /unread count/);
  assert.throws(() => mapLegacyChatToNormalized({ ...legacyChat, messages: [{ sender: 'bot', text: 'x' }] }), /supported sender/);
  assert.throws(() => mapLegacyChatToNormalized({ ...legacyChat, messages: [{ sender: 'customer', text: '   ' }] }), /message text/);
  assert.throws(() => mapLegacyChatToNormalized({ ...legacyChat, details: { ...legacyChat.details, tags: 'VIP' } }), /tags/);
});

test('does not invent timestamps from display-only legacy time labels', () => {
  const mapped = mapLegacyChatToNormalized(legacyChat);
  assert.equal('sentAt' in mapped.messages[0], false);
  assert.deepEqual(mapped.messages[0].metadata, { legacyTime: '10:20 AM' });
  assert.equal(mapped.contact.metadata.displayTime, '10:24 AM');
});