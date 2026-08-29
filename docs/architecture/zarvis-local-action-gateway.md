# Z.A.R.V.I.S. Local Action Gateway Architecture

Epic: #148  
Issue: #154

## Trust flow

```text
Owner browser on 127.0.0.1
  -> owner token
  -> dry-run preview and exact impact
  -> SHA-256 digest + one-time nonce approval
  -> approved action journal
  -> worker-only queue endpoint
  -> isolated local worker
  -> compare-and-set local mutation
  -> execution-bound rollback proof
```

## Local-only boundary

The HTTP service accepts loopback clients only and refuses a non-loopback bind address. Ubuntu/Linux Compose uses host networking so the process remains bound to `127.0.0.1` inside the container. No reverse proxy, public DNS, Cloudflare, or Internet ingress is required.

## Capability model

The registry contains exactly one capability:

```text
sandbox.preference.set
scope: owner-sandbox/preferences
external side effects: none
network access: none
reversible: true
```

Every other capability fails closed. Untrusted-content, policy-effect, and tool-grant fields are rejected rather than interpreted.

## Durability

The local adapter uses operator-controlled fixed paths:

- `action-events.jsonl` — append-only lifecycle snapshots;
- `local-state.json` — atomically replaced preference and emergency-stop state.

Action IDs, keys, values, headers, and request paths never determine filesystem paths.

## Approval and execution

The approval digest binds action ID, capability, key, previous value, next value, immutable owner identity, tenant, and expiry. Approval consumes its nonce. The worker has a separate token, never receives the owner token, and sees only approved action IDs. Execution compares the current value with the previewed previous value; drift returns `stale_preview` without mutation.

## Recovery

Successful execution creates a rollback digest and nonce bound to the execution ID and both values. Rollback uses compare-and-set again. Emergency stop persists before revoking all non-terminal actions and blocks new previews and execution until exact owner resume confirmation.
