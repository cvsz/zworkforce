# Z.A.R.V.I.S. Local Red-Team Plan

## Objectives

Prove that the local release preserves immutable owner identity, loopback-only exposure, capability default-deny, exact mutation approval, proactive non-mutation, secret isolation, request-size limits, and SSRF/path controls.

## Automated cases

| Area | Cases | Expected result |
|---|---|---|
| Owner authentication | Wrong owner token on Action and Proactive status | 403 |
| Worker authentication | Wrong action/proactive worker tokens | 403 |
| Capability abuse | `shell.execute` preview | 403 |
| Confused deputy | `untrusted_content` in action/schedule request | 403 |
| Filesystem abuse | Path traversal in preference key | 400, no file write |
| Resource abuse | Oversized action JSON body | 413 |
| SSRF | Unknown check and metadata-service target | 403, no network request |
| Account expansion | Registration routes on both services | 404 |
| Secret leakage | Scan every response and release artifact for configured credentials | Zero matches |
| Proactive escalation | Create/replay action handoff and compare action count | Unchanged; handoff `executed: false` |
| Health invariants | Local-only and autonomous-mutation flags | Local only, mutation false |

## Manual cases on the target host

- confirm no process listens on wildcard or LAN addresses for Z.A.R.V.I.S. ports;
- attempt access from a second LAN device and confirm failure;
- inspect browser developer tools and confirm worker tokens are never present;
- stop each worker independently and confirm owner consoles remain readable but no work executes;
- attempt to reuse expired approval/rollback values;
- inspect journals and evidence for credentials;
- confirm emergency stop survives service restart;
- confirm proactive handoff requires opening the Action Console and creating/approving a separate preview.

## Pass criteria

All automated checks pass, no response or artifact contains configured credentials, no proactive handoff changes action state, no non-loopback socket exists, and no mutation occurs without exact owner approval.
