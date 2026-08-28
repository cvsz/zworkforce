import type { ChatSession } from "../types";

interface SessionSidebarProps {
  sessions: ChatSession[];
  activeId: string | null;
  search: string;
  open: boolean;
  onSearch: (value: string) => void;
  onCreate: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}

export function SessionSidebar({
  sessions,
  activeId,
  search,
  open,
  onSearch,
  onCreate,
  onSelect,
  onDelete,
  onClose,
}: SessionSidebarProps) {
  const normalized = search.trim().toLocaleLowerCase();
  const filtered = sessions.filter((session) =>
    session.title.toLocaleLowerCase().includes(normalized),
  );
  return (
    <aside className={`sidebar ${open ? "sidebar-open" : ""}`} aria-label="Chats">
      <div className="brand-row">
        <div className="brand-mark" aria-hidden="true">
          z
        </div>
        <div>
          <strong>zc workspace</strong>
          <span>local-first AI</span>
        </div>
        <button className="icon-button mobile-only" onClick={onClose} aria-label="Close chats">
          ×
        </button>
      </div>
      <button className="new-chat" onClick={onCreate}>
        <span aria-hidden="true">＋</span> New chat
      </button>
      <label className="search-field">
        <span className="sr-only">Search chats</span>
        <span aria-hidden="true">⌕</span>
        <input
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Search chats"
        />
      </label>
      <div className="session-list">
        {filtered.map((session) => (
          <div
            className={`session-row ${session.id === activeId ? "active" : ""}`}
            key={session.id}
          >
            <button onClick={() => onSelect(session.id)}>
              <strong>{session.title}</strong>
              <span>
                {session.messages.length} messages ·{" "}
                {new Date(session.updated_at).toLocaleDateString()}
              </span>
            </button>
            <button
              className="delete-chat"
              onClick={() => onDelete(session.id)}
              aria-label={`Delete ${session.title}`}
            >
              ×
            </button>
          </div>
        ))}
        {!filtered.length && (
          <p className="empty-sidebar">No conversations found.</p>
        )}
      </div>
      <div className="privacy-note">
        <span className="status-dot" />
        Data stays on this machine
      </div>
    </aside>
  );
}
