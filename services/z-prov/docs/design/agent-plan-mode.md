# Agent plan-mode design

Status: mutation gate implemented.

Plan mode is durable session state, changed immutably with a revision increment.
Tools declare whether they mutate state; the safe default is mutating, and
unknown tools are also mutating. Declared read-only tools may run in plan mode
after normal tool permission checks.

A mutating call in plan mode requires two independent records:

1. an exact `allow` permission decision bound to the call and context; and
2. a `PlanApproval` bound to the session, immutable plan SHA-256, and an exact
   planned action containing the call ID, tool name, and argument SHA-256.

Changing the plan, arguments, call identity, or session invalidates approval.
Approval of a plan never substitutes for tool permission, and a tool allow
never substitutes for plan approval. `require_execution_allowed` is the
combined fail-closed boundary intended for every future tool dispatcher.

Plans contain bounded human-readable steps and argument digests rather than
raw tool arguments. This avoids duplicating potentially sensitive inputs in a
second persisted artifact.
