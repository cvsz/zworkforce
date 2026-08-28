# Subagent scheduling design

Status: bounded scheduler and hierarchical cancellation implemented.

`SubagentManager` is the only constructor of subagent requests. It derives
depth from an actively running tracked parent, verifies the same session, and
enforces configured depth, concurrent, lifetime-count, per-agent-token,
aggregate-token, and wall-clock limits.

Token budgets are reserved atomically before scheduling, preventing concurrent
overcommit. A successful worker is charged its validated reported usage and
unused reservation is released. Failure, cancellation, timeout, or usage above
the reservation is charged the full reservation so retry/failure cannot evade
the aggregate budget.

Each request has a cancellation token. Cancelling a parent cancels every
tracked descendant, including work queued behind the concurrency semaphore.
Worker exceptions are converted to fixed error codes; exception details are
not returned or audited. Lifecycle audit records contain depth and token
counts, never task or output content.

The scheduler invokes an injected `SubagentWorker` protocol and does not itself
execute shell commands, load provider credentials, or bypass tool permission
and plan gates.
