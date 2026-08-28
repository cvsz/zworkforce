# Z.A.R.V.I.S. Perception Operations Runbook

## Start

```bash
export ZARVIS_EDGE_SHARED_SECRET='<edge-secret>'
export ZARVIS_PERCEPTION_WORKER_TOKEN='<independent-worker-token>'
export ZARVIS_PERCEPTION_MASTER_KEY_B64="$(openssl rand -base64 32)"
export ZARVIS_PERCEPTION_DATA_DIR='/var/lib/zarvis-perception'
pnpm --filter @z-platform/zarvis-perception start
```

Health must report owner-only, encrypted analysis, no raw-media retention, no continuous capture, and no biometric identification.

## Smoke test

1. Create a document-only session.
2. Confirm media upload is rejected before activation.
3. Review purpose/modalities/retention and activate with exact digest+nonce.
4. Upload text containing an email and instruction-injection phrase.
5. Confirm redaction, neutralization, empty tool grants, and `policy_effect: none`.
6. Stop the session and confirm later media is rejected.
7. Delete with the exact confirmation header and verify history is gone.
8. Perform one screen and one camera snapshot; verify browser capture indicators end immediately.

## Retention worker

Run at least hourly:

```text
POST /v1/internal/perception/purge-expired
Authorization: Bearer <ZARVIS_PERCEPTION_WORKER_TOKEN>
```

## Backup and restore

Back up the encrypted journal and master key separately. Restore into an empty data directory with the matching key, list sessions, inspect one result, then delete one test session to verify compaction.

## Incident response

Disable edge access, stop the service, rotate edge/worker credentials, preserve the encrypted journal if investigation is required, revoke any future provider credential, and destroy compromised keys/backups under the approved retention procedure.
