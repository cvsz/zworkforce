const STORAGE_KEYS = {
  activeConversationId: "zchat.activeConversationId",
  conversationId: "zchat.conversationId",
  conversations: "zchat.conversations",
  model: "zchat.model",
  messages: "zchat.messages",
  promptTemplates: "zchat.promptTemplates",
  themeMode: "zchat.themeMode",
  systemPrompt: "zchat.systemPrompt",
  sessionStartedAt: "zchat.sessionStartedAt",
};

const IMPORT_LIMITS = Object.freeze({
  maxMessages: 1000,
  maxMessageCharacters: 1_000_000,
  maxTotalCharacters: 5_000_000,
  maxSystemPromptCharacters: 16_000,
  maxTitleCharacters: 200,
  maxModelCharacters: 200,
});

const DEFAULT_PROMPT_TEMPLATES = [
  {
    id: "summarize",
    title: "Summarize",
    prompt: "Summarize the most important points in bullet form.",
    builtIn: true,
  },
  {
    id: "review",
    title: "Code review",
    prompt: "Review this for correctness, security, and edge cases.",
    builtIn: true,
  },
  {
    id: "rewrite",
    title: "Rewrite",
    prompt: "Rewrite this for clarity and brevity without losing meaning.",
    builtIn: true,
  },
];

function safeJsonParse(value, fallback) {
  if (typeof value !== "string" || !value.trim()) return fallback;
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function toTimestamp(value, fallback = Date.now()) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function normalizeText(text) {
  return String(text ?? "").replace(/\s+/g, " ").trim();
}

function summarizeMessage(message) {
  const content = normalizeText(message?.content);
  if (!content) return "";
  return content.length > 64 ? `${content.slice(0, 64).trimEnd()}…` : content;
}

function truncateTemplatePrompt(prompt) {
  const content = normalizeText(prompt);
  if (!content) return "";
  return content.length > 96 ? `${content.slice(0, 96).trimEnd()}…` : content;
}

const THEME_MODES = new Set(["system", "light", "dark"]);

function normalizeThemeMode(value) {
  return THEME_MODES.has(value) ? value : "system";
}

export function summarizeConversation(conversation) {
  const messages = Array.isArray(conversation?.messages) ? conversation.messages : [];
  const firstUserMessage = messages.find((message) => message?.role === "user" && normalizeText(message.content));
  const firstMessage = firstUserMessage || messages.find((message) => normalizeText(message.content));
  const title = normalizeText(conversation?.title) || summarizeMessage(firstMessage) || "New chat";
  const preview = summarizeMessage(messages[messages.length - 1]) || "No messages yet";

  return {
    id: conversation?.id || conversation?.conversationId || "",
    title,
    preview,
    model: typeof conversation?.model === "string" ? conversation.model : "",
    systemPrompt: typeof conversation?.systemPrompt === "string" ? conversation.systemPrompt : "",
    draft: typeof conversation?.draft === "string" ? conversation.draft : "",
    messageCount: messages.length,
    createdAt: toTimestamp(conversation?.createdAt),
    updatedAt: toTimestamp(conversation?.updatedAt),
    messages,
  };
}

function normalizeMessage(message) {
  return {
    id: typeof message?.id === "string" && message.id ? message.id : crypto.randomUUID(),
    role: message?.role === "assistant" ? "assistant" : "user",
    content: typeof message?.content === "string" ? message.content : "",
    createdAt: toTimestamp(message?.createdAt),
    pending: Boolean(message?.pending),
    error: Boolean(message?.error),
  };
}

export function createConversation(now = Date.now(), randomId = crypto.randomUUID, overrides = {}) {
  const id = typeof overrides.id === "string" && overrides.id ? overrides.id : randomId();
  return {
    id,
    title: typeof overrides.title === "string" && overrides.title.trim() ? overrides.title.trim() : "New chat",
    model: typeof overrides.model === "string" ? overrides.model : "",
    systemPrompt: typeof overrides.systemPrompt === "string" ? overrides.systemPrompt : "",
    draft: typeof overrides.draft === "string" ? overrides.draft : "",
    messages: Array.isArray(overrides.messages) ? overrides.messages.map(normalizeMessage) : [],
    createdAt: toTimestamp(overrides.createdAt, now),
    updatedAt: toTimestamp(overrides.updatedAt, now),
  };
}

export function createPromptTemplate(now = Date.now(), randomId = crypto.randomUUID, overrides = {}) {
  const id = typeof overrides.id === "string" && overrides.id ? overrides.id : randomId();
  const title = normalizeText(overrides.title) || "Untitled prompt";
  const prompt = typeof overrides.prompt === "string" ? overrides.prompt.trim() : "";
  return {
    id,
    title,
    prompt,
    preview: truncateTemplatePrompt(prompt),
    builtIn: Boolean(overrides.builtIn),
    createdAt: toTimestamp(overrides.createdAt, now),
    updatedAt: toTimestamp(overrides.updatedAt, now),
  };
}

function normalizePromptTemplate(template, now = Date.now(), randomId = crypto.randomUUID) {
  return createPromptTemplate(now, randomId, {
    id: template?.id,
    title: template?.title,
    prompt: template?.prompt,
    builtIn: template?.builtIn,
    createdAt: template?.createdAt,
    updatedAt: template?.updatedAt,
  });
}

function defaultPromptTemplates(now = Date.now(), randomId = crypto.randomUUID) {
  return DEFAULT_PROMPT_TEMPLATES.map((template) => createPromptTemplate(now, randomId, template));
}

function normalizeConversation(conversation, now = Date.now(), randomId = crypto.randomUUID) {
  return createConversation(now, randomId, {
    id: conversation?.id || conversation?.conversationId,
    title: conversation?.title,
    model: conversation?.model,
    systemPrompt: conversation?.systemPrompt,
    draft: conversation?.draft,
    messages: conversation?.messages,
    createdAt: conversation?.createdAt,
    updatedAt: conversation?.updatedAt,
  });
}

function sortConversations(conversations) {
  return [...conversations].sort((left, right) => {
    if (right.updatedAt !== left.updatedAt) return right.updatedAt - left.updatedAt;
    if (right.createdAt !== left.createdAt) return right.createdAt - left.createdAt;
    return left.id.localeCompare(right.id);
  });
}

function materializeState(state, now = Date.now(), randomId = crypto.randomUUID) {
  const hadConversationRecords = Array.isArray(state?.conversations) && state.conversations.length > 0;
  let conversations = Array.isArray(state?.conversations)
    ? state.conversations.map((conversation) => normalizeConversation(conversation, now, randomId))
    : [];

  const legacyMessages = Array.isArray(state?.messages)
    ? state.messages.map((message) => normalizeMessage(message))
    : [];

  if (!conversations.length) {
    const fallbackId = typeof state?.activeConversationId === "string" && state.activeConversationId
      ? state.activeConversationId
      : typeof state?.conversationId === "string" && state.conversationId
        ? state.conversationId
        : randomId();
    conversations = [createConversation(now, randomId, {
      id: fallbackId,
      model: typeof state?.model === "string" ? state.model : "",
      messages: legacyMessages,
      createdAt: state?.sessionStartedAt,
      updatedAt: state?.sessionStartedAt,
    })];
  }

  const activeConversationId = typeof state?.activeConversationId === "string" && state.activeConversationId
    ? state.activeConversationId
    : typeof state?.conversationId === "string" && state.conversationId
      ? state.conversationId
      : conversations[0].id;

  const activeConversation = conversations.find((conversation) => conversation.id === activeConversationId) || conversations[0];
  const activeModel = typeof state?.model === "string" && state.model
    ? state.model
    : activeConversation.model;
  const activeSystemPrompt = typeof state?.systemPrompt === "string" && state.systemPrompt.trim()
    ? state.systemPrompt
    : activeConversation.systemPrompt;
  const activeDraft = typeof state?.draft === "string" ? state.draft : activeConversation.draft;
  const activeMessages = !hadConversationRecords && Array.isArray(state?.messages) && state.messages.length
    ? legacyMessages
    : activeConversation.messages;
  const resolvedConversations = conversations.map((conversation) => {
    if (conversation.id !== activeConversation.id) return conversation;
    return {
      ...conversation,
      model: activeModel,
      systemPrompt: activeSystemPrompt,
      draft: activeDraft,
      messages: activeMessages,
    };
  });
  const sortedConversations = sortConversations(resolvedConversations);

  return {
    activeConversationId: activeConversation.id,
    conversationId: activeConversation.id,
    sessionStartedAt: typeof state?.sessionStartedAt === "string" && state.sessionStartedAt ? state.sessionStartedAt : String(now),
    model: activeModel,
    systemPrompt: activeSystemPrompt,
    draft: activeDraft,
    messages: activeMessages,
    conversations: sortedConversations,
  };
}

function migrateLegacyState(storage, now = Date.now(), randomId = crypto.randomUUID) {
  const legacyMessages = safeJsonParse(storage.getItem(STORAGE_KEYS.messages), []);
  const conversation = createConversation(now, randomId, {
    id: storage.getItem(STORAGE_KEYS.conversationId) || storage.getItem(STORAGE_KEYS.activeConversationId),
    model: storage.getItem(STORAGE_KEYS.model) || "",
    systemPrompt: storage.getItem(STORAGE_KEYS.systemPrompt) || "",
    messages: Array.isArray(legacyMessages) ? legacyMessages : [],
    createdAt: toTimestamp(storage.getItem(STORAGE_KEYS.sessionStartedAt), now),
    updatedAt: now,
  });

  return materializeState({
    activeConversationId: conversation.id,
    sessionStartedAt: storage.getItem(STORAGE_KEYS.sessionStartedAt) || String(now),
    systemPrompt: conversation.systemPrompt,
    conversations: [conversation],
  }, now, randomId);
}

export function loadPromptTemplates(storage, now = Date.now(), randomId = crypto.randomUUID) {
  const parsed = safeJsonParse(storage.getItem(STORAGE_KEYS.promptTemplates), null);
  if (!Array.isArray(parsed) || parsed.length === 0) {
    return defaultPromptTemplates(now, randomId);
  }
  return parsed.map((template) => normalizePromptTemplate(template, now, randomId));
}

export function loadThemeMode(storage) {
  return normalizeThemeMode(storage.getItem(STORAGE_KEYS.themeMode));
}

export function persistPromptTemplates(storage, templates) {
  const normalized = Array.isArray(templates) ? templates.map((template) => normalizePromptTemplate(template)) : [];
  storage.setItem(STORAGE_KEYS.promptTemplates, JSON.stringify(normalized));
}

export function persistThemeMode(storage, themeMode) {
  storage.setItem(STORAGE_KEYS.themeMode, normalizeThemeMode(themeMode));
}

export function addPromptTemplate(templates, template, now = Date.now(), randomId = crypto.randomUUID) {
  const normalized = normalizePromptTemplate(template, now, randomId);
  return [normalized, ...(Array.isArray(templates) ? templates : []).filter((item) => item.id !== normalized.id)];
}

export function removePromptTemplate(templates, templateId) {
  return (Array.isArray(templates) ? templates : []).filter((template) => template.id !== templateId);
}

export function updatePromptTemplate(templates, templateId, updates = {}, now = Date.now(), randomId = crypto.randomUUID) {
  return (Array.isArray(templates) ? templates : []).map((template) => {
    if (template.id !== templateId) return normalizePromptTemplate(template, now, randomId);
    return normalizePromptTemplate({
      ...template,
      ...updates,
      updatedAt: now,
    }, now, randomId);
  });
}

function withActiveConversation(state, updater, now = Date.now(), randomId = crypto.randomUUID) {
  const normalized = materializeState(state, now, randomId);
  let updatedActiveConversation;
  const nextConversations = normalized.conversations.map((conversation) => {
    if (conversation.id !== normalized.activeConversationId) return conversation;
    updatedActiveConversation = normalizeConversation(updater(conversation), now, randomId);
    return updatedActiveConversation;
  });

  return materializeState({
    ...normalized,
    model: updatedActiveConversation?.model ?? normalized.model,
    systemPrompt: updatedActiveConversation?.systemPrompt ?? normalized.systemPrompt,
    draft: updatedActiveConversation?.draft ?? normalized.draft,
    conversations: nextConversations,
  }, now, randomId);
}

function updateConversationById(state, conversationId, updater, now = Date.now(), randomId = crypto.randomUUID) {
  const normalized = materializeState(state, now, randomId);
  const nextConversations = normalized.conversations.map((conversation) => {
    if (conversation.id !== conversationId) return conversation;
    return normalizeConversation(updater(conversation), now, randomId);
  });

  return materializeState({
    ...normalized,
    conversations: nextConversations,
  }, now, randomId);
}

export function createChatState(now = Date.now(), randomId = crypto.randomUUID) {
  const conversationId = randomId();
  return materializeState({
    activeConversationId: conversationId,
    conversationId,
    sessionStartedAt: String(now),
    conversations: [createConversation(now, randomId, { id: conversationId })],
  }, now, randomId);
}

export function loadChatState(storage, now = Date.now(), randomId = crypto.randomUUID) {
  const conversations = safeJsonParse(storage.getItem(STORAGE_KEYS.conversations), null);
  if (Array.isArray(conversations) && conversations.length > 0) {
    return materializeState({
      activeConversationId: storage.getItem(STORAGE_KEYS.activeConversationId) || storage.getItem(STORAGE_KEYS.conversationId) || conversations[0]?.id,
      sessionStartedAt: storage.getItem(STORAGE_KEYS.sessionStartedAt) || String(now),
      draft: undefined,
      conversations,
    }, now, randomId);
  }

  return migrateLegacyState(storage, now, randomId);
}

export function persistChatState(storage, state) {
  const normalized = materializeState(state);
  storage.setItem(STORAGE_KEYS.activeConversationId, normalized.activeConversationId);
  storage.setItem(STORAGE_KEYS.conversationId, normalized.conversationId);
  storage.setItem(STORAGE_KEYS.sessionStartedAt, normalized.sessionStartedAt);
  storage.setItem(STORAGE_KEYS.model, normalized.model || "");
  storage.setItem(STORAGE_KEYS.systemPrompt, normalized.systemPrompt || "");
  storage.setItem(STORAGE_KEYS.messages, JSON.stringify(normalized.messages));
  storage.setItem(STORAGE_KEYS.conversations, JSON.stringify(normalized.conversations));
}

export function clearChatState(storage, now = Date.now(), randomId = crypto.randomUUID) {
  const state = createChatState(now, randomId);
  persistChatState(storage, state);
  return state;
}

export function getActiveConversation(state) {
  const normalized = materializeState(state);
  return normalized.conversations.find((conversation) => conversation.id === normalized.activeConversationId) || normalized.conversations[0];
}

export function selectConversation(state, conversationId, now = Date.now(), randomId = crypto.randomUUID) {
  const normalized = materializeState(state, now, randomId);
  const selected = normalized.conversations.find((conversation) => conversation.id === conversationId);
  if (!selected) return normalized;

  return materializeState({
    ...normalized,
    activeConversationId: selected.id,
    model: selected.model,
    systemPrompt: selected.systemPrompt,
    draft: selected.draft,
  }, now, randomId);
}

export function startNewConversation(state, now = Date.now(), randomId = crypto.randomUUID) {
  const normalized = materializeState(state, now, randomId);
  const nextConversation = createConversation(now, randomId, {
    model: normalized.model,
    systemPrompt: normalized.systemPrompt,
  });
  return materializeState({
    ...normalized,
    activeConversationId: nextConversation.id,
    conversations: [nextConversation, ...normalized.conversations],
  }, now, randomId);
}

export function renameActiveConversation(state, conversationId, now = Date.now(), randomId = crypto.randomUUID) {
  const normalized = materializeState(state, now, randomId);
  if (!conversationId || conversationId === normalized.activeConversationId) {
    return normalized;
  }

  const nextConversations = normalized.conversations.map((conversation) => {
    if (conversation.id !== normalized.activeConversationId) return conversation;
    return {
      ...conversation,
      id: conversationId,
      updatedAt: now,
    };
  });

  return materializeState({
    ...normalized,
    activeConversationId: conversationId,
    conversations: nextConversations,
  }, now, randomId);
}

export function clearActiveConversation(state, now = Date.now(), randomId = crypto.randomUUID) {
  return withActiveConversation(state, (conversation) => ({
    ...conversation,
    title: "New chat",
    messages: [],
    draft: "",
    updatedAt: now,
  }), now, randomId);
}

export function appendMessage(state, message, now = Date.now(), randomId = crypto.randomUUID) {
  return withActiveConversation(state, (conversation) => {
    const nextMessages = [...conversation.messages, normalizeMessage(message)];
    const title = conversation.title === "New chat" && nextMessages.some((item) => item.role === "user")
      ? summarizeMessage(nextMessages.find((item) => item.role === "user"))
      : conversation.title;
    return {
      ...conversation,
      title: title || "New chat",
      messages: nextMessages,
      updatedAt: now,
    };
  }, now, randomId);
}

export function setActiveSystemPrompt(state, systemPrompt, now = Date.now(), randomId = crypto.randomUUID) {
  const normalizedPrompt = typeof systemPrompt === "string" ? systemPrompt : "";
  return withActiveConversation(state, (conversation) => ({
    ...conversation,
    systemPrompt: normalizedPrompt,
    updatedAt: now,
  }), now, randomId);
}

export function setActiveDraft(state, draft, now = Date.now(), randomId = crypto.randomUUID) {
  const normalizedDraft = typeof draft === "string" ? draft : "";
  return withActiveConversation(state, (conversation) => ({
    ...conversation,
    draft: normalizedDraft,
    updatedAt: now,
  }), now, randomId);
}

export function setActiveModel(state, model, now = Date.now(), randomId = crypto.randomUUID) {
  const normalizedModel = typeof model === "string" ? model : "";
  return withActiveConversation(state, (conversation) => ({
    ...conversation,
    model: normalizedModel,
    updatedAt: now,
  }), now, randomId);
}

export function setActiveConversationTitle(state, title, now = Date.now(), randomId = crypto.randomUUID) {
  const normalizedTitle = normalizeText(title) || "New chat";
  return withActiveConversation(state, (conversation) => ({
    ...conversation,
    title: normalizedTitle,
    updatedAt: now,
  }), now, randomId);
}

export function replaceMessage(state, messageId, updates, now = Date.now(), randomId = crypto.randomUUID) {
  return withActiveConversation(state, (conversation) => ({
    ...conversation,
    messages: conversation.messages.map((message) => (message.id === messageId ? {
      ...message,
      ...updates,
      createdAt: toTimestamp(updates?.createdAt, message.createdAt),
      pending: Boolean(updates?.pending ?? message.pending),
      error: Boolean(updates?.error ?? message.error),
    } : message)),
    updatedAt: now,
  }), now, randomId);
}

export function deleteMessage(state, messageId, now = Date.now(), randomId = crypto.randomUUID) {
  return withActiveConversation(state, (conversation) => ({
    ...conversation,
    messages: conversation.messages.filter((message) => message.id !== messageId),
    updatedAt: now,
  }), now, randomId);
}

export function deleteConversation(state, conversationId, now = Date.now(), randomId = crypto.randomUUID) {
  const normalized = materializeState(state, now, randomId);
  const remaining = normalized.conversations.filter((conversation) => conversation.id !== conversationId);
  if (remaining.length === normalized.conversations.length) return normalized;
  if (!remaining.length) return createChatState(now, randomId);

  const active = normalized.activeConversationId === conversationId ? remaining[0] : getActiveConversation(normalized);
  return materializeState({
    ...normalized,
    activeConversationId: active.id,
    model: active.model,
    systemPrompt: active.systemPrompt,
    draft: active.draft,
    conversations: remaining,
  }, now, randomId);
}

export function forkActiveConversation(state, throughMessageId, now = Date.now(), randomId = crypto.randomUUID) {
  const normalized = materializeState(state, now, randomId);
  const source = getActiveConversation(normalized);
  const throughIndex = source.messages.findIndex((message) => message.id === throughMessageId);
  if (throughIndex < 0) return normalized;

  const branch = createConversation(now, randomId, {
    title: `${source.title} (branch)`.slice(0, IMPORT_LIMITS.maxTitleCharacters),
    model: source.model,
    systemPrompt: source.systemPrompt,
    messages: source.messages.slice(0, throughIndex + 1).map((message) => ({ ...message })),
    createdAt: now,
    updatedAt: now,
  });
  return materializeState({
    ...normalized,
    activeConversationId: branch.id,
    model: branch.model,
    systemPrompt: branch.systemPrompt,
    draft: "",
    conversations: [branch, ...normalized.conversations],
  }, now, randomId);
}

export function lastUserMessage(messages) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index]?.role === "user") {
      return messages[index];
    }
  }
  return null;
}

export function activeConversationSummary(state) {
  return summarizeConversation(getActiveConversation(state));
}

export function conversationSummaries(state) {
  return materializeState(state).conversations.map((conversation) => summarizeConversation(conversation));
}

export function searchConversationSummaries(state, query) {
  const summaries = conversationSummaries(state);
  const terms = normalizeText(query).toLocaleLowerCase().split(" ").filter(Boolean);
  if (!terms.length) return summaries;

  return summaries.filter((summary) => {
    const searchableText = [
      summary.title,
      summary.preview,
      summary.model,
      summary.systemPrompt,
      ...summary.messages.map((message) => message?.content),
    ].map(normalizeText).join(" ").toLocaleLowerCase();
    return terms.every((term) => searchableText.includes(term));
  });
}

function formatExportStamp(timestamp) {
  return new Date(timestamp).toISOString();
}

export function conversationToExportData(conversation) {
  const normalized = summarizeConversation(conversation);
  return {
    schemaVersion: 1,
    id: normalized.id,
    title: normalized.title,
    model: normalized.model,
    systemPrompt: normalized.systemPrompt,
    createdAt: normalized.createdAt,
    updatedAt: normalized.updatedAt,
    messages: normalized.messages.map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
      createdAt: message.createdAt,
      pending: Boolean(message.pending),
      error: Boolean(message.error),
    })),
  };
}

export function importConversation(state, input, now = Date.now(), randomId = crypto.randomUUID) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("Conversation import must be a JSON object");
  }
  if (input.schemaVersion !== undefined && input.schemaVersion !== 1) {
    throw new Error("Unsupported conversation schema version");
  }
  if (!Array.isArray(input.messages) || input.messages.length > IMPORT_LIMITS.maxMessages) {
    throw new Error(`Conversation import supports at most ${IMPORT_LIMITS.maxMessages} messages`);
  }
  const title = typeof input.title === "string" ? input.title.trim() : "";
  const model = typeof input.model === "string" ? input.model.trim() : "";
  const systemPrompt = typeof input.systemPrompt === "string" ? input.systemPrompt : "";
  if (title.length > IMPORT_LIMITS.maxTitleCharacters) throw new Error("Conversation title is too long");
  if (model.length > IMPORT_LIMITS.maxModelCharacters) throw new Error("Conversation model is too long");
  if (systemPrompt.length > IMPORT_LIMITS.maxSystemPromptCharacters) throw new Error("System prompt is too long");

  let totalCharacters = systemPrompt.length;
  const messages = input.messages.map((message, index) => {
    if (!message || typeof message !== "object" || Array.isArray(message)) {
      throw new Error(`Message ${index + 1} must be an object`);
    }
    if (message.role !== "user" && message.role !== "assistant") {
      throw new Error(`Message ${index + 1} has an unsupported role`);
    }
    if (typeof message.content !== "string") {
      throw new Error(`Message ${index + 1} content must be a string`);
    }
    if (message.content.length > IMPORT_LIMITS.maxMessageCharacters) {
      throw new Error(`Message ${index + 1} is too large`);
    }
    totalCharacters += message.content.length;
    if (totalCharacters > IMPORT_LIMITS.maxTotalCharacters) {
      throw new Error("Conversation import is too large");
    }
    return {
      id: randomId(),
      role: message.role,
      content: message.content,
      createdAt: toTimestamp(message.createdAt, now),
      pending: false,
      error: false,
    };
  });

  const normalized = materializeState(state, now, randomId);
  const imported = createConversation(now, randomId, {
    title: title || "Imported chat",
    model,
    systemPrompt,
    messages,
    createdAt: toTimestamp(input.createdAt, now),
    updatedAt: now,
  });
  return materializeState({
    ...normalized,
    activeConversationId: imported.id,
    model: imported.model,
    systemPrompt: imported.systemPrompt,
    draft: "",
    conversations: [imported, ...normalized.conversations],
  }, now, randomId);
}

export function conversationToMarkdown(conversation) {
  const normalized = summarizeConversation(conversation);
  const lines = [
    `# ${normalized.title}`,
    "",
    `- Conversation ID: ${normalized.id || "unknown"}`,
    `- Model: ${normalized.model || "default"}`,
    `- Created: ${formatExportStamp(normalized.createdAt)}`,
    `- Updated: ${formatExportStamp(normalized.updatedAt)}`,
  ];

  if (normalized.systemPrompt) {
    lines.push("", "## System Prompt", "", normalized.systemPrompt.trim());
  }

  for (const message of normalized.messages) {
    lines.push(
      "",
      `## ${message.role === "assistant" ? "Assistant" : "User"}`,
      "",
      `- Message ID: ${message.id}`,
      `- Created: ${formatExportStamp(message.createdAt)}`,
      "",
      message.content || "",
    );
  }

  return lines.join("\n").trimEnd() + "\n";
}

export { IMPORT_LIMITS, STORAGE_KEYS };
