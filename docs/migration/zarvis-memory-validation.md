# Z.A.R.V.I.S. Owner Memory Validation

Date: 2026-08-06
Epic: #148
Issue: #152
Branch: `feat/zarvis-owner-memory-privacy`

## Focused coverage

- exact 32-byte base64 master-key validation;
- raw credential/private-key rejection before persistence;
- proposal invisibility before owner confirmation;
- digest and nonce mismatch rejection;
- AES-256-GCM journal with no plaintext content or provenance on disk;
- idempotent confirmation replay;
- correction revision and owner-scoped retrieval;
- active-memory export;
- physical compaction of every proposal and revision during deletion;
- retention hiding and worker purge;
- owner-only privacy console and APIs;
- explicit deletion confirmation;
- independent retention-worker authentication;
- startup failure without edge, worker, or encryption key.

## Required gates

- [ ] `services/zarvis-memory` focused tests pass.
- [ ] `packages/contracts` memory schema tests pass.
- [ ] All existing command, voice, task, and platform tests pass.
- [ ] CI passes.
- [ ] Validate passes.
- [ ] CodeQL Advanced passes with no unresolved thread.
- [ ] Operations passes.

## Production evidence retained for #156

- external key-manager and rotation drill;
- direct-origin denial;
- encrypted backup/restore test;
- production database/vector derivative deletion evidence;
- retention-worker deployment and monitoring;
- privacy export/delete owner acceptance test on release infrastructure.
