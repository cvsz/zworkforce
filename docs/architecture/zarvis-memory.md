# Z.A.R.V.I.S. Owner Memory Architecture

Epic: #148
Issue: #152

## Flow

```text
Owner/session/task source
      -> memory proposal + provenance
      -> safety classification
      -> exact digest + nonce
      -> owner confirmation
      -> AES-256-GCM encrypted journal
      -> owner-scoped retrieval/export/delete
```

## Event model

The journal contains encrypted events:

- `memory.proposal-created.v1`;
- `memory.confirmed.v1`;
- future lifecycle events may be added only through versioned contracts.

The active snapshot is reconstructed by applying confirmed revisions in order. Proposals do not affect retrieval until confirmed. Corrections create a new proposal for the same `memory_id` and next revision.

## Encryption boundary

- AES-256-GCM with a random 96-bit IV per event;
- fixed authenticated additional data identifying the Z.A.R.V.I.S. memory contract;
- one operator-managed 32-byte master key loaded from the secret manager;
- fixed journal path `memory-events.enc.jsonl` under `ZARVIS_MEMORY_DATA_DIR`;
- plaintext exists only inside the service process while validating, retrieving, exporting, or compacting.

The first slice intentionally avoids a separate plaintext search index. Lexical retrieval decrypts active records server-side, which ensures deletion has no derivative index to clean. Future vector storage must support owner-scoped deletion and provenance parity before adoption.

## Privacy lifecycle

1. Proposed content is classified and checked for raw secrets.
2. Owner reviews content, reason, provenance, retention, digest, and expiry.
3. Exact confirmation creates the active encrypted revision.
4. Retrieval excludes expired records and always returns provenance.
5. Correction repeats the proposal/confirmation path.
6. Export returns active non-expired records in a versioned owner-bound document.
7. Delete atomically compacts all encrypted proposal and revision events for the memory.
8. Retention worker compacts expired memories with an independent credential.

## Scale-out boundary

`EncryptedMemoryStore` is an adapter. A production database/vector adapter must preserve:

- encryption at rest and in transit;
- owner-only isolation;
- proposal confirmation;
- provenance and retention fields;
- exact correction revisions;
- export completeness;
- deletion of primary and derivative records;
- auditable purge behavior.
