# Agent session-store design

Status: SQLite persistence and optimistic concurrency implemented.

`SQLiteSessionStore` persists the complete versioned `Session` JSON document
with its revision in a schema-versioned SQLite database. Loading revalidates
the document and cross-checks its ID and revision against indexed columns.
Session documents and database lock waits are bounded.

Creation is insert-only. Updates require the caller's expected revision and a
strictly newer session revision. A single conditional update runs inside
`BEGIN IMMEDIATE`; zero updated rows become either `SessionNotFound` or
`SessionConflict`. Consequently, two workers starting from one revision cannot
both commit and silently overwrite each other.

The database is an owner-only regular file, symlinks are rejected, SQLite
trusted schemas are disabled, rollback journaling and full synchronous commits
are used, and unsupported schema versions fail closed. The repository has no
delete operation.

Tool-call schemas recursively reject credential-shaped argument fields before
they can enter a session document. Provider credentials remain exclusively in
`zeaz-provider`; the agent gateway client holds only its gateway client key and
never serializes that key into a session.

SQLite transaction and isolation references:

- https://www.sqlite.org/transactional.html
- https://www.sqlite.org/isolation.html
- https://www.sqlite.org/lang_transaction.html
