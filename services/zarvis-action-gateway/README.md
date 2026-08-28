# Z.A.R.V.I.S. Local Action Gateway

Owner-only, loopback-only action gateway for the first reversible Z.A.R.V.I.S. mutation.

## Implemented capability

` sandbox.preference.set ` changes one string preference in the local owner sandbox. It has no external network side effect and cannot write outside the operator-controlled fixed state file.

The lifecycle is mandatory:

1. owner creates a dry-run preview;
2. preview captures the previous value and exact impact;
3. owner approves the SHA-256 digest and one-time nonce before expiry;
4. an independently authenticated local worker executes with compare-and-set protection;
5. owner can roll back using execution-bound digest and nonce;
6. emergency stop revokes every pending/approved action and blocks new previews.

## Local installation on Ubuntu/Linux

```bash
bash scripts/zarvis-local-setup.sh
```

Open `http://127.0.0.1:8098`, then enter `ZARVIS_LOCAL_OWNER_TOKEN` from `.env.zarvis.local`.

The Compose deployment uses host networking so the service can remain bound to loopback inside the container. It is intentionally Linux-only.

## Direct Node installation

```bash
export ZARVIS_LOCAL_OWNER_TOKEN="$(openssl rand -hex 32)"
export ZARVIS_ACTION_WORKER_TOKEN="$(openssl rand -hex 32)"
export ZARVIS_ACTION_DATA_DIR="$PWD/var/zarvis-action"
node services/zarvis-action-gateway/server.mjs
```

In a second terminal with only the worker token:

```bash
export ZARVIS_ACTION_WORKER_TOKEN='<same-worker-token>'
node services/zarvis-action-gateway/worker.mjs
```

## Security boundaries

- default bind address is `127.0.0.1`;
- non-loopback bind configuration fails startup;
- immutable owner identity is `github:4076926` / `owner-4076926`;
- owner and worker tokens are independent and require at least 32 bytes;
- the worker never receives the owner token;
- the browser never receives the worker token;
- capability registry is default-deny;
- shell, GitHub writes, email, finance, wallets, device control, and arbitrary filesystem writes are not registered;
- request values never influence a filesystem path;
- every transition is append-only audited;
- state drift fails closed and requires a new preview.

## Tests

```bash
npm test --prefix services/zarvis-action-gateway
```
