# GitHub Environments Operations Guide

This guide defines the required GitHub Environments for `z-platform` and how they must be configured before staging or production traffic is enabled.

## Required environments

| Environment | Purpose | Required protection |
|---|---|---|
| `ci` | Automated validation for pull requests and pushes | No production secrets; read-only validation only |
| `staging` | Production-equivalent verification before external traffic | Required reviewers, environment secrets, deployment branch restriction |
| `production` | External traffic and production releases | Required reviewers, strict branch restriction, operator approval, rollback notes |

Do not store provider credentials, service tokens, payment secrets, wallet keys, MPC shares, KYC data, or production identifiers in repository files. Use GitHub Environment secrets or the approved secret manager only.

## How to create environments

1. Open `cvsz/z-platform` on GitHub.
2. Go to **Settings**.
3. Open **Environments**.
4. Create `ci`, `staging`, and `production`.
5. Configure protection rules before adding secrets.

Repository-local automation is available in `scripts/configure-github-environments.sh`. It creates or updates `ci`, `staging`, and `production`, loads `.env`, `.env.phase6`, and `.env.phase6.server` in order, and imports populated keys into GitHub environment variables and secrets for the environments that use them. It still requires explicit reviewer selectors such as `user:LOGIN` or `team:SLUG` when a reviewer is supplied on the command line. Bare `STAGING_REVIEWER`, `PRODUCTION_REVIEWER`, and `PRODUCTION_APPROVER` values from the env overlays are treated as GitHub user logins, and the helper also publishes the operator-owned non-secret review fields `INCIDENT_OWNER`, `ESCALATION_ROUTE`, and `WATCH_WINDOW` into the `staging` environment so release records and sign-off workflows can consume the same values without retyping them.
It also updates deployment branch policies for `staging` and `production`, so the helper can enforce `main`-only or protected-branch behavior without manual API calls.

## `ci` environment

Use `ci` only for non-secret validation.

Required settings:

- No production provider credentials.
- No payment, wallet, KYC, MPC, or signing credentials.
- No deployment permission.
- CI workflows may use repository read permission and generated test data only.
- Environment bootstrap scripts may create the environment, but `ci` must remain free of secrets and reviewer protection.

## `staging` environment

Use `staging` for production-equivalent validation before production rollout.

Required settings:

- Required reviewers: at least one operator or maintainer.
- Deployment branches: restrict to `main` or protected branches only.
- Environment secrets: staging-only service tokens and provider URLs.
- Environment variables: non-secret staging configuration only.
- Observability: logs, metrics, traces, and alerts visible before sign-off.
- Backups: restore test completed before production promotion.
- Use `scripts/configure-github-environments.sh` to apply the environment and branch policy with operator-approved reviewer selectors.

Suggested staging secrets:

| Secret | Purpose |
|---|---|
| `Z_PLATFORM_SERVICE_TOKEN` | Internal service authentication for staging only |
| `AI_GATEWAY_PROVIDER_TOKEN` | Upstream AI provider credential, held server-side only |
| `AGENT_JOB_STORE_URL` | Durable staging job store endpoint |
| `AGENT_QUEUE_URL` | Durable staging queue endpoint |
| `AGENT_AUDIT_URL` | Staging audit/event sink endpoint |
| `AGENT_IDENTITY_URL` | Staging identity approval endpoint |
| `AGENT_SANDBOX_URL` | Staging sandbox runtime endpoint |
| `BILLING_LEDGER_URL` | Staging billing ledger endpoint |
| `SUPABASE_URL` | Supabase project URL for the read-only Data API bridge |
| `SUPABASE_ANON_KEY` | Read-only Supabase anon key, kept server-side |
| `SUPABASE_TABLE` | Exposed Supabase table queried by the Phase 6 API |

Secret names are examples. Operator-approved provider names may differ, but browser-visible apps must never receive upstream provider credentials.

The Phase 6 API reads these Supabase values from the loaded `.env`, `.env.phase6`, and `.env.phase6.server` overlays when the helper script refreshes the GitHub environment. Only the anon key is sensitive; the URL and table name are operational configuration.

## `production` environment

Use `production` only after staging readiness is complete.

Required settings:

- Required reviewers: operator approval required.
- Deployment branches: restrict to `main` only, or the protected release branch selected by the operator.
- Environment secrets: production credentials only in GitHub Environment secrets or approved secret manager.
- Deployment notes: record commit SHA, workflow result, rollback SHA, data migration status, and incident owner.
- Traffic gate: keep external traffic disabled until health checks, logs, metrics, traces, and alerts are visible.
- Use `scripts/configure-github-environments.sh` to apply the environment and branch policy with the authorized production reviewer selector.

Production must not be the first environment to exercise a provider, queue, database, identity policy, sandbox profile, billing integration, Cloudflare rule, GitHub App token format, or restore path.

## Workflow usage

GitHub Actions jobs that deploy or verify an environment should declare the environment explicitly:

```yaml
jobs:
  staging-readiness:
    environment: staging
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "Run staging readiness checks here"
```

Deployment workflows must not print secrets. Prefer smoke tests that validate health endpoints, gateway-only access, approval gates, billing idempotency, ZWallet denial paths, and observability signals.

## Required staging smoke checks

- ZAI Coder web and CLI use only the AI Gateway.
- Browser clients cannot access provider secrets or service tokens.
- AI Gateway model catalog responds.
- Chat and streaming paths work through the gateway.
- File upload path works through the gateway.
- Workspace metadata uses the durable staging adapter.
- Agent job can be submitted, approved, executed with scoped tools, cancelled, retried idempotently, and audited.
- Workspace Runtime denies shell/deploy without approval grants.
- Billing Ledger accepts usage idempotently and rejects duplicates safely.
- ZWallet adapter rejects signing, cards, KYC, MPC, and swaps.
- Logs, metrics, traces, and alerts are visible.
- Backup restore has passed in staging.

## Operator sign-off record

Before production, record:

- environment name
- commit SHA
- GitHub workflow run result
- staging reviewer
- production approving operator
- selected identity provider
- selected Cloudflare account/zone/team domain
- selected secret manager
- selected database, queue, sandbox, observability, audit, billing, and backup providers
- rollback SHA and verification commands
- incident owner and post-launch watch window

## Related documents

- [Production master document](production-master.md)
- [Staging readiness review](staging-readiness.md)
- [Cloudflare Access service policies](cloudflare-access.md)
- [GitHub App token format readiness](github-app-token-format.md)
