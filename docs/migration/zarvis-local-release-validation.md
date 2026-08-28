# Z.A.R.V.I.S. Local Release Validation

Date: 2026-08-06  
Epic: #148  
Issue: #156  
Branch: `feat/zarvis-local-release-hardening`

## Automated evidence

- hardened Compose resource and privilege controls;
- exclusive loopback socket binding;
- action preview, exact approval, execution, rollback, emergency revoke, and resume;
- proactive policy, schedule, notification, feedback, revoke, and approval-only non-executing handoff;
- bounded health/status load with zero errors and p95 ≤ 750 ms;
- wrong-owner and wrong-worker denial;
- capability, confused-deputy, path, request-size, registration, SSRF, and secret-leak red-team cases;
- worker interruption and service restart with durable state recovery ≤ 60 seconds;
- SHA-256 backup archives excluding credentials;
- destructive volume removal, verified restore, and acceptance-ID reconstruction;
- independent owner/action-worker/proactive-worker rotation with old credential rejection;
- evidence secret scan;
- SHA-256 evidence manifest bound to the source SHA;
- artifact upload and main-branch manifest provenance attestation.

## Required workflows

- [ ] CI passes;
- [ ] validate passes, including deployed smoke and SBOM;
- [ ] CodeQL Advanced passes with no unresolved review thread;
- [ ] operations passes;
- [ ] ZARVIS Local passes;
- [ ] ZARVIS Local Release passes;
- [ ] release manifest reports every automated assertion as true;
- [ ] PR is squash-merged as one complete vertical slice.

## Honest completion boundary

Passing this validation means the repository and ephemeral Ubuntu/Linux release workflow are complete for the documented local deployment profile. It does not mean the owner's actual machine, microphone, camera, display capture, browser, firewall, virtualization, external memory key, or backups have been configured or manually accepted. That evidence remains `pending_actual_target_host` until the owner completes `docs/releases/zarvis-local-owner-acceptance.md`.
