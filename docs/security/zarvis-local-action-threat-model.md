# Z.A.R.V.I.S. Local Action Threat Model

| Threat | Control |
|---|---|
| Remote access | Server binds and accepts loopback only; Linux Compose uses host networking |
| Shared secret guessing | Independent 32-byte minimum owner and worker tokens; constant-time comparison |
| Browser bypasses approval | Browser has no worker token; execution exists only on worker-authenticated internal route |
| Worker impersonates owner | Worker has no owner token and cannot preview, approve, roll back, stop, or resume |
| Approval tampering | SHA-256 digest binds exact previous/next values, capability, owner, tenant, and expiry |
| Approval replay | One-time nonce is consumed and approved/executed transitions are idempotent |
| Stale preview | Compare-and-set verifies current value equals previewed previous value |
| Rollback corruption | Execution-bound rollback proof plus second compare-and-set |
| Confused deputy | Untrusted-content, policy-effect, and tool-grant fields are rejected |
| Capability escalation | Default-deny registry contains only `sandbox.preference.set` |
| Arbitrary file write | Two fixed operator-controlled paths; input never determines a path |
| External side effects | First fixture has no network call and changes only local sandbox preference state |
| Emergency persistence gap | Emergency-stop state is written before action revocation |
| Secret disclosure | Health/status omit tokens; worker and browser each receive only their own credential |
| Container privilege | Read-only root filesystem, all Linux capabilities dropped, no-new-privileges |

## Explicitly unavailable

The gateway does not implement shell execution, arbitrary browser automation, GitHub mutation, email/calendar mutation, payment or wallet actions, device control, package installation, destructive deletion, or unattended external actions.
