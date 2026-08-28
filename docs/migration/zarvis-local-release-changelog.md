# Z.A.R.V.I.S. Local Release Changelog

Date: 2026-08-06

## Added

- immutable single-owner command, voice, task, memory, perception, local action, and proactive boundaries;
- loopback-only Action and Proactive consoles;
- hardened local Compose profile with CPU, memory, PID, file-descriptor, tmpfs, read-only-root, dropped-capability, and no-new-privileges controls;
- automated local owner acceptance with action approval/rollback/emergency revoke and proactive suggestion/feedback/revoke/handoff;
- bounded local health/status SLO sampling;
- cross-boundary security red-team suite;
- worker interruption and service restart recovery drill;
- SHA-256 local volume backup, destructive volume removal, verified restore, and durable state reconstruction;
- independent owner/action-worker/proactive-worker credential rotation verification;
- secret-free release evidence artifact and immutable SHA-256 evidence manifest;
- main-branch provenance attestation for the evidence manifest;
- actual-host owner acceptance checklist and complete local release runbook.

## Security

- public and LAN ingress remain unsupported;
- proactive intelligence cannot execute actions;
- local mutation requires exact owner approval and remains reversible;
- arbitrary shell, arbitrary filesystem write, broad browser automation, financial action, device control, shared accounts, and owner reassignment remain unavailable;
- release evidence is scanned for every configured CI credential before upload.

## Completion boundary

Automated repository and ephemeral Ubuntu/Linux release evidence can be complete. Actual owner-machine acceptance remains pending until the physical host/VM checklist is completed.
