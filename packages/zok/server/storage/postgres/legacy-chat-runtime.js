import { withRequestTransaction } from '../request-transaction.js';
import { createContactsRepository } from './contacts-repository.js';
import { createConversationsRepository } from './conversations-repository.js';

const SENDERS = new Set(['agent', 'customer', 'bot', 'system']);

function parseLegacyChatId(value) {
  if (!/^\d+$/.test(String(value))) return null;
  const id = Number(value);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

function normalizeMessageInput(input = {}) {
  const body = typeof input.text === 'string' ? input.text.trim() : '';
  if (!body) throw new TypeError('Message text is required');
  if (body.length > 4000) throw new TypeError('Message text exceeds 4000 characters');
  const sender = input.sender || 'agent';
  if (typeof sender !== 'string' || !SENDERS.has(sender)) {
    throw new TypeError('Invalid sender');
  }
  return {
    direction: sender === 'customer' ? 'inbound' : 'outbound',
    senderType: sender === 'bot' ? 'ai' : sender,
    body,
  };
}

function normalizeTags(tags) {
  if (!Array.isArray(tags) || tags.length > 32) {
    throw new TypeError('Tags must be an array of at most 32 items');
  }
  return tags.map(tag => {
    if (typeof tag !== 'string' || !tag.trim() || tag.trim().length > 80) {
      throw new TypeError('Each tag must be a non-empty string of at most 80 characters');
    }
    return tag.trim();
  });
}

function metadataFromContact(contact) {
  const metadata = contact?.metadata;
  if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) {
    throw new Error('PostgreSQL chat metadata is unavailable');
  }
  return metadata;
}

export function createLegacyChatRuntime({ storage } = {}) {
  if (!storage || typeof storage.withIdentityTransaction !== 'function') {
    throw new TypeError('PostgreSQL storage is required');
  }

  async function findState(tx, externalThreadId) {
    const conversations = createConversationsRepository(tx);
    const conversation = await conversations.findByExternalThreadId(externalThreadId);
    if (!conversation) return null;
    const contacts = createContactsRepository(tx);
    const contact = await contacts.findById(conversation.contactId);
    if (!contact) throw new Error('PostgreSQL chat contact is unavailable');
    return { conversations, conversation, contacts, contact };
  }

  async function read(request, legacyChatId) {
    const parsedId = parseLegacyChatId(legacyChatId);
    if (parsedId === null) throw new TypeError('Legacy chat id must be a positive integer');
    const externalThreadId = `legacy-chat:${parsedId}`;

    return withRequestTransaction(storage, request, async tx => {
      const state = await findState(tx, externalThreadId);
      if (!state) return null;
      const messages = await state.conversations.listMessages(state.conversation.id);
      return { conversation: state.conversation, messages, metadata: metadataFromContact(state.contact) };
    });
  }

  async function writeMessage(request, legacyChatId, input = {}) {
    const parsedId = parseLegacyChatId(legacyChatId);
    if (parsedId === null) throw new TypeError('Legacy chat id must be a positive integer');
    const messageInput = normalizeMessageInput(input);
    const externalThreadId = `legacy-chat:${parsedId}`;

    return withRequestTransaction(storage, request, async tx => {
      const conversations = createConversationsRepository(tx);
      const conversation = await conversations.findByExternalThreadId(externalThreadId);
      if (!conversation) return null;
      return conversations.addMessage(conversation.id, messageInput);
    });
  }

  async function markRead(request, legacyChatId) {
    const parsedId = parseLegacyChatId(legacyChatId);
    if (parsedId === null) throw new TypeError('Legacy chat id must be a positive integer');
    const externalThreadId = `legacy-chat:${parsedId}`;

    return withRequestTransaction(storage, request, async tx => {
      const state = await findState(tx, externalThreadId);
      if (!state) return null;
      const metadata = { ...metadataFromContact(state.contact), unread: 0 };
      const updated = await state.contacts.replaceMetadata(state.contact.id, metadata);
      return metadataFromContact(updated);
    });
  }

  async function replaceTags(request, legacyChatId, tags) {
    const parsedId = parseLegacyChatId(legacyChatId);
    if (parsedId === null) throw new TypeError('Legacy chat id must be a positive integer');
    const normalizedTags = normalizeTags(tags);
    const externalThreadId = `legacy-chat:${parsedId}`;

    return withRequestTransaction(storage, request, async tx => {
      const state = await findState(tx, externalThreadId);
      if (!state) return null;
      const metadata = { ...metadataFromContact(state.contact), tags: normalizedTags };
      const updated = await state.contacts.replaceMetadata(state.contact.id, metadata);
      return metadataFromContact(updated);
    });
  }

  async function touchMetadata(request, legacyChatId, patch = {}) {
    const parsedId = parseLegacyChatId(legacyChatId);
    if (parsedId === null) throw new TypeError('Legacy chat id must be a positive integer');
    const externalThreadId = `legacy-chat:${parsedId}`;

    return withRequestTransaction(storage, request, async tx => {
      const state = await findState(tx, externalThreadId);
      if (!state) return null;
      const metadata = { ...metadataFromContact(state.contact), ...patch };
      const updated = await state.contacts.replaceMetadata(state.contact.id, metadata);
      return metadataFromContact(updated);
    });
  }

  return Object.freeze({ read, writeMessage, markRead, replaceTags, touchMetadata });
}