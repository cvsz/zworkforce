# Z.A.R.V.I.S. Local Release Evidence Map

Epic: #148  
Release hardening: #156

| Capability / invariant | Merged implementation | Automated release evidence |
|---|---|---|
| Immutable single owner | PR #149 and all later phases | Health/status identities, wrong-owner red-team |
| Voice command and GitHub read-only tool | PR #149 | Existing CI/contracts and owner-machine checklist |
| Realtime voice and durable sessions | PR #150 | Existing CI/contracts and owner-machine checklist |
| Durable tasks and exact-plan approval | PR #157 | Existing CI/contracts and owner-machine checklist |
| Encrypted memory/privacy | PR #158 | Existing CI/contracts and owner-machine checklist |
| Consent perception | PR #159 | Existing CI/contracts and owner-machine checklist |
| Reversible local action | PR #160 | Release acceptance, rollback, emergency revoke, restart, restore |
| Bounded proactive scheduler | PR #161 | Release acceptance, red-team, feedback/revoke/handoff evidence |
| Loopback-only access | PRs #160–#161 | Container/socket evidence and Local workflows |
| No unapproved mutation | PR #160 | Approval lifecycle, wrong-token/capability red-team |
| No autonomous proactive mutation | PR #161 | Handoff/action-count red-team and manifest assertion |
| Resource bounds | Release PR | Docker inspection evidence |
| SLO | Release PR | Bounded health/status latency and error samples |
| Backup and restore | Release PR | Backup SHA manifest and restored-ID verification |
| Rotation | Release PR | Old credential rejection/new credential acceptance |
| Restart and worker interruption | Release PR | Restart drill with durable state and recovery timing |
| Secret-safe evidence | Release PR | Response scans and artifact secret scan |
| Evidence integrity | Release PR | SHA-256 release manifest and main-branch provenance attestation |
| Actual host/browser/device behavior | Manual checklist | Explicitly pending until run on the target machine |

The release manifest records the release SHA, evidence hashes, automated assertions, prohibited capabilities, and manual acceptance status. CI evidence does not claim that the owner's physical host has been configured or accepted.
