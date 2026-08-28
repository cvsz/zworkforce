# Deterministic agent fixtures

Status: reusable scripted model fixtures implemented.

`DeterministicModelClient` implements the production `ModelClient` protocol
without network access. A finite immutable script provides either strict
`ModelOutput` values or stable error codes. Each step may assert model alias,
turn roles, tool names, output limit, and canonical context SHA-256. Requests
are recorded and unexpected calls or unconsumed steps fail loudly.

`DeterministicUUIDFactory` derives a repeatable UUID sequence from a named seed,
and `FixedClock` provides an aware fixed timestamp. `AgentLoop` accepts both as
dependencies. Given the same initial session, user input, tool definitions,
script, UUID seed, clock, and compactor configuration, a replay produces the
identical immutable result and serialized session state.

These fixtures contain no provider credentials, make no external calls, and
are suitable for protocol, budget, failure, persistence, and replay tests.
