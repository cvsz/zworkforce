# Z.A.R.V.I.S. Local Proactive Scheduler

Loopback-only, single-owner scheduler for bounded read-only checks and explainable suggestions.

## Implemented vertical slice

- owner-defined schedule for `local.service.health`;
- allowlisted target `zarvis-action-gateway`;
- IANA timezone and missed-run policy;
- quiet hours, daily notification budget, confidence threshold, cooldown, and deduplication;
- explainable suggestion inbox with source URL and evidence;
- useful, irrelevant, and false-positive feedback;
- revocable subscriptions;
- optional action handoff that creates a request only and always reports `requires_owner_approval: true` and `executed: false`.

There is no autonomous mutation. The service and worker do not hold the action-gateway owner or worker token.

## Local installation

```bash
bash scripts/zarvis-local-setup.sh
```

Open:

- Action Console: `http://127.0.0.1:8098`
- Proactive Console: `http://127.0.0.1:8099`

Use `ZARVIS_LOCAL_OWNER_TOKEN` from `.env.zarvis.local` to unlock both consoles.

## Direct Node execution

```bash
export ZARVIS_LOCAL_OWNER_TOKEN="$(openssl rand -hex 32)"
export ZARVIS_PROACTIVE_WORKER_TOKEN="$(openssl rand -hex 32)"
export ZARVIS_PROACTIVE_DATA_DIR="$PWD/var/zarvis-proactive"
node services/zarvis-proactive/server.mjs
```

Second terminal:

```bash
export ZARVIS_PROACTIVE_WORKER_TOKEN='<same-proactive-worker-token>'
node services/zarvis-proactive/worker.mjs
```

## Security boundaries

- server binds and accepts loopback clients only;
- owner and proactive-worker tokens are independent;
- worker can only request one scheduler tick;
- schedule creation rejects untrusted-content, policy-effect, and tool-grant fields;
- health target must be an allowlisted loopback HTTP `/healthz` URL;
- redirect, credentials, query, fragment, arbitrary URL, and non-loopback checks are rejected;
- every evaluation and notification decision is append-only audited;
- suppressed notifications remain visible for explainability but do not consume delivered budget;
- action handoff is a data object, not an action call.

## Tests

```bash
npm test --prefix services/zarvis-proactive
```
