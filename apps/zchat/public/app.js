import {
  activeConversationSummary,
  appendMessage,
  clearActiveConversation,
  clearChatState,
  conversationSummaries,
  conversationToExportData,
  conversationToMarkdown,
  deleteConversation,
  deleteMessage,
  forkActiveConversation,
  importConversation,
  addPromptTemplate,
  lastUserMessage,
  loadChatState,
  loadPromptTemplates,
  loadThemeMode,
  persistChatState,
  persistPromptTemplates,
  persistThemeMode,
  renameActiveConversation,
  replaceMessage,
  removePromptTemplate,
  searchConversationSummaries,
  selectConversation,
  startNewConversation,
  setActiveSystemPrompt,
  setActiveConversationTitle,
  setActiveDraft,
  setActiveModel,
} from "./chat-state.mjs";
import { renderMarkdownFragment } from "./markdown.mjs";
import { readEventStream } from "./chat-stream.mjs";

const transcript = document.querySelector("#transcript");
const historyList = document.querySelector("#history");
const historySearch = document.querySelector("#history-search");
const templatesList = document.querySelector("#templates");
const templateForm = document.querySelector("#template-form");
const templateTitle = document.querySelector("#template-title");
const templatePrompt = document.querySelector("#template-prompt");
const copyMarkdown = document.querySelector("#copy-markdown");
const downloadJson = document.querySelector("#download-json");
const importJson = document.querySelector("#import-json");
const importJsonFile = document.querySelector("#import-json-file");
const conversationTitle = document.querySelector("#conversation-title");
const themeToggle = document.querySelector("#theme-toggle");
const composer = document.querySelector("#composer");
const systemPrompt = document.querySelector("#system-prompt");
const model = document.querySelector("#model");
const prompt = document.querySelector("#prompt");
const stop = document.querySelector("#stop");
const send = document.querySelector("#send");
const retry = document.querySelector("#retry");
const clear = document.querySelector("#clear");
const newChat = document.querySelector("#new-chat");
const login = document.querySelector("#login");
const logout = document.querySelector("#logout");
const status = document.querySelector("#status");
const conversationLabel = document.querySelector("#conversation");
const emptyState = document.querySelector("#empty-state");
const loadOlder = document.querySelector("#load-older");

const storage = window.localStorage;

let state = loadChatState(storage);
let promptTemplates = loadPromptTemplates(storage);
let themeMode = loadThemeMode(storage);
let busy = false;
let activeGeneration = null;
let visibleMessageLimit = 100;
const themeQuery = window.matchMedia("(prefers-color-scheme: dark)");

function isAbortError(error) {
  return Boolean(error && typeof error === "object" && "name" in error && error.name === "AbortError");
}

function resolveTheme(mode) {
  if (mode === "dark" || mode === "light") return mode;
  return themeQuery.matches ? "dark" : "light";
}

function renderTheme() {
  const resolved = resolveTheme(themeMode);
  document.documentElement.dataset.theme = resolved;
  document.documentElement.style.colorScheme = resolved;
  themeToggle.textContent = resolved === "dark" ? "Light mode" : "Dark mode";
  themeToggle.setAttribute("aria-pressed", String(resolved === "dark"));
  themeToggle.setAttribute("aria-label", resolved === "dark" ? "Switch to light mode" : "Switch to dark mode");
}

function cycleThemeMode(mode) {
  if (mode === "system") return "dark";
  if (mode === "dark") return "light";
  return "system";
}

function applyThemeMode(nextMode) {
  themeMode = nextMode;
  persistThemeMode(storage, themeMode);
  renderTheme();
}

function setStatus(message, tone = "idle") {
  status.dataset.tone = tone;
  status.textContent = message;
}

function setBusy(nextBusy) {
  busy = nextBusy;
  stop.disabled = !nextBusy;
  send.disabled = nextBusy;
  retry.disabled = nextBusy || !lastUserMessage(state.messages);
  clear.disabled = nextBusy;
  newChat.disabled = nextBusy;
  copyMarkdown.disabled = nextBusy;
  downloadJson.disabled = nextBusy;
  importJson.disabled = nextBusy;
  conversationTitle.disabled = nextBusy;
  themeToggle.disabled = nextBusy;
  prompt.disabled = nextBusy;
  systemPrompt.disabled = nextBusy;
  templateForm.querySelectorAll("input, textarea, button").forEach((element) => {
    element.disabled = nextBusy;
  });
  model.disabled = nextBusy;
  historySearch.disabled = nextBusy;
  historyList.querySelectorAll("button").forEach((button) => {
    button.disabled = nextBusy;
  });
  transcript.querySelectorAll("button").forEach((button) => {
    button.disabled = nextBusy;
  });
}

function formatRole(role) {
  return role === "assistant" ? "ZChat" : "You";
}

function formatTimestamp(timestamp) {
  return new Date(timestamp).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderMessage(message) {
  const item = document.createElement("li");
  item.className = `message message--${message.role}${message.pending ? " is-pending" : ""}${message.error ? " is-error" : ""}`;
  item.dataset.role = message.role;
  item.id = message.id;

  const meta = document.createElement("div");
  meta.className = "message__meta";
  const role = document.createElement("span");
  role.className = "message__role";
  role.textContent = formatRole(message.role);
  const stamp = document.createElement("span");
  stamp.className = "message__stamp";
  stamp.textContent = new Date(message.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const actions = document.createElement("span");
  actions.className = "message__actions";

  const copyButton = document.createElement("button");
  copyButton.type = "button";
  copyButton.textContent = "Copy";
  copyButton.setAttribute("aria-label", `Copy ${formatRole(message.role)} message`);
  copyButton.disabled = busy || !message.content;
  copyButton.addEventListener("click", () => {
    if (!navigator.clipboard?.writeText) {
      setStatus("Clipboard access is unavailable", "error");
      return;
    }
    void navigator.clipboard.writeText(message.content).then(
      () => setStatus("Message copied", "ready"),
      () => setStatus("Unable to copy message", "error"),
    );
  });
  actions.append(copyButton);

  if (message.role === "user") {
    const reuseButton = document.createElement("button");
    reuseButton.type = "button";
    reuseButton.textContent = "Use as draft";
    reuseButton.setAttribute("aria-label", "Use this message as the current draft");
    reuseButton.disabled = busy || !message.content;
    reuseButton.addEventListener("click", () => {
      if (busy) return;
      state = setActiveDraft(state, message.content);
      persistChatState(storage, state);
      prompt.value = message.content;
      prompt.focus();
      setStatus("Message loaded as draft", "ready");
    });
    actions.append(reuseButton);
  }
  const branchButton = document.createElement("button");
  branchButton.type = "button";
  branchButton.textContent = "Branch";
  branchButton.setAttribute("aria-label", "Branch conversation through this message");
  branchButton.disabled = busy || message.pending;
  branchButton.addEventListener("click", () => {
    if (busy || message.pending) return;
    state = forkActiveConversation(state, message.id);
    visibleMessageLimit = 100;
    persistChatState(storage, state);
    render();
    setStatus("Conversation branch created", "ready");
  });
  actions.append(branchButton);

  const deleteButton = document.createElement("button");
  deleteButton.type = "button";
  deleteButton.textContent = "Delete";
  deleteButton.className = "is-danger";
  deleteButton.setAttribute("aria-label", `Delete ${formatRole(message.role)} message`);
  deleteButton.disabled = busy || message.pending;
  deleteButton.addEventListener("click", () => {
    if (busy || message.pending || !window.confirm("Delete this message from browser history?")) return;
    state = deleteMessage(state, message.id);
    persistChatState(storage, state);
    render();
    setStatus("Message deleted", "ready");
  });
  actions.append(deleteButton);
  meta.append(role, stamp, actions);

  const body = document.createElement(message.role === "assistant" ? "div" : "pre");
  body.className = "message__body";
  if (message.role === "assistant" && message.content) {
    body.classList.add("markdown");
    body.replaceChildren(renderMarkdownFragment(document, message.content));
  } else {
    body.textContent = message.content || (message.pending ? "Streaming..." : "");
  }

  item.append(meta, body);
  return item;
}

function renderHistoryItem(summary) {
  const item = document.createElement("li");
  item.className = "history__item";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "history__button";
  button.dataset.active = String(summary.id === state.activeConversationId);
  button.setAttribute("aria-pressed", String(summary.id === state.activeConversationId));
  button.setAttribute("aria-label", `${summary.title}. ${summary.preview}. ${summary.messageCount} messages.`);

  const title = document.createElement("span");
  title.className = "history__title";
  title.textContent = summary.title;

  const meta = document.createElement("span");
  meta.className = "history__meta";
  meta.textContent = `${summary.messageCount} message${summary.messageCount === 1 ? "" : "s"} · ${formatTimestamp(summary.updatedAt)}`;

  const preview = document.createElement("span");
  preview.className = "history__preview";
  preview.textContent = summary.preview;

  button.append(title, meta, preview);
  button.addEventListener("click", () => {
    if (busy || summary.id === state.activeConversationId) return;
    state = selectConversation(state, summary.id);
    persistChatState(storage, state);
    prompt.value = "";
    render();
    setStatus(`Switched to ${summary.title}`, "ready");
  });

  const deleteButton = document.createElement("button");
  deleteButton.type = "button";
  deleteButton.className = "history__delete";
  deleteButton.textContent = "Delete";
  deleteButton.setAttribute("aria-label", `Delete conversation ${summary.title}`);
  deleteButton.addEventListener("click", () => {
    if (busy || !window.confirm(`Delete ${summary.title} from this browser?`)) return;
    state = deleteConversation(state, summary.id);
    visibleMessageLimit = 100;
    persistChatState(storage, state);
    render();
    setStatus("Conversation deleted", "ready");
  });

  const row = document.createElement("div");
  row.className = "history__row";
  row.append(button, deleteButton);
  item.append(row);
  return item;
}

function renderHistory() {
  const allSummaries = conversationSummaries(state);
  const summaries = searchConversationSummaries(state, historySearch.value);
  if (!summaries.length) {
    const emptyItem = document.createElement("li");
    emptyItem.className = "history__empty";
    emptyItem.textContent = allSummaries.length ? "No chats match this search." : "No saved chats yet.";
    historyList.replaceChildren(emptyItem);
    return;
  }

  historyList.replaceChildren(...summaries.map(renderHistoryItem));
}

function renderTemplateItem(template) {
  const item = document.createElement("li");
  item.className = "template__item";

  const body = document.createElement("div");
  body.className = "template__body";

  const title = document.createElement("div");
  title.className = "template__title";
  title.textContent = template.title;

  const preview = document.createElement("div");
  preview.className = "template__preview";
  preview.textContent = template.preview || "No prompt text";

  body.append(title, preview);

  const actions = document.createElement("div");
  actions.className = "template__actions";

  const useButton = document.createElement("button");
  useButton.type = "button";
  useButton.textContent = "Use";
  useButton.addEventListener("click", () => {
    templatePrompt.value = template.prompt;
    templatePrompt.focus();
    setStatus(`Loaded ${template.title} into the template editor`, "ready");
  });

  const startButton = document.createElement("button");
  startButton.type = "button";
  startButton.textContent = "Start";
  startButton.addEventListener("click", () => {
    if (busy) return;
    state = startNewConversation(state);
    persistChatState(storage, state);
    prompt.value = "";
    render();
    void sendMessage(template.prompt);
  });

  actions.append(useButton, startButton);

  if (!template.builtIn) {
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.textContent = "Delete";
    deleteButton.className = "is-danger";
    deleteButton.addEventListener("click", () => {
      if (busy) return;
      promptTemplates = removePromptTemplate(promptTemplates, template.id);
      persistPromptTemplates(storage, promptTemplates);
      render();
      setStatus(`Removed ${template.title}`, "ready");
    });
    actions.append(deleteButton);
  }

  item.append(body, actions);
  return item;
}

function renderTemplates() {
  templatesList.replaceChildren(...promptTemplates.map(renderTemplateItem));
}

async function copyActiveConversationMarkdown() {
  const markdown = conversationToMarkdown(activeConversationSummary(state));
  if (!navigator.clipboard?.writeText) {
    throw new Error("Clipboard access is unavailable");
  }
  await navigator.clipboard.writeText(markdown);
  setStatus("Copied active conversation as markdown", "ready");
}

function downloadActiveConversationJson() {
  const exportData = conversationToExportData(activeConversationSummary(state));
  const blob = new Blob([`${JSON.stringify(exportData, null, 2)}\n`], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${exportData.id || "zchat-conversation"}.json`;
  anchor.rel = "noopener";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  setStatus("Downloaded active conversation as JSON", "ready");
}

function render() {
  const activeSummary = activeConversationSummary(state);
  const firstVisibleIndex = Math.max(0, state.messages.length - visibleMessageLimit);
  transcript.replaceChildren(...state.messages.slice(firstVisibleIndex).map(renderMessage));
  loadOlder.hidden = firstVisibleIndex === 0;
  loadOlder.textContent = firstVisibleIndex > 0 ? `Load ${Math.min(100, firstVisibleIndex)} older messages` : "Load older messages";
  emptyState.hidden = state.messages.length > 0;
  conversationLabel.textContent = activeSummary.title;
  conversationLabel.title = `${activeSummary.title} · ${activeSummary.messageCount} messages`;
  conversationTitle.value = activeSummary.title;
  systemPrompt.value = state.systemPrompt || "";
  prompt.value = state.draft || "";
  model.value = state.model;
  retry.disabled = busy || !lastUserMessage(state.messages);
  clear.disabled = busy || state.messages.length === 0;
  newChat.disabled = busy;
  if (state.messages.length) {
    transcript.scrollTop = transcript.scrollHeight;
  }
  renderHistory();
  renderTemplates();
  renderTheme();
}

function createMessage(role, content, overrides = {}) {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    createdAt: Date.now(),
    pending: overrides.pending ?? false,
    error: overrides.error ?? false,
  };
}

function syncConversationId(nextConversationId) {
  if (!nextConversationId || nextConversationId === state.activeConversationId) return;
  state = renameActiveConversation(state, nextConversationId);
  persistChatState(storage, state);
  conversationLabel.textContent = activeConversationSummary(state).title;
}

function readSelectedModel() {
  return model.value || state.model || "default";
}

async function loadModels() {
  try {
    const response = await fetch("/api/models");
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load models");

    const options = (data.data || []).map((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = item.id;
      return option;
    });

    model.replaceChildren(...options);

    const available = options.some((option) => option.value === state.model);
    if (!available && options.length) {
      state = {
        ...state,
        model: options[0].value,
      };
      persistChatState(storage, state);
    }

    model.value = state.model;
    setStatus(state.messages.length ? "Conversation ready" : "Ready", "ready");
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Model catalog unavailable", "error");
  }
}

async function completeWithFallback(assistantId, requestBase) {
  let streamedText = "";
  try {
    const streamResponse = await fetch("/api/chat/stream", requestBase);
    if (streamResponse.ok && streamResponse.body) {
      const conversationId = streamResponse.headers.get("x-conversation-id");
      if (conversationId) {
        syncConversationId(conversationId);
      }

      const finalText = await readEventStream(streamResponse, (_, fullText) => {
        streamedText = fullText;
        state = replaceMessage(state, assistantId, {
          content: fullText,
          pending: true,
          error: false,
        });
        persistChatState(storage, state);
        render();
      }, requestBase.signal);

      streamedText = finalText;
      state = replaceMessage(state, assistantId, {
        content: finalText,
        pending: false,
        error: false,
      });
      persistChatState(storage, state);
      render();

      if (requestBase.signal?.aborted) {
        setStatus("Generation stopped", "ready");
        return { stopped: true, content: finalText };
      }

      return { stopped: false, content: finalText };
    }

    const fallbackResponse = await fetch("/api/chat", requestBase);
    const fallbackData = await fallbackResponse.json();
    if (!fallbackResponse.ok) {
      throw new Error(fallbackData.error || "Request failed");
    }

    if (fallbackData.conversation_id) {
      syncConversationId(fallbackData.conversation_id);
    }

    state = replaceMessage(state, assistantId, {
      content: fallbackData.content || "",
      pending: false,
      error: false,
    });
    persistChatState(storage, state);
    render();

    if (requestBase.signal?.aborted) {
      setStatus("Generation stopped", "ready");
      return { stopped: true, content: fallbackData.content || "" };
    }

    return { stopped: false, content: fallbackData.content || "" };
  } catch (error) {
    if (isAbortError(error) || requestBase.signal?.aborted) {
      state = replaceMessage(state, assistantId, {
        content: streamedText,
        pending: false,
        error: false,
      });
      persistChatState(storage, state);
      render();
      setStatus("Generation stopped", "ready");
      return { stopped: true, content: streamedText };
    }
    throw error;
  }
}

async function sendMessage(promptText, { retrying = false } = {}) {
  if (busy) return;

  const trimmed = promptText.trim();
  if (!trimmed) {
    setStatus("Enter a message before sending", "error");
    return;
  }

  const userMessage = createMessage("user", trimmed);
  const assistantMessage = createMessage("assistant", "", { pending: true });
  const generation = new AbortController();

  state = setActiveDraft(state, "");
  state = appendMessage(state, userMessage);
  state = appendMessage(state, assistantMessage);
  persistChatState(storage, state);
  prompt.value = "";
  render();
  setBusy(true);
  setStatus(retrying ? "Retrying" : "Streaming", "busy");
  let requestSucceeded = false;
  activeGeneration = generation;

  try {
    const result = await completeWithFallback(assistantMessage.id, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-Started-At": state.sessionStartedAt,
        "X-Usage-Correlation-Id": state.activeConversationId,
      },
      body: JSON.stringify({
        model: readSelectedModel(),
        prompt: trimmed,
        system_prompt: state.systemPrompt || "",
        conversation_id: state.activeConversationId,
      }),
      signal: generation.signal,
    });
    requestSucceeded = !result.stopped;
  } catch (error) {
    state = replaceMessage(state, assistantMessage.id, {
      content: error instanceof Error ? error.message : "Request failed",
      pending: false,
      error: true,
    });
    persistChatState(storage, state);
    setStatus("Error", "error");
    render();
  } finally {
    activeGeneration = null;
    setBusy(false);
    if (requestSucceeded) {
      setStatus(state.messages.length ? "Conversation ready" : "Ready", "ready");
    }
  }
}

composer.addEventListener("submit", (event) => {
  event.preventDefault();
  void sendMessage(prompt.value);
});

stop.addEventListener("click", () => {
  if (!busy || !activeGeneration) return;
  activeGeneration.abort();
  setStatus("Stopping generation", "busy");
});

systemPrompt.addEventListener("input", () => {
  state = setActiveSystemPrompt(state, systemPrompt.value);
  persistChatState(storage, state);
});

prompt.addEventListener("input", () => {
  state = setActiveDraft(state, prompt.value);
  persistChatState(storage, state);
});

conversationTitle.addEventListener("input", () => {
  state = setActiveConversationTitle(state, conversationTitle.value);
  persistChatState(storage, state);
  conversationLabel.textContent = activeConversationSummary(state).title;
  conversationLabel.title = `${activeConversationSummary(state).title} · ${activeConversationSummary(state).messageCount} messages`;
  renderHistory();
});

themeToggle.addEventListener("click", () => {
  applyThemeMode(cycleThemeMode(themeMode));
});

themeQuery.addEventListener("change", () => {
  if (themeMode === "system") {
    renderTheme();
  }
});

templateForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (busy) return;

  const title = templateTitle.value.trim();
  const promptText = templatePrompt.value.trim();
  if (!promptText) {
    setStatus("Enter a prompt before saving a template", "error");
    return;
  }

  const savedTitle = title || "Untitled prompt";
  promptTemplates = addPromptTemplate(promptTemplates, {
    title: savedTitle,
    prompt: promptText,
  });
  persistPromptTemplates(storage, promptTemplates);
  templateForm.reset();
  render();
  setStatus(`Saved ${savedTitle}`, "ready");
});

copyMarkdown.addEventListener("click", () => {
  if (busy) return;
  void copyActiveConversationMarkdown().catch((error) => {
    setStatus(error instanceof Error ? error.message : "Unable to copy conversation", "error");
  });
});

downloadJson.addEventListener("click", () => {
  if (busy) return;
  try {
    downloadActiveConversationJson();
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Unable to download conversation", "error");
  }
});

importJson.addEventListener("click", () => {
  if (!busy) importJsonFile.click();
});

importJsonFile.addEventListener("change", async () => {
  const [file] = importJsonFile.files || [];
  importJsonFile.value = "";
  if (!file) return;
  if (file.size > 6_000_000) {
    setStatus("Conversation import exceeds the 6 MB file limit", "error");
    return;
  }
  try {
    const imported = JSON.parse(await file.text());
    state = importConversation(state, imported);
    visibleMessageLimit = 100;
    persistChatState(storage, state);
    render();
    setStatus("Conversation imported", "ready");
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Unable to import conversation", "error");
  }
});

prompt.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

model.addEventListener("change", () => {
  state = setActiveModel(state, model.value);
  persistChatState(storage, state);
});

retry.addEventListener("click", () => {
  const previous = lastUserMessage(state.messages);
  if (!previous) return;
  void sendMessage(previous.content, { retrying: true });
});

clear.addEventListener("click", () => {
  if (busy) return;
  state = clearActiveConversation(state);
  persistChatState(storage, state);
  prompt.value = "";
  setStatus("Conversation cleared", "ready");
  render();
});

newChat.addEventListener("click", () => {
  if (busy) return;
  state = startNewConversation(state);
  visibleMessageLimit = 100;
  persistChatState(storage, state);
  prompt.value = "";
  setStatus("New chat ready", "ready");
  render();
});

loadOlder.addEventListener("click", () => {
  const previousHeight = transcript.scrollHeight;
  visibleMessageLimit += 100;
  render();
  transcript.scrollTop = transcript.scrollHeight - previousHeight;
});

historySearch.addEventListener("input", () => {
  renderHistory();
});

document.addEventListener("keydown", (event) => {
  const commandKey = event.ctrlKey || event.metaKey;
  if (commandKey && !event.shiftKey && event.key.toLocaleLowerCase() === "k") {
    event.preventDefault();
    historySearch.focus();
    historySearch.select();
    return;
  }
  if (commandKey && event.shiftKey && event.key.toLocaleLowerCase() === "o") {
    event.preventDefault();
    if (!busy) newChat.click();
    return;
  }
  if (event.key === "Escape" && document.activeElement === historySearch && historySearch.value) {
    historySearch.value = "";
    renderHistory();
  }
});

logout.addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  state = clearChatState(storage);
  prompt.value = "";
  login.style.display = "inline-flex";
  logout.style.display = "none";
  setStatus("Logged out", "idle");
  render();
});

login.addEventListener("click", (event) => {
  event.preventDefault();
  setStatus("Redirecting to Cloudflare Access...", "busy");
  setTimeout(() => {
    login.style.display = "none";
    logout.style.display = "inline-flex";
    setStatus("Ready", "ready");
  }, 500);
});

login.style.display = "none";

state = {
  ...state,
  messages: Array.isArray(state.messages) ? state.messages : [],
};
persistChatState(storage, state);
promptTemplates = loadPromptTemplates(storage);
render();
void loadModels();
