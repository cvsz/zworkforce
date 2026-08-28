import test from 'node:test';
import assert from 'node:assert/strict';
import { overlayPostgresMessages } from '../server/storage/postgres/chat-route-gate.js';
import { mapLegacyChatToNormalized } from '../server/storage/postgres/legacy-chat-mapping.js';
import { createLegacyChatRuntime } from '../server/storage/postgres/legacy-chat-runtime.js';

const tenantId = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';
const contactId = 'cccccccc-3333-4333-8333-cccccccccccc';
const conversationId = 'dddddddd-4444-4444-8444-dddddddddddd';

const legacyChat = {
  id: 7,
  name: 'Metadata Customer',
  avatar: 'MC',
  channel: 'line',
  unread: 3,
  time: 'Yesterday',
  messages: [{ sender: 'customer', text: 'hello', time: 'Yesterday' }],
  details: {
    phone: '+66 1 234 5678',
    email: 'meta@example.test',
    assigned: 'Alex Rivera',
    tags: ['VIP', 'LINE OA'],
    orders: [],
  },
};

test('legacy mapper deterministically includes chat metadata, unread state, and tags', () => {
  const mapped = mapLegacyChatToNormalized(legacyChat);
  assert.deepEqual(mapped.contact.metadata, {
    legacyChatId: 7,
    avatar: 'MC',
    assigned: 'Alex Rivera',
    tags: ['VIP', 'LINE OA'],
    orders: [],
    unread: 3,
    displayTime: 'Yesterday',
  });
});

test('PostgreSQL read overlay replaces legacy metadata without changing API shape', () => {
  const overlaid = overlayPostgresMessages({
    ...legacyChat,
    avatar: 'JSON',
    unread: 99,
    time: 'JSON time',
    details: { ...legacyChat.details, assigned: 'JSON owner', tags: ['JSON'], orders: [{ id: 'json' }] },
  }, {
    conversation: { id: conversationId },
    messages: [],
    metadata: {
      avatar: 'PG',
      assigned: 'Postgres owner',
      tags: ['Priority'],
      orders: [{ id: 'pg' }],
      unread: 1,
      displayTime: 'Postgres time',
    },
  });

  assert.equal(overlaid.avatar, 'PG');
  assert.equal(overlaid.unread, 1);
  assert.equal(overlaid.time, 'Postgres time');
  assert.equal(overlaid.details.assigned, 'Postgres owner');
  assert.deepEqual(overlaid.details.tags, ['Priority']);
  assert.deepEqual(overlaid.details.orders, [{ id: 'pg' }]);
  assert.deepEqual(overlaid.messages, []);
});

function createStorageFixture() {
  const calls = [];
  let metadata = mapLegacyChatToNormalized(legacyChat).contact.metadata;
  return {
    calls,
    storage: {
      async withIdentityTransaction(identity, operation) {
        return operation({
          tenantId: identity.tenantId,
          async query(text, values = []) {
            calls.push({ text, values });
            if (/FROM conversations c\s+WHERE c\.external_thread_id = \$1/i.test(text)) {
              return { rows: [{ id: conversationId, contactId, channel: 'line', externalThreadId: values[0], status: 'open' }] };
            }
            if (/FROM contacts/i.test(text) && /WHERE id = \$1/i.test(text)) {
              return { rows: [{ id: contactId, metadata }] };
            }
            if (/UPDATE contacts/i.test(text)) {
              metadata = JSON.parse(values[1]);
              return { rows: [{ id: contactId, metadata }] };
            }
            if (/FROM messages m/i.test(text)) return { rows: [] };
            return { rows: [] };
          },
        });
      },
    },
    getMetadata: () => metadata,
  };
}

test('legacy runtime reads and mutates metadata inside the authenticated tenant transaction', async () => {
  const fixture = createStorageFixture();
  const runtime = createLegacyChatRuntime({ storage: fixture.storage });
  const request = { user: { tenantId } };

  const state = await runtime.read(request, 7);
  assert.equal(state.metadata.unread, 3);
  assert.deepEqual(state.metadata.tags, ['VIP', 'LINE OA']);

  const readState = await runtime.markRead(request, 7);
  assert.equal(readState.unread, 0);

  const tagState = await runtime.replaceTags(request, 7, [' Priority ', 'LINE']);
  assert.deepEqual(tagState.tags, ['Priority', 'LINE']);
  assert.deepEqual(fixture.getMetadata().tags, ['Priority', 'LINE']);
  assert.equal(fixture.getMetadata().unread, 0);
  assert.ok(fixture.calls.some(call => /UPDATE contacts/i.test(call.text)));
});

test('legacy runtime metadata mutations fail closed for invalid tags and missing tenant identity', async () => {
  const fixture = createStorageFixture();
  const runtime = createLegacyChatRuntime({ storage: fixture.storage });

  await assert.rejects(() => runtime.markRead({ user: {} }, 7), /authenticated tenant identity is required/i);
  await assert.rejects(() => runtime.replaceTags({ user: { tenantId } }, 7, ['']), /non-empty string/i);
  await assert.rejects(() => runtime.replaceTags({ user: { tenantId } }, 7, Array(33).fill('x')), /at most 32/i);
});

test('legacy runtime touchMetadata updates partial metadata inside the authenticated tenant transaction', async () => {
  const fixture = createStorageFixture();
  const runtime = createLegacyChatRuntime({ storage: fixture.storage });
  const request = { user: { tenantId } };

  const touched = await runtime.touchMetadata(request, 7, { displayTime: 'Just now', unread: 5 });
  assert.equal(touched.displayTime, 'Just now');
  assert.equal(touched.unread, 5);
  assert.deepEqual(fixture.getMetadata(), {
    legacyChatId: 7,
    avatar: 'MC',
    assigned: 'Alex Rivera',
    tags: ['VIP', 'LINE OA'],
    orders: [],
    unread: 5,
    displayTime: 'Just now',
  });
});

test('legacy runtime touchMetadata preserves existing metadata when patching a subset of fields', async () => {
  const fixture = createStorageFixture();
  const runtime = createLegacyChatRuntime({ storage: fixture.storage });
  const request = { user: { tenantId } };

  const touched = await runtime.touchMetadata(request, 7, { displayTime: '2 mins ago' });
  assert.equal(touched.displayTime, '2 mins ago');
  assert.equal(touched.unread, 3);
  assert.deepEqual(touched.tags, ['VIP', 'LINE OA']);
});
