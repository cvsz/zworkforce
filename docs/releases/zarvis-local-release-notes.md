# Z.A.R.V.I.S. Local Release Notes

## Release profile

Z.A.R.V.I.S. is a single-owner local assistant platform bound to GitHub owner ID `4076926`. The supported release target is one Ubuntu/Linux host or VM with user-facing services exposed only on loopback.

## Included capabilities

- owner-only typed and push-to-start voice commands;
- constrained read-only GitHub repository status;
- durable voice sessions and idempotent command replay;
- durable read-only DAG tasks with exact-plan approval;
- encrypted, owner-confirmed memory with privacy export/delete/purge;
- consent-based one-shot file, screen, and camera perception;
- one reversible local sandbox preference action with preview, exact approval, worker execution, rollback, and emergency stop;
- owner-defined local health schedules with quiet hours, budgets, confidence, cooldown, deduplication, explainable suggestions, feedback, revocation, and approval-only handoff.

## Local security profile

- no account registration, guest access, invitations, owner reassignment, or multi-tenant mode;
- no public or LAN ingress;
- independent owner/action-worker/proactive-worker credentials;
- read-only container roots, dropped capabilities, no-new-privileges, and bounded CPU/memory/PIDs/files;
- no arbitrary shell, arbitrary filesystem write, broad browser automation, financial action, device control, or autonomous proactive mutation;
- fixed-path local journals and confirmation-gated destructive privacy operations.

## Release evidence

The ZARVIS Local Release workflow generates immutable JSON evidence for container/socket hardening, automated owner acceptance, SLO sampling, red-team checks, restart recovery, backup integrity, restore verification, credential rotation, and an SHA-256 manifest. Main-branch workflow runs attest the final manifest.

## Compatibility

The local action and proactive event journals remain backward-compatible within this release line. Backup archives do not contain `.env.zarvis.local`; credentials must be protected and recovered separately.

## Known limitation

Automated evidence does not configure or validate the owner's actual physical host, microphone, camera, screen picker, browser, firewall, virtualization, or external memory encryption key. Complete `docs/releases/zarvis-local-owner-acceptance.md` on the target machine before declaring that host accepted.
