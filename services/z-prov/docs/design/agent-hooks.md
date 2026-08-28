# Agent tool hooks

Tool hooks are ordered, trusted in-process policy callbacks in `zeaz-agent`.
They do not run in the provider gateway and do not execute commands.

Before calling any hook, the runner serializes tool input to bounded canonical
JSON bytes. Every pre-hook receives the same immutable bytes and SHA-256
digest. Post-hooks additionally receive a separately bounded output snapshot.
Convenience accessors decode a fresh value, so mutation by one hook cannot
affect the caller or another hook.

Each hook declares:

- a unique stable name;
- `pre_tool` or `post_tool` phase;
- a deadline of at most 60 seconds;
- `fail_closed` or `fail_open` failure policy.

`fail_closed` is the default. Explicit denial, timeout, exception, or an
invalid callback result stops the chain with a sanitized `HookDenied`.
`fail_open` converts timeout or failure to an allow outcome while retaining
`failed` and `timed_out` metadata for audit. Task cancellation always
propagates and is never converted into an allow decision.

Post-hook denial cannot undo an external mutation. Callers must treat it as a
failed tool workflow, audit the outcome, and avoid presenting the result as
successful.
