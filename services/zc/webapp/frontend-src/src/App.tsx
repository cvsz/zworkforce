import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ZcApiClient, ZcApiError } from "./api";
import { ArtifactsWorkspace } from "./components/ArtifactsWorkspace";
import { Composer } from "./components/Composer";
import { Markdown } from "./components/Markdown";
import { ProjectWorkspace } from "./components/ProjectWorkspace";
import { SessionSidebar, type WorkspaceView } from "./components/SessionSidebar";
import { SettingsPanel } from "./components/SettingsPanel";
import { readPreference, writePreference } from "./storage";
import type {
  Capabilities,
  ChatMessage,
  ChatSession,
  ResponseOptions,
  StreamEvent,
} from "./types";

const EMPTY_CAPABILITIES: Capabilities = { agents: [], personalities: [], skills: [] };
const DEFAULT_OPTIONS: ResponseOptions = { temperature: 0.3, max_tokens: 4096 };

const STARTERS = [
  { icon: "⌘", title: "Plan an implementation", prompt: "Help me break this feature into a clear implementation plan." },
  { icon: "◇", title: "Review a design", prompt: "Review this technical design for risks, missing cases, and simpler alternatives:" },
  { icon: "{}", title: "Explain a code sample", prompt: "Explain what this code does, including its edge cases:" },
  { icon: "✓", title: "Shape a test plan", prompt: "Create a focused test plan for this change. Include success and failure cases:" },
];

function exportMarkdown(session: ChatSession) {
  const content = [
    `# ${session.title}`,
    "",
    ...session.messages.flatMap((message) => [
      `## ${message.role === "user" ? "You" : "ZCoder"}`,
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

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
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
  const [apiReady, setApiReady] = useState(false);
  const [capabilities, setCapabilities] = useState<Capabilities>(EMPTY_CAPABILITIES);
  const [options, setOptions] = useState<ResponseOptions>(DEFAULT_OPTIONS);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [view, setView] = useState<WorkspaceView>("chat");
  const [artifactToOpen, setArtifactToOpen] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const transcript = useRef<HTMLDivElement>(null);

  useEffect(() => { tokenRef.current = token; }, [token]);

  const refresh = useCallback(async () => {
    try {
      const list = await api.listSessions();
      setSessions(list);
      setApiReady(true);
      setError("");
      if (!active && list.length) setActive(await api.getSession(list[0].id));
    } catch (caught) {
      if (caught instanceof ZcApiError && caught.status === 401) {
        setApiReady(false);
        setError("Connect with an application token to load this workspace.");
        setSettingsOpen(true);
      } else {
        setApiReady(false);
        setError(caught instanceof Error ? caught.message : "Unable to load sessions.");
      }
    }
  }, [active, api]);

  useEffect(() => {
    void Promise.all([
      readPreference<ResponseOptions>("response-options", DEFAULT_OPTIONS).then(setOptions),
      readPreference<string>("draft", "").then(setDraft),
    ]);
    void refresh();
  }, []); // The initial chat bootstrap intentionally runs once.

  useEffect(() => { void writePreference("draft", draft); }, [draft]);
  useEffect(() => { void writePreference("response-options", options); }, [options]);
  useEffect(() => {
    transcript.current?.scrollTo({ top: transcript.current.scrollHeight, behavior: "smooth" });
  }, [active?.messages.length, streamed]);

  const loadDiscovery = useCallback(async () => {
    try {
      const [nextModels, nextCapabilities] = await Promise.all([api.models(), api.capabilities()]);
      setModels(nextModels);
      setCapabilities(nextCapabilities);
      setApiReady(true);
      await refresh();
    } catch (caught) {
      setApiReady(false);
      if (caught instanceof ZcApiError && caught.status === 401) {
        setError("The application token was not accepted. Check it in Workspace settings.");
      } else {
        setError(caught instanceof Error ? caught.message : "Unable to connect to ZCoder.");
      }
    }
  }, [api, refresh]);

  const createSession = async () => {
    setView("chat");
    try {
      const session = await api.createSession();
      setActive(session);
      setSessions((current) => [session, ...current]);
      setSidebarOpen(false);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create session.");
      if (caught instanceof ZcApiError && caught.status === 401) setSettingsOpen(true);
    }
  };

  const selectSession = async (id: string) => {
    try {
      setActive(await api.getSession(id));
      setView("chat");
      setSidebarOpen(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load session.");
      if (caught instanceof ZcApiError && caught.status === 401) setSettingsOpen(true);
    }
  };

  const deleteSession = async (id: string) => {
    if (!window.confirm("Delete this conversation from this workspace?")) return;
    try {
      await api.deleteSession(id);
      const remaining = sessions.filter((session) => session.id !== id);
      setSessions(remaining);
      if (active?.id === id) setActive(remaining.length ? await api.getSession(remaining[0].id) : null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to delete session.");
    }
  };

  const renameSession = async () => {
    if (!active) return;
    const title = window.prompt("Rename session", active.title)?.trim();
    if (!title || title === active.title) return;
    try {
      const updated = await api.renameSession(active.id, title);
      setActive(updated);
      setSessions((current) => current.map((session) => session.id === updated.id ? updated : session));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to rename session.");
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
        setSessions((current) => [session!, ...current]);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Unable to create session.");
        if (caught instanceof ZcApiError && caught.status === 401) setSettingsOpen(true);
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
      await api.streamResponse(session.id, prompt, options, abortController.signal, (event: StreamEvent) => {
        if (event.type === "response.output_text.delta") setStreamed((current) => current + event.delta);
        else if (event.type === "response.error") throw new Error(event.error.message);
      });
      const updated = await api.getSession(session.id);
      setActive(updated);
      setSessions((current) => [updated, ...current.filter((item) => item.id !== updated.id)]);
      setStreamed("");
    } catch (caught) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) {
        setError(caught instanceof Error ? caught.message : "Response failed.");
        if (caught instanceof ZcApiError && caught.status === 401) setSettingsOpen(true);
      }
      const restored = await api.getSession(session.id).catch(() => null);
      if (restored) setActive(restored);
    } finally {
      setBusy(false);
      controller.current = null;
    }
  };

  const visibleMessages = active?.messages ?? [];
  const title = view === "chat" ? (active?.title ?? "New coding session") : "Coding workspace";

  return (
    <div className={`app-shell view-${view}`}>
      <SessionSidebar
        sessions={sessions}
        activeId={active?.id ?? null}
        search={search}
        open={sidebarOpen}
        view={view}
        onSearch={setSearch}
        onViewChange={setView}
        onCreate={() => void createSession()}
        onSelect={(id) => void selectSession(id)}
        onDelete={(id) => void deleteSession(id)}
        onClose={() => setSidebarOpen(false)}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      {sidebarOpen && <button className="sidebar-scrim" onClick={() => setSidebarOpen(false)} aria-label="Close navigation" />}

      <main className="workspace">
        <header className="workspace-header">
          <button className="icon-button mobile-only" onClick={() => setSidebarOpen(true)} aria-label="Open workspace navigation">☰</button>
          <div className="title-block">
            <span className="breadcrumb"><span>ZCODER</span><b>/</b>{view.toUpperCase()}</span>
            <h1>{title}</h1>
          </div>
          <div className="header-actions">
            {view === "chat" && <button className="model-pill" onClick={() => setSettingsOpen(true)}><span className={`status-dot ${apiReady ? "" : "offline"}`} /><span>{options.model || "Default model"}</span><b>⌄</b></button>}
            {view === "chat" && active && <>
              <button className="text-button" onClick={() => void renameSession()}>Rename</button>
              <button className="text-button" onClick={() => exportMarkdown(active)}>Export</button>
            </>}
            <button className="icon-button" onClick={() => setSettingsOpen(true)} aria-label="Open workspace settings" title="Workspace settings">⚙</button>
          </div>
        </header>

        {view === "chat" ? (
          <>
            {error && <div className="error-banner" role="alert"><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss">×</button></div>}
            <div className="chat-layout">
              <div className="chat-column">
                <div className="transcript" ref={transcript} aria-live="polite">
                  {!visibleMessages.length && !streamed ? (
                    <section className="welcome">
                      <div className="welcome-mark">Z</div>
                      <span className="eyebrow">Your coding workspace</span>
                      <h2>What are we working on?</h2>
                      <p>Plan a change, reason through a design, or work through a code sample with your selected agent.</p>
                      <div className="starter-grid">
                        {STARTERS.map((starter) => <button key={starter.title} onClick={() => setDraft(starter.prompt)}><span className="starter-icon">{starter.icon}</span><span>{starter.title}</span><b>↗</b></button>)}
                      </div>
                    </section>
                  ) : (
                    <div className="messages">
                      {visibleMessages.map((message) => <article className={`message ${message.role}`} key={message.id}>
                        <div className="avatar">{message.role === "user" ? "You" : "Z"}</div>
                        <div className="message-content">
                          <header><strong>{message.role === "user" ? "You" : "ZCoder"}</strong><span>{formatTime(message.created_at)}</span>{message.model && <span className="message-model">{message.model}</span>}</header>
                          {message.role === "assistant" ? <Markdown>{message.content}</Markdown> : <p>{message.content}</p>}
                        </div>
                      </article>)}
                      {streamed && <article className="message assistant"><div className="avatar">Z</div><div className="message-content"><header><strong>ZCoder</strong><span className="live-label">generating</span></header><Markdown>{streamed}</Markdown></div></article>}
                    </div>
                  )}
                </div>
                <Composer
                  value={draft}
                  busy={busy}
                  disabled={false}
                  agent={options.agent}
                  model={options.model}
                  onOpenSettings={() => setSettingsOpen(true)}
                  onChange={setDraft}
                  onSubmit={() => void submit()}
                  onStop={() => controller.current?.abort()}
                />
              </div>
              <aside className="session-inspector">
                <div className="inspector-heading"><span className="eyebrow">Session setup</span><button className="quiet-button" onClick={() => setSettingsOpen(true)}>Edit</button></div>
                <div className="inspector-agent"><span className="agent-avatar">Z</span><span><strong>{options.agent || "General agent"}</strong><small>{options.personality || "Default personality"}</small></span><span className={`online-dot ${apiReady ? "" : "offline"}`} title={apiReady ? "ZC API connected" : "ZC API not connected"} /></div>
                <div className="inspector-rule" />
                <div className="inspector-field"><span>MODEL</span><strong>{options.model || "Server default"}</strong></div>
                <div className="inspector-field"><span>SKILL</span><strong>{options.skill || "No skill selected"}</strong></div>
                <div className="inspector-field"><span>RESPONSE BUDGET</span><strong>{options.max_tokens.toLocaleString()} tokens</strong></div>
                <div className="inspector-rule" />
                <div className="inspector-heading"><span className="eyebrow">Session activity</span><span className="count-pill">{visibleMessages.length}</span></div>
                {active ? <div className="activity-card"><span className="activity-icon">◷</span><span><strong>Conversation saved</strong><small>Updated {new Date(active.updated_at).toLocaleString()}</small></span></div> : <div className="activity-card"><span className="activity-icon">＋</span><span><strong>New session</strong><small>Your messages will appear here.</small></span></div>}
                <div className="inspector-note"><span className="note-icon">i</span><span>Provider credentials stay behind the ZC API boundary.</span></div>
              </aside>
            </div>
          </>
        ) : view === "projects" ? (
          <ProjectWorkspace key={apiReady ? "authenticated" : "waiting-for-token"} api={api} models={models} options={options} onOpenArtifacts={(id) => { setArtifactToOpen(id); setView("artifacts"); }} onOpenSettings={() => setSettingsOpen(true)} />
        ) : (
          <ArtifactsWorkspace key={apiReady ? "authenticated" : "waiting-for-token"} api={api} models={models} options={options} onOpenSettings={() => setSettingsOpen(true)} initialArtifactId={artifactToOpen ?? undefined} onArtifactOpened={() => setArtifactToOpen(null)} />
        )}
      </main>

      <SettingsPanel
        open={settingsOpen}
        token={token}
        models={models}
        capabilities={capabilities}
        options={options}
        onToken={(value) => { setToken(value); tokenRef.current = value; }}
        onOptions={setOptions}
        onClose={() => { setSettingsOpen(false); void loadDiscovery(); }}
      />
    </div>
  );
}
