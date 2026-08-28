import { createHash } from 'node:crypto';
import { isDeepStrictEqual } from 'node:util';
import { createContactsRepository } from './contacts-repository.js';
import { createConversationsRepository } from './conversations-repository.js';
import { mapLegacyChatToNormalized } from './legacy-chat-mapping.js';

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const CHECKPOINT_VERSION = 1;
const IMPORT_LOCK_NAMESPACE = 'zok:legacy-chat-import:v1';

function sameJson(left, right) {
  return isDeepStrictEqual(left ?? {}, right ?? {});
}

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

function importLockKey(mappedChats, tenantId) {
  return `${IMPORT_LOCK_NAMESPACE}:${tenantId}:${sourceDigest(mappedChats)}`;
}

function buildCheckpoint(mappedChats, tenantId, nextIndex) {
  return Object.freeze({
    version: CHECKPOINT_VERSION,
    tenantId,
    sourceDigest: sourceDigest(mappedChats),
    nextIndex,
    totalChats: mappedChats.length,
  });
}

function resolveStartIndex(checkpoint, mappedChats, tenantId) {
  if (checkpoint === undefined || checkpoint === null) return 0;
  if (!checkpoint || typeof checkpoint !== 'object' || Array.isArray(checkpoint)) {
    throw new TypeError('Import checkpoint must be an object');
  }
  const expected = buildCheckpoint(mappedChats, tenantId, checkpoint.nextIndex);
  if (checkpoint.version !== CHECKPOINT_VERSION) {
    throw new Error('Import checkpoint version is unsupported');
  }
  if (checkpoint.tenantId !== tenantId) {
    throw new Error('Import checkpoint tenant does not match import tenant');
  }
  if (checkpoint.sourceDigest !== expected.sourceDigest || checkpoint.totalChats !== mappedChats.length) {
    throw new Error('Import checkpoint source does not match current legacy chats');
  }
  if (!Number.isInteger(checkpoint.nextIndex) || checkpoint.nextIndex < 0 || checkpoint.nextIndex > mappedChats.length) {
    throw new Error('Import checkpoint nextIndex is invalid');
  }
  return checkpoint.nextIndex;
}

function buildSummary(mappedChats) {
  return {
    chats: mappedChats.length,
    messages: mappedChats.reduce((total, chat) => total + chat.messages.length, 0),
    contactsCreated: 0,
    contactsReused: 0,
    conversationsCreated: 0,
    conversationsReused: 0,
    messagesCreated: 0,
    messagesReused: 0,
  };
}

async function findContactByExternalId(tx, externalId) {
  const result = await tx.query(`
    SELECT id, name, email, phone, external_id AS "externalId", metadata
    FROM contacts
    WHERE external_id = $1
    ORDER BY id ASC
    LIMIT 2
  `, [externalId]);
  if (result.rows.length > 1) {
    throw new Error(`Ambiguous existing contact for ${externalId}`);
  }
  return result.rows[0] || null;
}

function assertExistingContactMatches(existing, expected) {
  if (
    existing.name !== expected.name ||
    (existing.email || null) !== (expected.email || null) ||
    (existing.phone || null) !== (expected.phone || null) ||
    !sameJson(existing.metadata, expected.metadata)
  ) {
    throw new Error(`Existing contact conflicts with import source for ${expected.externalId}`);
  }
}

function assertExistingConversationMatches(existing, expected, contactId) {
  if (existing.contactId !== contactId || existing.channel !== expected.channel) {
    throw new Error(`Existing conversation conflicts with import source for ${expected.externalThreadId}`);
  }
}

function assertExistingMessageMatches(existing, expected) {
  if (
    existing.direction !== expected.direction ||
    existing.senderType !== expected.senderType ||
    existing.body !== expected.body ||
    !sameJson(existing.metadata, expected.metadata)
  ) {
    throw new Error(`Existing message conflicts with import source for ${expected.externalMessageId}`);
  }
}

async function importMappedChat(tx, mapped, summary) {
  const contacts = createContactsRepository(tx);
  const conversations = createConversationsRepository(tx);

  let contact = await findContactByExternalId(tx, mapped.contact.externalId);
  if (contact) {
    assertExistingContactMatches(contact, mapped.contact);
    summary.contactsReused += 1;
  } else {
    contact = await contacts.create(mapped.contact);
    summary.contactsCreated += 1;
  }

  let conversation = await conversations.findByExternalThreadId(mapped.conversation.externalThreadId);
  if (conversation) {
    assertExistingConversationMatches(conversation, mapped.conversation, contact.id);
    summary.conversationsReused += 1;
  } else {
    conversation = await conversations.create({
      contactId: contact.id,
      channel: mapped.conversation.channel,
      externalThreadId: mapped.conversation.externalThreadId,
    });
    summary.conversationsCreated += 1;
  }

  const existingMessages = await conversations.listMessages(conversation.id);
  const byExternalId = new Map();
  for (const existing of existingMessages) {
    if (!existing.externalMessageId) continue;
    if (byExternalId.has(existing.externalMessageId)) {
      throw new Error(`Ambiguous existing message for ${existing.externalMessageId}`);
    }
    byExternalId.set(existing.externalMessageId, existing);
  }

  for (const message of mapped.messages) {
    const existing = byExternalId.get(message.externalMessageId);
    if (existing) {
      assertExistingMessageMatches(existing, message);
      summary.messagesReused += 1;
      continue;
    }
    await conversations.addMessage(conversation.id, message);
    summary.messagesCreated += 1;
  }
}

export function createLegacyChatImportCheckpoint({ chats, tenantId, nextIndex = 0 } = {}) {
  if (typeof tenantId !== 'string' || !UUID_PATTERN.test(tenantId)) {
    throw new TypeError('tenantId is required and must be a UUID');
  }
  const mappedChats = prepareChats(chats);
  if (!Number.isInteger(nextIndex) || nextIndex < 0 || nextIndex > mappedChats.length) {
    throw new TypeError('nextIndex must be an integer within the source chat range');
  }
  return buildCheckpoint(mappedChats, tenantId, nextIndex);
}

export async function importLegacyChats({
  chats,
  tenantId,
  storage,
  dryRun = false,
  checkpoint,
  onCheckpoint,
} = {}) {
  if (typeof tenantId !== 'string' || !UUID_PATTERN.test(tenantId)) {
    throw new TypeError('tenantId is required and must be a UUID');
  }
  if (onCheckpoint !== undefined && typeof onCheckpoint !== 'function') {
    throw new TypeError('onCheckpoint must be a function when provided');
  }

  const mappedChats = prepareChats(chats);
  const startIndex = resolveStartIndex(checkpoint, mappedChats, tenantId);
  const summary = buildSummary(mappedChats);

  if (dryRun) {
    return Object.freeze({ ...summary, dryRun: true });
  }
  if (!storage || typeof storage.withTenantTransaction !== 'function') {
    throw new TypeError('PostgreSQL storage with withTenantTransaction() is required');
  }
  if (typeof storage.withSessionAdvisoryLock !== 'function') {
    throw new TypeError('PostgreSQL storage with withSessionAdvisoryLock() is required');
  }

  return storage.withSessionAdvisoryLock(importLockKey(mappedChats, tenantId), async () => {
    for (let index = startIndex; index < mappedChats.length; index += 1) {
      await storage.withTenantTransaction(tenantId, async tx => {
        await importMappedChat(tx, mappedChats[index], summary);
      });

      if (onCheckpoint) {
        await onCheckpoint(buildCheckpoint(mappedChats, tenantId, index + 1));
      }
    }

    return Object.freeze({ ...summary, dryRun: false });
  });
}
