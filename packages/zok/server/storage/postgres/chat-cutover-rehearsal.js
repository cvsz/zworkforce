import { createHash } from 'node:crypto';
import { isDeepStrictEqual } from 'node:util';
import { createConversationsRepository } from './conversations-repository.js';
import { mapLegacyChatToNormalized } from './legacy-chat-mapping.js';

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function prepareChats(chats) {
  if (!Array.isArray(chats)) throw new TypeError('Legacy chats must be an array');

  const seenThreads = new Set();
  const seenMessages = new Set();
  return chats.map(chat => {
    const mapped = mapLegacyChatToNormalized(chat);
    const threadId = mapped.conversation.externalThreadId;
    if (seenThreads.has(threadId)) {
      throw new TypeError(`Duplicate legacy chat external id: ${threadId}`);
    }
    seenThreads.add(threadId);

    for (const message of mapped.messages) {
      if (seenMessages.has(message.externalMessageId)) {
        throw new TypeError(`Duplicate legacy message external id: ${message.externalMessageId}`);
      }
      seenMessages.add(message.externalMessageId);
    }
    return mapped;
  });
}

function sourceDigest(mappedChats) {
  return createHash('sha256').update(JSON.stringify(mappedChats)).digest('hex');
}

function fail(message) {
  throw new Error(`Chat cutover preflight failed: ${message}`);
}

function assertMessageMatches(existing, expected) {
  if (
    existing.direction !== expected.direction ||
    existing.senderType !== expected.senderType ||
    existing.body !== expected.body ||
    !isDeepStrictEqual(existing.metadata ?? {}, expected.metadata ?? {})
  ) {
    fail(`message ${expected.externalMessageId} differs from the legacy source`);
  }
}

export async function preflightLegacyChatCutover({ chats, tenantId, storage } = {}) {
  if (typeof tenantId !== 'string' || !UUID_PATTERN.test(tenantId)) {
    throw new TypeError('tenantId is required and must be a UUID');
  }
  if (!storage || typeof storage.withTenantTransaction !== 'function') {
    throw new TypeError('PostgreSQL storage with withTenantTransaction() is required');
  }

  const mappedChats = prepareChats(chats);
  const expectedMessageCount = mappedChats.reduce((total, chat) => total + chat.messages.length, 0);

  await storage.withTenantTransaction(tenantId, async tx => {
    const conversations = createConversationsRepository(tx);

    for (const mapped of mappedChats) {
      const threadId = mapped.conversation.externalThreadId;
      const conversation = await conversations.findByExternalThreadId(threadId);
      if (!conversation) fail(`missing imported conversation ${threadId}`);
      if (conversation.channel !== mapped.conversation.channel) {
        fail(`conversation ${threadId} channel differs from the legacy source`);
      }

      const existingMessages = await conversations.listMessages(conversation.id);
      if (existingMessages.length !== mapped.messages.length) {
        fail(`conversation ${threadId} message count differs from the legacy source`);
      }

      const byExternalId = new Map();
      for (const existing of existingMessages) {
        if (!existing.externalMessageId) {
          fail(`conversation ${threadId} contains a message without a legacy external id`);
        }
        if (byExternalId.has(existing.externalMessageId)) {
          fail(`conversation ${threadId} contains duplicate message id ${existing.externalMessageId}`);
        }
        byExternalId.set(existing.externalMessageId, existing);
      }

      for (const expected of mapped.messages) {
        const existing = byExternalId.get(expected.externalMessageId);
        if (!existing) fail(`missing imported message ${expected.externalMessageId}`);
        assertMessageMatches(existing, expected);
      }
    }
  });

  return Object.freeze({
    ready: true,
    chats: mappedChats.length,
    messages: expectedMessageCount,
    sourceDigest: sourceDigest(mappedChats),
  });
}
