const CHANNELS = new Set(['line', 'whatsapp', 'messenger', 'tiktok', 'shopify']);
const SENDERS = new Set(['customer', 'agent']);

function optionalTrimmed(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function metadataValue(value, fallback) {
  return value === undefined ? fallback : structuredClone(value);
}

export function mapLegacyChatToNormalized(chat) {
  if (!chat || typeof chat !== 'object' || Array.isArray(chat)) {
    throw new TypeError('Legacy chat record is required');
  }
  if (!Number.isSafeInteger(chat.id) || chat.id <= 0) {
    throw new TypeError('Legacy chat id must be a positive integer');
  }

  const name = optionalTrimmed(chat.name);
  if (!name) throw new TypeError('Legacy chat name is required');
  if (typeof chat.channel !== 'string' || !CHANNELS.has(chat.channel)) {
    throw new TypeError('Legacy chat must use a supported channel');
  }
  if (!Array.isArray(chat.messages)) throw new TypeError('Legacy chat messages must be an array');
  if (chat.unread !== undefined && (!Number.isSafeInteger(chat.unread) || chat.unread < 0)) {
    throw new TypeError('Legacy chat unread count must be a non-negative integer');
  }

  const details = chat.details && typeof chat.details === 'object' && !Array.isArray(chat.details)
    ? chat.details
    : {};
  if (details.tags !== undefined && !Array.isArray(details.tags)) {
    throw new TypeError('Legacy chat tags must be an array');
  }
  if (details.orders !== undefined && !Array.isArray(details.orders)) {
    throw new TypeError('Legacy chat orders must be an array');
  }

  const stableId = `legacy-chat:${chat.id}`;
  const messages = chat.messages.map((message, index) => {
    if (!message || typeof message !== 'object' || Array.isArray(message)) {
      throw new TypeError('Legacy message record is required');
    }
    if (typeof message.sender !== 'string' || !SENDERS.has(message.sender)) {
      throw new TypeError('Legacy message must use a supported sender');
    }
    const body = optionalTrimmed(message.text);
    if (!body) throw new TypeError('Legacy message text is required');

    const metadata = {};
    const legacyTime = optionalTrimmed(message.time);
    if (legacyTime) metadata.legacyTime = legacyTime;

    return {
      direction: message.sender === 'customer' ? 'inbound' : 'outbound',
      senderType: message.sender,
      body,
      externalMessageId: `${stableId}:message:${index}`,
      metadata,
    };
  });

  const email = optionalTrimmed(details.email);
  const phone = optionalTrimmed(details.phone);
  const avatar = optionalTrimmed(chat.avatar);
  const assigned = optionalTrimmed(details.assigned);
  const displayTime = optionalTrimmed(chat.time);

  return {
    contact: {
      name,
      email: email ? email.toLowerCase() : null,
      phone,
      externalId: stableId,
      metadata: {
        legacyChatId: chat.id,
        avatar,
        assigned,
        tags: metadataValue(details.tags, []),
        orders: metadataValue(details.orders, []),
        unread: chat.unread ?? 0,
        displayTime,
      },
    },
    conversation: {
      channel: chat.channel,
      externalThreadId: stableId,
    },
    messages,
  };
}