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
  name: 'Regression Customer',
  avatar: 'RC',
  channel: 'line',
  unread: 3,
  time: 'Yesterday',
  messages: [{ sender: 'customer', text: 'hello', time: 'Yesterday' }],
  details: {
    phone: '+66 1 234 5678',
    email: 'regression@example.test',
    assigned: 'Alex Rivera',
    tags: ['VIP', 'LINE OA'],
    orders: [],
  },
};

function createStorageFixture(initialMetadata) {
  const calls = [];
  let metadata = initialMetadata || mapLegacyChatToNormalized(legacyChat).contact.metadata;
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

test('service-backed regression: active chat keeps unread at 0 after new message and metadata touch', async () => {
  const fixture = createStorageFixture();
  const runtime = createLegacyChatRuntime({ storage: fixture.storage });
  const request = { user: { tenantId } };

  await runtime.markRead(request, 7);
  assert.equal(fixture.getMetadata().unread, 0);

  await runtime.touchMetadata(request, 7, { displayTime: 'Just now', unread: 0 });
  assert.equal(fixture.getMetadata().unread, 0);
  assert.equal(fixture.getMetadata().displayTime, 'Just now');
});

test('service-backed regression: inactive chat increments unread after new message and metadata touch', async () => {
  const fixture = createStorageFixture();
  const runtime = createLegacyChatRuntime({ storage: fixture.storage });
  const request = { user: { tenantId } };

  await runtime.touchMetadata(request, 7, { displayTime: 'Just now', unread: 4 });
  assert.equal(fixture.getMetadata().unread, 4);
  assert.equal(fixture.getMetadata().displayTime, 'Just now');
});

test('service-backed regression: display-time projection reflects PostgreSQL metadata without mutating JSON', async () => {
  const fixture = createStorageFixture();
  const runtime = createLegacyChatRuntime({ storage: fixture.storage });
  const request = { user: { tenantId } };

  await runtime.touchMetadata(request, 7, { displayTime: 'Now', unread: 1 });

  const state = await runtime.read(request, 7);
  assert.equal(state.metadata.displayTime, 'Now');
  assert.equal(state.metadata.unread, 1);

  const overlaid = overlayPostgresMessages(legacyChat, {
    conversation: { id: conversationId },
    messages: [],
    metadata: state.metadata,
  });
  assert.equal(overlaid.time, 'Now');
  assert.equal(overlaid.unread, 1);
});

test('service-backed regression: JSON rollback snapshot is not mutated by PostgreSQL metadata updates', async () => {
  const fixture = createStorageFixture();
  const runtime = createLegacyChatRuntime({ storage: fixture.storage });
  const request = { user: { tenantId } };

  const jsonRollbackSnapshot = { ...legacyChat, unread: 3, time: 'Yesterday' };

  await runtime.markRead(request, 7);
  await runtime.replaceTags(request, 7, ['Priority', 'Postgres']);
  await runtime.touchMetadata(request, 7, { displayTime: 'Just now', unread: 0 });

  const finalMetadata = fixture.getMetadata();
  assert.equal(finalMetadata.unread, 0);
  assert.deepEqual(finalMetadata.tags, ['Priority', 'Postgres']);
  assert.equal(finalMetadata.displayTime, 'Just now');

  assert.equal(jsonRollbackSnapshot.unread, 3);
  assert.equal(jsonRollbackSnapshot.time, 'Yesterday');
});

test('service-backed regression: sequential metadata updates persist each patch', async () => {
  const fixture = createStorageFixture();
  const runtime = createLegacyChatRuntime({ storage: fixture.storage });
  const request = { user: { tenantId } };

  await runtime.touchMetadata(request, 7, { unread: 5 });
  await runtime.touchMetadata(request, 7, { displayTime: 'Now' });

  const finalMetadata = fixture.getMetadata();
  assert.equal(finalMetadata.unread, 5);
  assert.equal(finalMetadata.displayTime, 'Now');
});
