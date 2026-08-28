# Agent schema design

Status: implemented, schema version `1`.

The `zeaz-agent` package owns provider-neutral state. Its persisted boundary is
made from immutable Pydantic models that reject unknown fields. Every durable
aggregate and tool payload carries a literal schema version so future readers
can dispatch migrations explicitly rather than guessing from shape.

Session and turn IDs are UUIDs. Turns also carry a correlation UUID and a
strictly increasing sequence number. A session validates ownership, unique
turn IDs, sequence ordering, and timezone-aware timestamps. Content is a
discriminated union of text, bounded image references/data, tool calls, and
tool results. Tool names and IDs use conservative portable character sets;
all nested tool values must be JSON values.

Tool-call blocks are restricted to assistant turns and tool-result blocks to
tool turns. This removes protocol-specific role differences at the persistence
boundary. Permission decisions and execution records will be separate schemas:
a tool call describes requested work and never proves authorization.

The generated schemas target JSON Schema Draft 2020-12. UUID representation
follows RFC 9562 and timestamps follow RFC 3339:

- https://json-schema.org/draft/2020-12
- https://www.rfc-editor.org/rfc/rfc9562
- https://www.rfc-editor.org/rfc/rfc3339

Deliberate exclusions for this task are provider credentials, arbitrary Python
objects, executable callbacks, and provider-native response objects.
