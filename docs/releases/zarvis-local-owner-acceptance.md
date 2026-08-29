# Z.A.R.V.I.S. Local Owner-Machine Acceptance

This checklist must be completed on the actual Ubuntu/Linux host or VM. CI cannot prove physical-device audio, camera, screen, firewall, browser, storage, or operator-experience behavior.

## Host and access

- [ ] Host is controlled only by GitHub owner ID `4076926`.
- [ ] `.env.zarvis.local` is mode `0600` and excluded from backups/artifacts intended for sharing.
- [ ] Ports 8098 and 8099 listen only on `127.0.0.1` or `::1`.
- [ ] Access from a second LAN device fails.
- [ ] No router port forwarding, public tunnel, reverse proxy, or wildcard listener exposes the consoles.

## Voice and command

- [ ] Typed command returns the expected owner-bound GitHub status.
- [ ] Push-to-start microphone works and stops after the interaction.
- [ ] Thai and English speech output are understandable.
- [ ] Browser developer tools show no provider, worker, or GitHub credential.

## Tasks

- [ ] Read-only multi-step task shows the exact plan digest and nonce.
- [ ] Altered digest/nonce is rejected.
- [ ] Pause, resume, cancel, retry, expiry, and restart recovery behave as documented.

## Memory and privacy

- [ ] Proposed memory is invisible until owner confirmation.
- [ ] Correction creates a new revision.
- [ ] Export contains active owner memories only.
- [ ] Delete and retention purge remove all encrypted revisions.
- [ ] Backup and restore with the correct external key succeeds.

## Perception

- [ ] File, screen, and camera require explicit purpose/modality consent.
- [ ] Screen/camera indicators stop immediately after one frame.
- [ ] PII and instruction-like text are redacted/neutralized.
- [ ] Raw media is not retained.
- [ ] Stop, expiry, and delete prevent further access.

## Local actions

- [ ] Preview displays exact previous and next values and no external side effects.
- [ ] Browser cannot execute without the worker.
- [ ] Stale state is rejected.
- [ ] Rollback restores the prior value.
- [ ] Emergency stop survives restart and revokes pending/approved actions.

## Proactive intelligence

- [ ] Timezone and quiet hours match the owner's expectation.
- [ ] Budget, confidence, cooldown, and deduplication suppress correctly.
- [ ] Feedback and schedule revocation are immediate.
- [ ] Action handoff remains a suggestion and creates no action automatically.

## Operations

- [ ] Automated local release workflow artifact and manifest are available for the installed release SHA.
- [ ] Backup/restore drill succeeds on the actual host.
- [ ] All old credentials fail after rotation.
- [ ] Restart recovery is within the local 60-second objective.
- [ ] Memory, CPU, PID, read-only root, capability, and no-new-privileges controls are active.
- [ ] Incident-response contacts and offline recovery material are available.

## Acceptance record

- Release SHA:
- Host/VM identifier:
- Ubuntu version:
- Browser version:
- Date/time (Asia/Bangkok):
- Owner result: **PASS / FAIL**
- Exceptions and evidence locations:

Until this record is completed, automated release evidence may be complete while actual-host acceptance remains pending.
