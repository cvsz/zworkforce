# Z.A.R.V.I.S. Owner Memory & Privacy

Encrypted, owner-confirmed memory service for Epic #148 / Issue #152.

## Invariants

- Owner is permanently `github:4076926` in tenant `owner-4076926`.
- No long-term memory is written silently.
- Every new memory and correction begins as a proposal.
- Confirmation requires the exact SHA-256 digest and one-time nonce before expiry.
- Raw credentials, private keys, bearer tokens, API keys, and payment-card-like values are rejected before persistence.
- All events are encrypted with AES-256-GCM in one fixed-path journal.
- Memory IDs never influence filesystem paths.
- Deletion compacts the encrypted journal and removes every proposal and revision for the memory.

## Required configuration

```bash
export ZARVIS_EDGE_SHARED_SECRET='<at-least-32-random-bytes>'
export ZARVIS_MEMORY_WORKER_TOKEN='<independent-32-byte-token>'
export ZARVIS_MEMORY_MASTER_KEY_B64="$(openssl rand -base64 32)"
export ZARVIS_MEMORY_DATA_DIR='/var/lib/zarvis-memory'
pnpm --filter @z-platform/zarvis-memory start
```

The master key must decode to exactly 32 bytes and must be stored in the deployment secret manager. Losing the key makes the journal unrecoverable. Exposing the key compromises every memory record.

## API

- `GET /healthz`
- `POST /v1/memory/proposals`
- `POST /v1/memory/proposals/{proposal_id}/confirm`
- `GET /v1/memories?q=&classification=`
- `GET /v1/memories/{memory_id}`
- `POST /v1/memories/{memory_id}/corrections`
- `DELETE /v1/memories/{memory_id}` with exact confirmation header
- `GET /v1/memories/export`
- `POST /v1/internal/memory/purge-expired` with worker bearer token

The root path serves the owner-only privacy console.

## Retention

| Classification | Default | Maximum |
|---|---:|---:|
| Working | 1 day | 7 days |
| Episodic | 90 days | 365 days |
| Semantic | 365 days | 3650 days |
| Procedural | 365 days | 3650 days |

Expired memories are hidden immediately and physically removed by the authenticated retention worker.

## Retrieval

The service exposes a deterministic local lexical retriever as the first retrieval adapter. It decrypts only inside the owner service boundary, filters active records, scores query-token overlap, and returns provenance. A future embedding adapter must preserve the same owner scope, deletion semantics, and provenance contract.
