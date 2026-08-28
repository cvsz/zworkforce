import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ZcApiClient, ZcApiError } from "./api";
import { Composer } from "./components/Composer";
import { Markdown } from "./components/Markdown";
import { SessionSidebar } from "./components/SessionSidebar";
import { SettingsPanel } from "./components/SettingsPanel";
import { readPreference, writePreference } from "./storage";
import type {
  Capabilities,
  ChatMessage,
  ChatSession,
  ResponseOptions,
  StreamEvent,
} from "./types";

const EMPTY_CAPABILITIES: Capabilities = {
  agents: [],
  personalities: [],
  skills: [],
};
const DEFAULT_OPTIONS: ResponseOptions = {
  temperature: 0.3,
  max_tokens: 4096,
};

function exportMarkdown(session: ChatSession) {
  const content = [
    `# ${session.title}`,
    "",
    ...session.messages.flatMap((message) => [
      `## ${message.role === "user" ? "You" : "zc"}`,
      "",
      message.content,
      "",
    ]),
  ].join("\n");
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([content], { type: "text/markdown" }));
  link.download = `${session.title.replace(/[^\w-]+/g, "-").toLowerCase() || "chat"}.md`;
  link.click();
  URL.revokeObjectURL(link.href);
}

export default function App() {
  const [token, setToken] = useState("");
  const tokenRef = useRef("");
  const api = useMemo(() => new ZcApiClient(() => tokenRef.current), []);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [active, setActive] = useState<ChatSession | null>(null);
  const [search, setSearch] = useState("");
  const [draft, setDraft] = useState("");
  const [streamed, setStreamed] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [capabilities, setCapabilities] =
    useState<Capabilities>(EMPTY_CAPABILITIES);
  const [options, setOptions] = useState<ResponseOptions>(DEFAULT_OPTIONS);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const transcript = useRef<HTMLDivElement>(null);

  useEffect(() => {
    tokenRef.current = token;
  }, [token]);

  const refresh = useCallback(async () => {
    try {
      const list = await api.listSessions();
      setSessions(list);
      setError("");
      if (!active && list.length) setActive(await api.getSession(list[0].id));
    } catch (caught) {
      if (caught instanceof ZcApiError && caught.status === 401) {
        setError("Connect with an application token to load this workspace.");
        setSettingsOpen(true);
      } else {
        setError(caught instanceof Error ? caught.message : "Unable to load chats.");
      }
    }
  }, [active, api]);

  useEffect(() => {
    void Promise.all([
      readPreference<ResponseOptions>("response-options", DEFAULT_OPTIONS).then(setOptions),
      readPreference<string>("draft", "").then(setDraft),
    ]);
    void refresh();
  }, []); // Initial bootstrap intentionally runs once.

  useEffect(() => {
    void writePreference("draft", draft);
  }, [draft]);
  useEffect(() => {
    void writePreference("response-options", options);
  }, [options]);
  useEffect(() => {
    transcript.current?.scrollTo({
      top: transcript.current.scrollHeight,
      behavior: "smooth",
    });
  }, [active?.messages.length, streamed]);

  const loadDiscovery = useCallback(async () => {
    try {
      const [nextModels, nextCapabilities] = await Promise.all([
        api.models(),
        api.capabilities(),
      ]);
      setModels(nextModels);
      setCapabilities(nextCapabilities);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to connect.");
    }
  }, [api, refresh]);

  const createSession = async () => {
    try {
      const session = await api.createSession();
      setActive(session);
      setSessions((current) => [session, ...current]);
      setSidebarOpen(false);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create chat.");
    }
  };

  const selectSession = async (id: string) => {
    try {
      setActive(await api.getSession(id));
      setSidebarOpen(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load chat.");
    }
  };

  const deleteSession = async (id: string) => {
    if (!window.confirm("Delete this conversation from local storage?")) return;
    try {
      await api.deleteSession(id);
      const remaining = sessions.filter((session) => session.id !== id);
      setSessions(remaining);
      if (active?.id === id) {
        setActive(remaining.length ? await api.getSession(remaining[0].id) : null);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to delete chat.");
    }
  };

  const renameSession = async () => {
    if (!active) return;
    const title = window.prompt("Rename conversation", active.title)?.trim();
    if (!title || title === active.title) return;
    try {
      const updated = await api.renameSession(active.id, title);
      setActive(updated);
      setSessions((current) =>
        current.map((session) => (session.id === updated.id ? updated : session)),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to rename chat.");
    }
  };

  const submit = async () => {
    const prompt = draft.trim();
    if (!prompt || busy) return;
    let session = active;
    if (!session) {
      try {
        session = await api.createSession();
        setActive(session);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Unable to create chat.");
        return;
      }
    }
    const optimistic: ChatMessage = {
      id: `pending-${Date.now()}`,
      role: "user",
      content: prompt,
      created_at: new Date().toISOString(),
      model: options.model ?? null,
      usage: { input_tokens: null, output_tokens: null },
    };
    setActive({ ...session, messages: [...session.messages, optimistic] });
    setDraft("");
    setStreamed("");
    setBusy(true);
    setError("");
    const abortController = new AbortController();
    controller.current = abortController;
    try {
      await api.streamResponse(
        session.id,
        prompt,
        options,
        abortController.signal,
        (event: StreamEvent) => {
          if (event.type === "response.output_text.delta") {
            setStreamed((current) => current + event.delta);
          } else if (event.type === "response.error") {
            throw new Error(event.error.message);
          }
        },
      );
      const updated = await api.getSession(session.id);
      setActive(updated);
      setSessions((current) => [
        updated,
        ...current.filter((item) => item.id !== updated.id),
      ]);
      setStreamed("");
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) {
        setError(caught instanceof Error ? caught.message : "Response failed.");
      }
      const restored = await api.getSession(session.id).catch(() => null);
      if (restored) setActive(restored);
    } finally {
      setBusy(false);
      controller.current = null;
    }
  };

  const visibleMessages = active?.messages ?? [];
  return (
    <div className="app-shell">
      <SessionSidebar
        sessions={sessions}
        activeId={active?.id ?? null}
        search={search}
        open={sidebarOpen}
        onSearch={setSearch}
        onCreate={() => void createSession()}
        onSelect={(id) => void selectSession(id)}
        onDelete={(id) => void deleteSession(id)}
        onClose={() => setSidebarOpen(false)}
      />
      {sidebarOpen && <button className="sidebar-scrim" onClick={() => setSidebarOpen(false)} aria-label="Close chats" />}
      <main className="workspace">
        <header className="workspace-header">
          <button className="icon-button mobile-only" onClick={() => setSidebarOpen(true)} aria-label="Open chats">☰</button>
          <div className="title-block">
            <span className="eyebrow">{active ? "Conversation" : "Workspace"}</span>
            <h1>{active?.title ?? "What are we building?"}</h1>
          </div>
          <div className="header-actions">
            {active && (
              <>
                <button className="text-button" onClick={() => void renameSession()}>
                  Rename
                </button>
                <button className="text-button" onClick={() => exportMarkdown(active)}>
                  Export
                </button>
              </>
            )}
            <button className="icon-button" onClick={() => setSettingsOpen(true)} aria-label="Open settings">⚙</button>
          </div>
        </header>
        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button onClick={() => setError("")} aria-label="Dismiss">×</button>
          </div>
        )}
        <div className="transcript" ref={transcript} aria-live="polite">
          {!visibleMessages.length && !streamed ? (
            <section className="welcome">
              <div className="welcome-mark">zc</div>
              <span className="eyebrow">Private by default</span>
              <h2>Build with your local AI workspace.</h2>
              <p>
                Conversations stay on this machine. Model credentials remain
                behind the zc API boundary.
              </p>
              <div className="starter-grid">
                {[
                  "Review the current repository architecture",
                  "Design a secure API for this feature",
                  "Find and explain the next failing test",
                  "Plan a production-ready implementation",
                ].map((starter) => (
                  <button key={starter} onClick={() => setDraft(starter)}>
                    <span>{starter}</span><b>↗</b>
                  </button>
                ))}
              </div>
            </section>
          ) : (
            <div className="messages">
              {visibleMessages.map((message) => (
                <article className={`message ${message.role}`} key={message.id}>
                  <div className="avatar">{message.role === "user" ? "You" : "zc"}</div>
                  <div className="message-content">
                    <header>
                      <strong>{message.role === "user" ? "You" : "zc"}</strong>
                      <span>{new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                    </header>
                    {message.role === "assistant" ? <Markdown>{message.content}</Markdown> : <p>{message.content}</p>}
                  </div>
                </article>
              ))}
              {streamed && (
                <article className="message assistant">
                  <div className="avatar">zc</div>
                  <div className="message-content">
                    <header><strong>zc</strong><span className="live-label">streaming</span></header>
                    <Markdown>{streamed}</Markdown>
                  </div>
                </article>
              )}
            </div>
          )}
        </div>
        <Composer
          value={draft}
          busy={busy}
          disabled={false}
          onChange={setDraft}
          onSubmit={() => void submit()}
          onStop={() => controller.current?.abort()}
        />
      </main>
      <SettingsPanel
        open={settingsOpen}
        token={token}
        models={models}
        capabilities={capabilities}
        options={options}
        onToken={(value) => {
          setToken(value);
          tokenRef.current = value;
        }}
        onOptions={setOptions}
        onClose={() => {
          setSettingsOpen(false);
          void loadDiscovery();
        }}
      />
    </div>
  );
}
