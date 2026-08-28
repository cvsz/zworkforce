# Agent context and token-budget design

Status: deterministic compaction and durable token accounting implemented.

Each session persists an immutable `TokenBudget` and cumulative `TokenUsage`.
The budget independently bounds context tokens, output tokens per request, and
total session tokens. Before a model call, the loop reserves room from the
remaining total budget, projects context within that room, and lowers
`max_output_tokens` when necessary. It fails before contacting the provider
when no viable request remains.

The provider-neutral counter measures canonical UTF-8 bytes. This deliberately
conservative unit avoids coupling the agent to any provider tokenizer and
counts messages, tool arguments, images, metadata, and tool schemas. Actual
input/output usage returned by ZeaZ Provider is schema-validated, checked
against context, requested-output, and remaining-total limits, then accumulated
in the returned session.

Compaction never rewrites persisted history. It creates a deterministic
request-only system summary of omitted turns, identified by a SHA-256 of their
canonical schemas, and retains a configurable recent suffix. Text excerpts are
bounded; image payloads and tool-result bodies are represented only by safe
metadata. Leading system instructions remain verbatim. If system instructions,
tools, the bounded summary, and required recent turns cannot fit, the request
fails closed.

This preserves deterministic session replay: the stored turns are unchanged,
and the same turns, tool schemas, and compactor configuration produce the same
projection.
