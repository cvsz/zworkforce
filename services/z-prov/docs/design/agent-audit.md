# Agent audit-ledger design

Status: append-only local ledger implemented.

`JsonlAuditLog` writes immutable, versioned events with mandatory session and
correlation UUIDs. Each record has a contiguous sequence number, the prior
record SHA-256, and its own SHA-256 over canonical JSON. Verification rejects
modified, reordered, malformed, oversized, or partial records.

The file is opened without following symlinks, must be a regular file owned by
the process with mode `0600`, and is written only through `O_APPEND` while an
exclusive advisory lock is held. One bounded JSON record is fully written and
optionally `fsync`ed before unlocking. Concurrent appenders therefore cannot
silently reuse sequence numbers.

Events contain operational metadata, never prompts or credentials. Common
credential, authorization, message, prompt, content, and request-body fields
are recursively redacted before model validation and persistence. Depth,
collection cardinality, string length, event bytes, and total log bytes are
bounded.

When configured with a ledger, `AgentLoop` emits user-turn, model-request,
model-completion, model-failure, and tool-result metadata without content.
Dedicated helpers record permission decisions and plan approvals without raw
arguments. Audit write failures propagate instead of silently dropping an
event.

The hash chain detects edits and reordering, but tail truncation requires an
external checkpoint for proof. Durable remote export and retention policy are
future deployment concerns. The design follows the operational goals of NIST
SP 800-92 without claiming full conformance:

- https://csrc.nist.gov/pubs/sp/800/92/final
