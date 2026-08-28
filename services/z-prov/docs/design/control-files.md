# Control-plane Files

The Files service streams uploads into an owner-only staging directory while
enforcing per-chunk and total-byte limits and computing SHA-256. Provider I/O
starts only after local validation succeeds. Staging files are removed on
success and every failure path.

Purpose selects a closed MIME allow-list. PDF and image declarations require
matching magic bytes; text must be incremental UTF-8; JSONL requires a
`.jsonl` basename, bounded lines and count, one JSON object per line, and the
exact request shape for Batch input. Paths, hidden names, NUL, slash, and
backslash are rejected.

Provider metadata must echo the validated provider, account, filename, size,
digest, MIME, and purpose before it can commit. Metadata and its audit event
share one SQLite transaction. Stable ID keyset pagination prevents local list
skips and duplicates.

Downloads remain asynchronous streams. Each provider chunk and aggregate
length are bounded, then the final byte count and SHA-256 are checked against
catalog metadata. Provider content is never buffered as one in-memory object.

Public API provenance:
<https://platform.openai.com/docs/api-reference/files>.
