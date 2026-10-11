import type { ChatSession } from "../types";

export type WorkspaceView = "chat" | "projects" | "artifacts";

interface SessionSidebarProps {
  sessions: ChatSession[];
  activeId: string | null;
  search: string;
  open: boolean;
  view: WorkspaceView;
  onSearch: (value: string) => void;
  onViewChange: (view: WorkspaceView) => void;
  onCreate: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
  onOpenSettings: () => void;
}

export function SessionSidebar({
  sessions,
  activeId,
  search,
  open,
  view,
  onSearch,
  onViewChange,
  onCreate,
  onSelect,
  onDelete,
  onClose,
  onOpenSettings,
}: SessionSidebarProps) {
  const normalized = search.trim().toLocaleLowerCase();
  const filtered = sessions.filter((session) =>
    session.title.toLocaleLowerCase().includes(normalized),
  );
  return (
    <aside className={`sidebar ${open ? "sidebar-open" : ""}`} aria-label="Workspace navigation">
      <div className="brand-row">
        <div className="brand-mark" aria-hidden="true">Z</div>
        <div>
          <strong>ZCoder</strong>
          <span>Agent workspace</span>
        </div>
        <button className="icon-button mobile-only" onClick={onClose} aria-label="Close workspace navigation">
          ×
        </button>
      </div>
      <button className="new-chat" onClick={onCreate}>
        <span aria-hidden="true">＋</span> New session
      </button>
      <nav className="workspace-nav" aria-label="Workspace">
        <span className="sidebar-section-label">WORKSPACE</span>
        <button className={`nav-item ${view === "chat" ? "active" : ""}`} aria-current={view === "chat" ? "page" : undefined} onClick={() => { onViewChange("chat"); onClose(); }}><span className="nav-icon">◌</span> Chat <span className="nav-shortcut">01</span></button>
        <button className={`nav-item ${view === "projects" ? "active" : ""}`} aria-current={view === "projects" ? "page" : undefined} onClick={() => { onViewChange("projects"); onClose(); }}><span className="nav-icon">⌘</span> Projects <span className="nav-shortcut">02</span></button>
        <button className={`nav-item ${view === "artifacts" ? "active" : ""}`} aria-current={view === "artifacts" ? "page" : undefined} onClick={() => { onViewChange("artifacts"); onClose(); }}><span className="nav-icon">◇</span> Artifacts <span className="nav-shortcut">03</span></button>
      </nav>

      {view === "chat" ? (
        <>
          <label className="search-field">
            <span className="sr-only">Search chats</span>
            <span aria-hidden="true">⌕</span>
            <input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Find a session" />
          </label>
          <div className="sidebar-section-label session-label">RECENT SESSIONS</div>
          <div className="session-list">
            {filtered.map((session) => (
              <div className={`session-row ${session.id === activeId ? "active" : ""}`} key={session.id}>
                <button onClick={() => onSelect(session.id)}>
                  <strong>{session.title}</strong>
                  <span>{session.messages.length} messages · {new Date(session.updated_at).toLocaleDateString()}</span>
                </button>
                <button className="delete-chat" onClick={() => onDelete(session.id)} aria-label={`Delete ${session.title}`}>×</button>
              </div>
            ))}
            {!filtered.length && <p className="empty-sidebar">No conversations found.</p>}
          </div>
        </>
      ) : (
        <div className="sidebar-note"><span className="sidebar-note-mark">↳</span><strong>{view === "projects" ? "Project planning" : "Versioned outputs"}</strong><span>{view === "projects" ? "Break a goal into focused tasks and review each agent result." : "Keep generated code and documents together with their revision history."}</span></div>
      )}

      <div className="sidebar-footer">
        <div className="privacy-note"><span className="status-dot" /><span>Provider keys stay server-side</span></div>
        <button className="profile-button" onClick={onOpenSettings}><span className="profile-avatar">Z</span><span><strong>Workspace settings</strong><small>Model · agent · access</small></span><span className="profile-more">···</span></button>
      </div>
    </aside>
  );
}
