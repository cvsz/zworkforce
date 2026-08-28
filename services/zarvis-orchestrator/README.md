# Z.A.R.V.I.S. Orchestrator

The Z.A.R.V.I.S. orchestrator converts owner text or voice transcripts into constrained tool calls, returns speech-ready results, records immutable audit events, and persists owner session history.

This service is permanently bound to GitHub user ID `4076926` (`cvsz`). The owner ID is a source-code invariant and cannot be replaced through environment variables.

## Boundary

```text
Trusted identity edge
        |
        | fixed owner assertion + edge secret
        v
ZARVIS Console / ZVoice
        |
        | fixed owner service identity + service token
        v
ZARVIS Orchestrator
        |                 |
        |                 +--> append-only session events + idempotency results
        |
        +--> fixed-host HTTPS GET --> GitHub REST API
```

The browser never receives `GITHUB_TOKEN`, the edge secret, or the service token. The only registered tool remains `github.repository.status`; unknown or mutating tool names fail closed.

## Durable session runtime

The default single-owner deployment uses `FileSessionStore`:

- fixed `${ZARVIS_DATA_DIR}/session-events.jsonl` journal for append-only session transitions;
- fixed `${ZARVIS_DATA_DIR}/command-results.jsonl` journal for idempotency result envelopes;
- request/session/command identifiers never influence filesystem paths;
- all writes and privacy compaction are serialized through one in-process lock;
- file and directory modes are restricted to the service account;
- `command_id` idempotency uses a SHA-256 payload fingerprint;
- `409 idempotency_conflict` is returned when the same `command_id` is reused with different content;
- session history view and explicit confirmation-gated deletion are available to the owner;
- deletion atomically compacts both journals and removes all records associated with the session.

The storage contract is an adapter boundary. A later PostgreSQL/outbox implementation can replace the file adapter without changing the HTTP or orchestrator contracts.

## Run

```bash
export ZARVIS_ORCHESTRATOR_SERVICE_TOKEN='<at-least-32-random-bytes>'
export ZARVIS_DATA_DIR='/var/lib/zarvis'
pnpm --filter @z-platform/zarvis-orchestrator start
```

Environment variables:

| Variable | Default | Purpose |
|---|---:|---|
| `PORT` | `8094` | HTTP listen port |
| `HOST` | `0.0.0.0` | HTTP listen address |
| `GITHUB_TOKEN` | unset | Optional server-side token for private repositories or higher rate limits |
| `ZARVIS_GITHUB_TIMEOUT_MS` | `5000` | GitHub request timeout |
| `ZARVIS_ORCHESTRATOR_SERVICE_TOKEN` | required | Authenticates Console/ZVoice to the orchestrator; minimum 32 bytes |
| `ZARVIS_DATA_DIR` | `./data/zarvis` | Durable session and idempotency storage root |

There is intentionally no `ZARVIS_OWNER_GITHUB_ID` configuration variable.

## Protected API

Every route except `GET /healthz` requires:

```text
x-zarvis-owner-id: 4076926
x-zarvis-service-token: <matching service token>
```

Caller-supplied user and tenant headers are ignored. Audit and session events always use:

```text
user_id: github:4076926
tenant_id: owner-4076926
```

### `POST /v1/commands`

```json
{
  "schema_version": "zarvis.command.requested.v1",
  "command_id": "command-1",
  "session_id": "session-1",
  "input": {
    "modality": "voice",
    "text": "ตรวจสถานะ GitHub cvsz/z-platform",
    "locale": "th-TH"
  }
}
```

The response includes `replayed: false` for a new execution and `replayed: true` for a safe idempotent replay.

### `GET /v1/sessions/{session_id}?limit=100`

Returns the latest 1-500 append-only session events for the owner.

### `DELETE /v1/sessions/{session_id}`

Requires an explicit confirmation header:

```text
x-zarvis-confirm-delete: <same session_id>
```

Without the matching confirmation the service returns `428 confirmation_required`.
