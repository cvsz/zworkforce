# Agent memory design

Status: scoped interface and local SQLite implementation complete.

`MemoryStore` separates long-lived memory from replayable session turns.
Records have a namespace, stable UUID and key, kind (`episodic`, `semantic`, or
`preference`), bounded content, unique tags, JSON metadata, timestamps, and an
optimistic revision.

`SQLiteMemoryStore` provides create, exact scoped retrieval, literal substring
search, and compare-and-swap update. Namespace is part of every primary lookup,
so one user's identifier cannot retrieve another user's record. Search escapes
SQL wildcard characters, is capped at 100 results, and has a bounded query.

Documents are revalidated when read and cross-checked against indexed
namespace, ID, revision, and content columns. Records and lock waits are
bounded. The database uses the same owner-only, no-symlink, trusted-schema-off,
full-synchronous SQLite posture as session persistence and may safely share
that local database.

This first implementation intentionally provides deterministic text search,
not embeddings or cloud retrieval. The interface leaves those implementations
replaceable without changing agent/session schemas.
