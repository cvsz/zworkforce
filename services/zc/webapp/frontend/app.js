// app.js — wire web console
// Talks to the FastAPI backend in webapp/backend/server.py. Same-origin by
// default (the backend serves this file), so relative URLs are enough.

const API = "/api";

const el = (id) => document.getElementById(id);

const transcript      = el("transcript");
const chatForm        = el("chatForm");
const promptInput      = el("promptInput");
const sendBtn          = el("sendBtn");
const modelSelect      = el("modelSelect");
const personalitySelect= el("personalitySelect");
const agentSelect       = el("agentSelect");
const skillSelect       = el("skillSelect");
const tempRange         = el("tempRange");
const tempVal           = el("tempVal");
const systemPrompt      = el("systemPrompt");
const apiKeyInput       = el("apiKeyInput");
const saveKeyBtn        = el("saveKeyBtn");
const newSessionBtn     = el("newSessionBtn");
const sessionIdTag      = el("sessionIdTag");
const versionTag        = el("versionTag");
const healthPip         = el("healthPip");
const healthText        = el("healthText");
const themeToggle        = el("themeToggle");
const sessionList        = el("sessionList");
const streamToggle       = el("streamToggle");

let sessionId = null;
let busy = false;

// --- theme ------------------------------------------------------------
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  themeToggle.textContent = theme === "light" ? "☀" : "☾";
  try { localStorage.setItem("wire-theme", theme); } catch (e) { /* ignore */ }
}
themeToggle.addEventListener("click", () => {
  const current = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
  applyTheme(current === "light" ? "dark" : "light");
});
(() => {
  let saved = "dark";
  try { saved = localStorage.getItem("wire-theme") || "dark"; } catch (e) { /* ignore */ }
  applyTheme(saved);
})();

// --- minimal markdown: fenced code blocks + inline code, nothing else --
// Deliberately not a full markdown renderer (no external deps, per this
// project's dependency-free frontend) — just the two constructs that
// actually matter for a coding assistant's output.
function renderMarkdownLite(container, text) {
  container.innerHTML = "";
  const parts = text.split(/```(\w*)\n?([\s\S]*?)```/g);
  // split() with capturing groups yields [plain, lang, code, plain, lang, code, ...]
  for (let i = 0; i < parts.length; i += 3) {
    const plain = parts[i];
    if (plain) {
      const span = document.createElement("span");
      span.innerHTML = plain
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/`([^`]+)`/g, "<code>$1</code>");
      container.appendChild(span);
    }
    const lang = parts[i + 1];
    const code = parts[i + 2];
    if (code !== undefined) {
      const pre = document.createElement("pre");
      const codeEl = document.createElement("code");
      codeEl.textContent = code.replace(/\n$/, "");
      if (lang) codeEl.className = "lang-" + lang;
      const copyBtn = document.createElement("button");
      copyBtn.className = "copy-btn";
      copyBtn.textContent = "copy";
      copyBtn.type = "button";
      copyBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(code).then(() => {
          copyBtn.textContent = "copied ✓";
          setTimeout(() => { copyBtn.textContent = "copy"; }, 1400);
        });
      });
      pre.appendChild(codeEl);
      pre.appendChild(copyBtn);
      container.appendChild(pre);
    }
  }
}

// --- session list -------------------------------------------------------
async function refreshSessionList() {
  let sessions;
  try {
    sessions = await getJSON("/sessions");
  } catch (e) {
    return; // non-fatal — sidebar just stays as-is
  }
  sessionList.innerHTML = "";
  if (!sessions.length) {
    sessionList.innerHTML = '<span class="session-list-empty">no sessions yet</span>';
    return;
  }
  sessions.forEach((s) => {
    const item = document.createElement("div");
    item.className = "session-item" + (s.session_id === sessionId ? " active" : "");
    const preview = document.createElement("div");
    preview.className = "s-preview";
    preview.textContent = s.preview || "(empty)";
    const meta = document.createElement("div");
    meta.className = "s-meta";
    meta.textContent = `${s.session_id.slice(0, 8)} · ${s.turns} turn${s.turns === 1 ? "" : "s"}`;
    item.appendChild(preview);
    item.appendChild(meta);
    item.addEventListener("click", () => loadSession(s.session_id));
    sessionList.appendChild(item);
  });
}

async function loadSession(id) {
  try {
    const data = await getJSON(`/sessions/${id}`);
    sessionId = id;
    sessionIdTag.textContent = id.slice(0, 8);
    transcript.innerHTML = "";
    (data.history || []).forEach((m) => addMessage(m.role === "user" ? "user" : "assistant", m.content));
    refreshSessionList();
  } catch (e) {
    addMessage("error", `Could not load session: ${e.message || e}`);
  }
}

async function getJSON(path) {
  const res = await fetch(API + path);
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
  return res.json();
}

async function postJSON(path, body) {
  const res = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `${path} -> HTTP ${res.status}`);
  return data;
}

function addMessage(role, text, meta) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const sym = document.createElement("span");
  sym.className = "prompt-sym";
  sym.textContent = role === "user" ? "$" : role === "error" ? "!" : ">";
  const bubble = document.createElement("div");
  bubble.innerHTML = "";
  bubble.style.display = "flex";
  bubble.style.flexDirection = "column";

  const body = document.createElement("div");
  body.className = "bubble";
  if (role === "assistant") {
    renderMarkdownLite(body, text);
  } else {
    body.textContent = text;
  }
  bubble.appendChild(body);

  if (meta) {
    const m = document.createElement("div");
    m.className = "meta";
    m.textContent = meta;
    bubble.appendChild(m);
  }

  wrap.appendChild(sym);
  wrap.appendChild(bubble);
  transcript.appendChild(wrap);
  transcript.scrollTop = transcript.scrollHeight;
  return body;
}

function setBusy(state) {
  busy = state;
  sendBtn.disabled = state;
  sendBtn.textContent = state ? "…" : "run";
}

async function loadStaticData() {
  try {
    const v = await getJSON("/version");
    versionTag.textContent = "v" + v.version;
  } catch (e) { versionTag.textContent = "v?"; }

  try {
    const models = await getJSON("/models");
    modelSelect.innerHTML = "";
    models.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = `${m.display_name} (${m.tier})`;
      if (m.id === "claude-sonnet-5") opt.selected = true;
      modelSelect.appendChild(opt);
    });
  } catch (e) {
    modelSelect.innerHTML = '<option value="claude-sonnet-5">zAICoder Sonnet 5</option>';
  }

  try {
    const personalities = await getJSON("/personalities");
    personalities.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.name;
      opt.textContent = p.name;
      opt.title = p.description;
      personalitySelect.appendChild(opt);
    });
  } catch (e) { /* non-fatal */ }

  try {
    const agents = await getJSON("/agents");
    agents.forEach((a) => {
      const opt = document.createElement("option");
      opt.value = a.name;
      opt.textContent = a.name.replace(/_/g, " ");
      opt.title = a.description;
      agentSelect.appendChild(opt);
    });
  } catch (e) { /* non-fatal */ }

  try {
    const skills = await getJSON("/skills");
    skills.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.name;
      opt.textContent = s.name.replace(/_/g, " ");
      opt.title = s.description;
      skillSelect.appendChild(opt);
    });
  } catch (e) { /* non-fatal */ }
}

async function refreshHealth() {
  try {
    const h = await getJSON("/health");
    const ok = h.status === "healthy";
    healthPip.className = "dot " + (ok ? "ok" : "bad");
    const failing = (h.checks || []).filter((c) => !c.ok).map((c) => c.name);
    healthText.textContent = ok ? "healthy" : `unhealthy (${failing.join(", ")})`;
  } catch (e) {
    healthPip.className = "dot bad";
    healthText.textContent = "unreachable";
  }
}

tempRange.addEventListener("input", () => { tempVal.textContent = tempRange.value; });

saveKeyBtn.addEventListener("click", async () => {
  const key = apiKeyInput.value.trim();
  if (!key) return;
  saveKeyBtn.textContent = "saving…";
  try {
    await postJSON("/config", { api_key: key });
    saveKeyBtn.textContent = "saved ✓";
    apiKeyInput.value = "";
    setTimeout(refreshHealth, 300);
  } catch (e) {
    saveKeyBtn.textContent = "failed";
  }
  setTimeout(() => { saveKeyBtn.textContent = "save to server config"; }, 1800);
});

newSessionBtn.addEventListener("click", () => {
  sessionId = null;
  sessionIdTag.textContent = "new";
  transcript.innerHTML = `<div class="welcome"><p><span class="prompt-sym">&gt;</span> new session started.</p></div>`;
});

promptInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    chatForm.requestSubmit();
  }
});
promptInput.addEventListener("input", () => {
  promptInput.style.height = "auto";
  promptInput.style.height = Math.min(promptInput.scrollHeight, 160) + "px";
});

async function sendStreaming(payload) {
  const res = await fetch(API + "/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok || !res.body) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `chat/stream -> HTTP ${res.status}`);
  }

  const bubble = addMessage("assistant", "", "streaming…");
  const cursor = document.createElement("span");
  cursor.className = "streaming-cursor";
  cursor.textContent = "▍";
  bubble.appendChild(cursor);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let full = "";
  let done = false;

  while (!done) {
    const { value, done: rDone } = await reader.read();
    if (rDone) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n\n");
    buf = lines.pop(); // last (possibly incomplete) chunk stays in buf
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const evt = JSON.parse(line.slice(6));
      if (evt.type === "token") {
        full += evt.text;
        renderMarkdownLite(bubble, full);
        bubble.appendChild(cursor);
        transcript.scrollTop = transcript.scrollHeight;
      } else if (evt.type === "done") {
        sessionId = evt.session_id;
        sessionIdTag.textContent = sessionId.slice(0, 8);
        done = true;
      } else if (evt.type === "error") {
        renderMarkdownLite(bubble, full || `[ERROR] ${evt.message}`);
        done = true;
      }
    }
  }
  cursor.remove();
  refreshSessionList();
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (busy) return;
  const text = promptInput.value.trim();
  if (!text) return;

  addMessage("user", text);
  promptInput.value = "";
  promptInput.style.height = "auto";
  setBusy(true);

  const payload = {
    prompt: text,
    session_id: sessionId,
    model: modelSelect.value || "claude-sonnet-5",
    temperature: parseFloat(tempRange.value),
    system: systemPrompt.value || null,
    personality: personalitySelect.value || null,
    agent: agentSelect.value || null,
    skill: skillSelect.value || null,
  };

  try {
    if (streamToggle.checked) {
      await sendStreaming(payload);
    } else {
      const data = await postJSON("/chat", payload);
      sessionId = data.session_id;
      sessionIdTag.textContent = sessionId.slice(0, 8);
      const isErr = /^\[(ERROR|API ERROR|REFUSED)/.test(data.response || "");
      addMessage(isErr ? "error" : "assistant", data.response, `model: ${data.model}`);
      refreshSessionList();
    }
  } catch (err) {
    addMessage("error", String(err.message || err));
  } finally {
    setBusy(false);
    promptInput.focus();
  }
});

loadStaticData();
refreshHealth();
refreshSessionList();
setInterval(refreshHealth, 20000);
setInterval(refreshSessionList, 15000);
