# Z.A.R.V.I.S. Memory Operations Runbook

## Start

```bash
export ZARVIS_EDGE_SHARED_SECRET='<edge-secret>'
export ZARVIS_MEMORY_WORKER_TOKEN='<independent-worker-token>'
export ZARVIS_MEMORY_MASTER_KEY_B64="$(openssl rand -base64 32)"
export ZARVIS_MEMORY_DATA_DIR='/var/lib/zarvis-memory'
pnpm --filter @z-platform/zarvis-memory start
```

Verify health reports owner-only, encrypted-at-rest, and no silent long-term writes.

## Smoke test

1. Create a semantic memory proposal.
2. Confirm the memory list remains empty before approval.
3. Review and submit the returned digest and nonce.
4. Search for a term in the confirmed content.
5. Export and verify provenance and retention fields.
6. Correct the memory through a second proposal and confirmation.
7. Delete using the exact confirmation header.
8. Verify list/search/export no longer contain the memory.

## Retention

Run the purge worker at least daily:

```text
POST /v1/internal/memory/purge-expired
Authorization: Bearer <ZARVIS_MEMORY_WORKER_TOKEN>
```

Expired records are already excluded from retrieval before physical compaction.

## Backup

Back up the encrypted journal and key separately. A journal backup without the key is unreadable; a key without the journal contains no memory data. Use encrypted, access-controlled, filesystem-consistent snapshots.

## Restore

1. Restore the journal into an empty data directory.
2. Restore the matching master key through the secret manager.
3. Start the service.
4. List and export memories.
5. Confirm one correction and one deletion.
6. Verify no authentication or decryption errors.

## Emergency deletion

Disable edge access, stop the service, take incident evidence if required, then use the authenticated delete API or securely erase the entire encrypted journal and destroy all backups and the corresponding key according to retention policy.

## Key compromise

Immediately disable access, stop the service, rotate edge/worker credentials, preserve audit evidence, migrate active records to a new key during controlled recovery, destroy the compromised key, and review backups. Production rotation automation remains tracked in #156.
