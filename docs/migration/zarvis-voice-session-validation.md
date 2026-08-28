# Z.A.R.V.I.S. Voice Session Validation

Date: 2026-08-06
Epic: #148
Vertical slice: realtime voice transcript bridge and durable owner sessions

## Local validation

Runtime: Node.js `v22.16.0`

```text
services/zarvis-orchestrator: 12 passed
apps/zvoice:                 7 passed
packages/contracts:          4 passed
------------------------------------
total:                      23 passed
failed:                      0
```

## Covered behavior

- Thai repository-status intent inference.
- Read-only fixed-host GitHub adapter and token redaction.
- Durable append-only session events.
- File store reconstruction after process restart.
- Complete session privacy deletion, including all referenced command snapshots.
- Command result persistence and deletion.
- Identical `command_id` replay without a second tool execution.
- Conflicting `command_id` reuse rejected.
- Owner-only session history API.
- Confirmation-gated session deletion.
- ZVoice trusted-edge bypass rejection for static UI and APIs.
- Immutable owner identity replacement.
- Required transcript validation before upstream calls.
- Voice transcript conversion to the versioned command contract.
- Absence of edge and orchestrator secrets from health and command responses.
- Backward-compatible generic ZVoice identity mode when owner mode is disabled.

## Remaining external gates

- Full repository CI, validate, CodeQL, and operations workflows on the PR head.
- Deployment of exact owner policy at the identity edge.
- Direct-origin firewall verification.
- Persistent-volume backup/restore drill.
- Secret rotation and emergency-revocation drill.
- Live voice-gateway integration smoke test in the authorized environment.
