# Local Compose Operations

The repository root contains a runnable `compose.yml` for the services that currently expose executable Node HTTP servers:

- Agent Control Panel on host loopback port `3000`
- ZChat on host loopback port `3021`
- ZWallet on host loopback port `3040`
- AI Gateway on host loopback port `8400`
- Agent Orchestrator on host loopback port `8500`
- Workspace Runtime on host loopback port `8600`
- Billing Ledger on host loopback port `8700`
- Agent Provider on host loopback port `8800`

## Start

```bash
cp .env.example .env
sed -i "s/^Z_PLATFORM_SERVICE_TOKEN=.*/Z_PLATFORM_SERVICE_TOKEN=$(openssl rand -hex 32)/" .env

docker compose config
docker compose build
docker compose up -d
docker compose ps
```

Provider-backed AI requests additionally require `UPSTREAM_BASE_URL` and `AI_GATEWAY_PROVIDER_TOKEN` in `.env`.

## Verify health

```bash
curl --fail --silent --show-error http://127.0.0.1:8400/health
curl --fail --silent --show-error http://127.0.0.1:8500/health
curl --fail --silent --show-error http://127.0.0.1:8600/health
curl --fail --silent --show-error http://127.0.0.1:8700/health
curl --fail --silent --show-error http://127.0.0.1:8800/health
curl --fail --silent --show-error http://127.0.0.1:3040/health
curl --fail --silent --show-error http://127.0.0.1:3021/health
```

## Real internal endpoint

The AI Gateway uses the Compose DNS endpoint:

```text
http://billing-ledger:8700
```

This is configured as `Z_PLATFORM_BILLING_LEDGER_URL` inside `compose.yml`.

## Agent provider status

Local execution intentionally uses:

```text
AGENT_ORCHESTRATOR_PROVIDER_MODE=memory
```

The repository does not yet contain HTTP services implementing the required job-store, queue, audit, identity, and sandbox provider contracts. Therefore these values must remain unset for the local stack:

```text
AGENT_JOB_STORE_URL
AGENT_QUEUE_URL
AGENT_AUDIT_URL
AGENT_IDENTITY_URL
AGENT_SANDBOX_URL
```

`workspace-runtime` is not a drop-in sandbox provider: the orchestrator expects `POST /execute`, while workspace-runtime exposes approval-gated project, shell, and deploy endpoints.

## Stop

```bash
docker compose down
```

Add `--remove-orphans` when cleaning up obsolete local containers.
