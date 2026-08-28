# Agent permission design

Status: explicit decision and policy evaluation implemented.

Every requested tool call can produce an immutable, versioned
`PermissionDecision` with an `allow`, `deny`, or `ask` outcome. Decisions bind
the session, correlation ID, call ID, tool name, and SHA-256 of canonical JSON
arguments. A recorded allow therefore cannot be replayed for a modified call,
another session, or another run.

`PermissionRule` matches a bounded portable tool-name glob and optional exact
top-level argument attributes. Highest priority wins; at equal priority,
`deny` wins over `ask`, which wins over `allow`. Rule IDs must be unique and
the policy is bounded to 10,000 rules. The safe default is `ask`.

An `ask` is not executable authorization. It can only be resolved to `allow`
or `deny` by a named actor, producing a new decision linked to the original.
`require_allowed` is the execution-boundary guard: non-allow decisions and
context/digest mismatches fail closed.

This is a deliberately small attribute-based policy inspired by NIST's ABAC
definition; it is not presented as an implementation of the full NIST model:

- https://csrc.nist.gov/pubs/sp/800/162/upd1/final

The later audit task will append these records durably, and the tool runtime
will accept only decisions that pass `require_allowed`.
