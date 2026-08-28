import assert from "node:assert/strict";
import test from "node:test";

import {
  STORAGE_KEYS,
  addPromptTemplate,
  activeConversationSummary,
  appendMessage,
  clearActiveConversation,
  clearChatState,
  conversationSummaries,
  createChatState,
  createPromptTemplate,
  conversationToExportData,
  conversationToMarkdown,
  deleteConversation,
  deleteMessage,
  forkActiveConversation,
  importConversation,
  lastUserMessage,
  loadChatState,
  loadPromptTemplates,
  persistChatState,
  persistPromptTemplates,
  loadThemeMode,
  removePromptTemplate,
  renameActiveConversation,
  searchConversationSummaries,
  selectConversation,
  startNewConversation,
  setActiveSystemPrompt,
  setActiveConversationTitle,
  setActiveDraft,
  setActiveModel,
  persistThemeMode,
} from "../public/chat-state.mjs";

function createStorage(entries = {}) {
  const store = new Map(Object.entries(entries));
  return {
    getItem(key) {
      return store.has(key) ? store.get(key) : null;
    },
    setItem(key, value) {
      store.set(key, String(value));
    },
    removeItem(key) {
      store.delete(key);
    },
    snapshot() {
      return Object.fromEntries(store.entries());
    },
  };
}

test("loadPromptTemplates seeds browser-local defaults when storage is empty", () => {
  const storage = createStorage();
  const templates = loadPromptTemplates(storage, 1700000000000, () => "template-default");

  assert.equal(templates.length, 3);
  assert.equal(templates[0].builtIn, true);
  assert.equal(templates[0].id, "summarize");
});

test("theme mode defaults to system and persists valid values only", () => {
  const storage = createStorage();

  assert.equal(loadThemeMode(storage), "system");
  persistThemeMode(storage, "dark");
  assert.equal(loadThemeMode(storage), "dark");

  persistThemeMode(storage, "neon");
  assert.equal(loadThemeMode(storage), "system");
});

test("prompt template helpers support save, remove, and persistence", () => {
  const storage = createStorage();
  const seeded = [
    createPromptTemplate(1700000000000, () => "template-1", {
      title: "Code review",
      prompt: "Review this file for security issues.",
    }),
  ];

  persistPromptTemplates(storage, seeded);
  const loaded = loadPromptTemplates(storage, 1700000000000, () => "ignored");
  assert.equal(loaded.length, 1);
  assert.equal(loaded[0].title, "Code review");
  assert.equal(loaded[0].preview, "Review this file for security issues.");

  const extended = addPromptTemplate(loaded, {
    id: "template-2",
    title: "Summarize",
    prompt: "Summarize the proposal in bullets.",
  }, 1700000000100, () => "ignored");
  assert.equal(extended.length, 2);
  assert.equal(extended[0].id, "template-2");

  const removed = removePromptTemplate(extended, "template-1");
  assert.equal(removed.length, 1);
  assert.equal(removed[0].id, "template-2");
});

test("conversation export helpers produce markdown and JSON-safe data", () => {
  const state = appendMessage(
    appendMessage(
      setActiveSystemPrompt(createChatState(1700000000000, () => "conversation-1"), "Be concise.", 1700000000100),
      { id: "1", role: "user", content: "hello" },
      1700000000200,
    ),
    { id: "2", role: "assistant", content: "hi" },
    1700000000300,
  );

  const markdown = conversationToMarkdown(state);
  assert.ok(markdown.includes("# hello"));
  assert.ok(markdown.includes("## System Prompt"));
  assert.ok(markdown.includes("Be concise."));
  assert.ok(markdown.includes("## Assistant"));

  const data = conversationToExportData(state);
  assert.equal(data.schemaVersion, 1);
  assert.equal(data.id, "conversation-1");
  assert.equal(data.systemPrompt, "Be concise.");
  assert.equal(data.messages.length, 2);
  assert.equal(data.messages[0].role, "user");
});

test("conversation model and draft remain isolated when switching chats", () => {
  let state = setActiveModel(createChatState(1700000000000, () => "conversation-1"), "gateway:model-a", 1700000000100);
  state = setActiveDraft(state, "unfinished first prompt", 1700000000200);
  state = startNewConversation(state, 1700000000300, () => "conversation-2");
  state = setActiveModel(state, "gateway:model-b", 1700000000400);
  state = setActiveDraft(state, "unfinished second prompt", 1700000000500);

  const first = selectConversation(state, "conversation-1", 1700000000600);
  assert.equal(first.model, "gateway:model-a");
  assert.equal(first.draft, "unfinished first prompt");

  const second = selectConversation(first, "conversation-2", 1700000000700);
  assert.equal(second.model, "gateway:model-b");
  assert.equal(second.draft, "unfinished second prompt");
});

test("createChatState seeds one conversation with matching active id", () => {
  const state = createChatState(1700000000000, () => "conversation-1");

  assert.equal(state.activeConversationId, "conversation-1");
  assert.equal(state.conversationId, "conversation-1");
  assert.equal(state.sessionStartedAt, "1700000000000");
  assert.equal(state.systemPrompt, "");
  assert.equal(state.conversations.length, 1);
  assert.equal(state.conversations[0].id, "conversation-1");
});

test("loadChatState hydrates persisted conversation history and selection", () => {
  const storage = createStorage({
    [STORAGE_KEYS.activeConversationId]: "conversation-2",
    [STORAGE_KEYS.sessionStartedAt]: "1700000000000",
    [STORAGE_KEYS.conversations]: JSON.stringify([
      {
        id: "conversation-1",
        title: "First chat",
        model: "hf:first",
        systemPrompt: "Always answer briefly.",
        messages: [{ id: "1", role: "user", content: "hello" }],
        createdAt: 1700000000000,
        updatedAt: 1700000000100,
      },
      {
        id: "conversation-2",
        title: "Second chat",
        model: "hf:second",
        systemPrompt: "Answer as a reviewer.",
        messages: [{ id: "2", role: "assistant", content: "hi" }],
        createdAt: 1700000000200,
        updatedAt: 1700000000300,
      },
    ]),
  });

  const state = loadChatState(storage, 1700000001000, () => "ignored");
  assert.equal(state.activeConversationId, "conversation-2");
  assert.equal(state.messages.length, 1);
  assert.equal(state.model, "hf:second");
  assert.equal(state.systemPrompt, "Answer as a reviewer.");
  assert.equal(activeConversationSummary(state).title, "Second chat");
  assert.equal(conversationSummaries(state)[0].id, "conversation-2");
});

test("legacy storage hydrates into the active conversation", () => {
  const storage = createStorage({
    [STORAGE_KEYS.conversationId]: "conversation-1",
    [STORAGE_KEYS.sessionStartedAt]: "1700000000000",
    [STORAGE_KEYS.model]: "hf:test",
    [STORAGE_KEYS.messages]: JSON.stringify([{ id: "1", role: "user", content: "hello" }]),
  });

  const state = loadChatState(storage, 1700000001000, () => "ignored");
  assert.equal(state.activeConversationId, "conversation-1");
  assert.equal(state.conversations.length, 1);
  assert.equal(state.messages.length, 1);
  assert.equal(state.model, "hf:test");
  assert.equal(state.systemPrompt, "");
});

test("persistChatState writes active conversation and history records", () => {
  const storage = createStorage();
  const state = appendMessage(
    appendMessage(createChatState(1700000000000, () => "conversation-1"), { id: "1", role: "user", content: "hello" }, 1700000000100),
    { id: "2", role: "assistant", content: "hi" },
    1700000000200,
  );

  persistChatState(storage, {
    ...state,
    model: "hf:test",
    systemPrompt: "Be concise.",
  });

  const snapshot = storage.snapshot();
  assert.equal(snapshot[STORAGE_KEYS.activeConversationId], "conversation-1");
  assert.equal(snapshot[STORAGE_KEYS.model], "hf:test");
  assert.equal(snapshot[STORAGE_KEYS.systemPrompt], "Be concise.");
  assert.ok(snapshot[STORAGE_KEYS.messages].includes("assistant"));
  assert.ok(snapshot[STORAGE_KEYS.conversations].includes("conversation-1"));
});

test("history helpers preserve selection and support new chat and clearing", () => {
  const seeded = appendMessage(
    appendMessage(createChatState(1700000000000, () => "conversation-1"), { id: "1", role: "user", content: "hello there" }, 1700000000100),
    { id: "2", role: "assistant", content: "hi" },
    1700000000200,
  );

  const rotated = startNewConversation(seeded, 1700000000500, () => "conversation-2");
  assert.equal(rotated.activeConversationId, "conversation-2");
  assert.equal(conversationSummaries(rotated)[0].id, "conversation-2");
  assert.equal(conversationSummaries(rotated)[1].title, "hello there");
  assert.equal(rotated.systemPrompt, "");

  const restored = selectConversation(rotated, "conversation-1");
  assert.equal(restored.activeConversationId, "conversation-1");
  assert.equal(lastUserMessage(restored.messages).content, "hello there");

  const cleared = clearActiveConversation(restored, 1700000000600, () => "conversation-3");
  assert.equal(cleared.activeConversationId, "conversation-1");
  assert.equal(cleared.messages.length, 0);
  assert.equal(activeConversationSummary(cleared).title, "New chat");
});

test("message deletion, conversation branching, and conversation deletion are immutable", () => {
  const source = appendMessage(
    appendMessage(
      appendMessage(createChatState(1700000000000, () => "conversation-1"), { id: "m1", role: "user", content: "first" }, 1700000000100),
      { id: "m2", role: "assistant", content: "second" },
      1700000000200,
    ),
    { id: "m3", role: "user", content: "third" },
    1700000000300,
  );

  const withoutMiddle = deleteMessage(source, "m2", 1700000000400);
  assert.deepEqual(withoutMiddle.messages.map(({ id }) => id), ["m1", "m3"]);
  assert.deepEqual(source.messages.map(({ id }) => id), ["m1", "m2", "m3"]);

  const branched = forkActiveConversation(source, "m2", 1700000000500, () => "conversation-2");
  assert.equal(branched.activeConversationId, "conversation-2");
  assert.deepEqual(branched.messages.map(({ id }) => id), ["m1", "m2"]);
  assert.equal(branched.conversations.length, 2);

  const remaining = deleteConversation(branched, "conversation-2", 1700000000600, () => "unused");
  assert.equal(remaining.activeConversationId, "conversation-1");
  assert.equal(remaining.conversations.length, 1);

  const reset = deleteConversation(remaining, "conversation-1", 1700000000700, () => "conversation-3");
  assert.equal(reset.activeConversationId, "conversation-3");
  assert.equal(reset.conversations.length, 1);
});

test("conversation import validates schema, limits, roles, and regenerates ids", () => {
  let nextId = 0;
  const randomId = () => `generated-${++nextId}`;
  const initial = createChatState(1700000000000, randomId);
  const imported = importConversation(initial, {
    schemaVersion: 1,
    id: "untrusted-conversation-id",
    title: "Imported release review",
    model: "gateway:safe-model",
    systemPrompt: "Review release evidence.",
    messages: [
      { id: "untrusted-message-id", role: "user", content: "Check SHA", pending: true },
      { role: "assistant", content: "Verified", error: true },
    ],
  }, 1700000000100, randomId);

  assert.notEqual(imported.activeConversationId, "untrusted-conversation-id");
  assert.deepEqual(imported.messages.map(({ role }) => role), ["user", "assistant"]);
  assert.ok(imported.messages.every((message) => !message.pending && !message.error));
  assert.ok(imported.messages.every((message) => message.id.startsWith("generated-")));
  assert.equal(imported.model, "gateway:safe-model");

  assert.throws(() => importConversation(initial, { schemaVersion: 2, messages: [] }), /Unsupported/);
  assert.throws(() => importConversation(initial, { messages: [{ role: "system", content: "unsafe" }] }), /unsupported role/);
  assert.throws(() => importConversation(initial, { messages: Array.from({ length: 1001 }, () => ({ role: "user", content: "x" })) }), /at most 1000/);
  assert.throws(() => importConversation(initial, { messages: [{ role: "user", content: "x".repeat(1_000_001) }] }), /too large/);
});

test("conversation search matches all user-visible conversation fields", () => {
  const first = appendMessage(
    setActiveSystemPrompt(createChatState(1700000000000, () => "conversation-1"), "Act as a security reviewer."),
    { id: "1", role: "user", content: "Inspect the payment gateway" },
    1700000000100,
  );
  const second = startNewConversation(first, 1700000000200, () => "conversation-2");
  const state = {
    ...appendMessage(second, { id: "2", role: "assistant", content: "Deployment is healthy" }, 1700000000300),
    model: "gemini:flash",
  };

  assert.deepEqual(searchConversationSummaries(state, "security payment").map(({ id }) => id), ["conversation-1"]);
  assert.deepEqual(searchConversationSummaries(state, "deployment healthy").map(({ id }) => id), ["conversation-2"]);
  assert.deepEqual(searchConversationSummaries(state, "GEMINI").map(({ id }) => id), ["conversation-2"]);
  assert.deepEqual(searchConversationSummaries(state, "missing"), []);
  assert.equal(searchConversationSummaries(state, "  ").length, 2);
});

test("setActiveSystemPrompt persists with the active conversation", () => {
  const seeded = createChatState(1700000000000, () => "conversation-1");
  const updated = setActiveSystemPrompt(seeded, "Be precise.");

  assert.equal(updated.systemPrompt, "Be precise.");
  assert.equal(updated.conversations[0].systemPrompt, "Be precise.");
});

test("setActiveConversationTitle persists a manual conversation title", () => {
  const seeded = appendMessage(
    createChatState(1700000000000, () => "conversation-1"),
    { id: "1", role: "user", content: "hello" },
    1700000000100,
  );
  const updated = setActiveConversationTitle(seeded, "Project planning");

  assert.equal(updated.conversations[0].title, "Project planning");
  assert.equal(activeConversationSummary(updated).title, "Project planning");
});

test("manual conversation titles survive later message appends", () => {
  const seeded = setActiveConversationTitle(createChatState(1700000000000, () => "conversation-1"), "Project planning");
  const updated = appendMessage(seeded, { id: "1", role: "user", content: "new question" }, 1700000000100);

  assert.equal(updated.conversations[0].title, "Project planning");
  assert.equal(activeConversationSummary(updated).title, "Project planning");
});

test("renameActiveConversation rebases the active conversation id", () => {
  const seeded = appendMessage(
    appendMessage(createChatState(1700000000000, () => "conversation-1"), { id: "1", role: "user", content: "hello" }, 1700000000100),
    { id: "2", role: "assistant", content: "hi" },
    1700000000200,
  );

  const renamed = renameActiveConversation(seeded, "conversation-9");
  assert.equal(renamed.activeConversationId, "conversation-9");
  assert.equal(renamed.conversations[0].id, "conversation-9");
  assert.equal(renamed.messages.length, 2);
});

test("clearChatState resets browser storage to a fresh chat", () => {
  const storage = createStorage();
  const cleared = clearChatState(storage, 1700000000100, () => "conversation-2");

  assert.equal(cleared.activeConversationId, "conversation-2");
  assert.equal(storage.getItem(STORAGE_KEYS.messages), "[]");
  assert.ok(storage.getItem(STORAGE_KEYS.conversations).includes("conversation-2"));
});
