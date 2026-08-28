# Z.A.R.V.I.S. Session Runtime

Epic: #148

## Objective

Connect the existing realtime ZVoice stack to the owner-only Z.A.R.V.I.S. command boundary and make command/session state durable without weakening the read-only or owner identity invariants.

## Flow

```text
microphone
  -> ZVoice AudioWorklet
  -> voice-gateway signed realtime session
  -> finalized transcript
  -> ZVoice owner bridge
  -> zarvis.command.requested.v1
  -> idempotency lookup
  -> read-only tool execution
  -> audit event
  -> session event
  -> speech-ready response
  -> browser speech synthesis
```

## Identity

All Z.A.R.V.I.S. voice requests are derived from the immutable owner identity:

- GitHub owner ID: `4076926`
- user ID: `github:4076926`
- tenant ID: `owner-4076926`

The trusted edge authenticates the owner and injects an edge-only assertion. ZVoice discards caller-supplied tenant/subject values and forwards only the fixed owner service identity to the orchestrator.

## Persistence model

`FileSessionStore` implements four operations:

1. append a versioned session event;
2. read recent events for one session;
3. store/read one idempotent command result envelope;
4. delete one session and its referenced command result envelopes.

The single-owner adapter uses two fixed-path journals inside `ZARVIS_DATA_DIR`:

- `session-events.jsonl` for append-only session transitions;
- `command-results.jsonl` for idempotency result envelopes.

Request, session, and command identifiers are data inside those journals and never influence filesystem paths. All writes are serialized through one in-process lock. Privacy deletion atomically compacts both fixed journals and removes every record associated with the selected session. This is suitable for a single-process, single-owner deployment. Horizontal multi-process production requires the planned PostgreSQL/outbox adapter.

## Failure semantics

- Duplicate identical commands do not execute the tool twice.
- Duplicate conflicting commands return `409`.
- Unsupported or mutating tools remain rejected before execution.
- Session deletion requires an explicit confirmation header.
- A storage failure fails the command rather than silently dropping session state.
- Provider, GitHub, edge, and service secrets are excluded from results, events, and health output.
